"""Detached desktop updater; runs from a copy outside the installed application."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import stat
import subprocess
import sys
import time
import zipfile


def write_json(path, value):
    path = Path(path)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value), encoding='utf-8')
    tmp.replace(path)


def alive(pid):
    if sys.platform == 'win32':
        import ctypes
        kernel = ctypes.windll.kernel32
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(kernel.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code))) and code.value == 259
        finally:
            kernel.CloseHandle(ctypes.c_void_p(handle))
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def wait_until(predicate, seconds, message):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(.2)
    raise RuntimeError(message)


def validate_archive(archive):
    # ditto preserves framework symlinks, but no archive entry may escape staging.
    with zipfile.ZipFile(archive) as bundle:
        if len(bundle.infolist()) > 50000 or sum(i.file_size for i in bundle.infolist()) > 2_000_000_000:
            raise ValueError('The update archive is too large.')
        for entry in bundle.infolist():
            name = entry.filename
            if '\\' in name or name.startswith('/') or '..' in Path(name).parts or ':' in name:
                raise ValueError('Unsafe path in update archive.')
            if stat.S_ISLNK(entry.external_attr >> 16):
                target = bundle.read(entry).decode('utf-8')
                resolved = os.path.normpath(os.path.join(os.path.dirname(name), target))
                if os.path.isabs(target) or resolved.startswith('../') or not resolved.startswith('Lambda.app/'):
                    raise ValueError('Unsafe link in update archive.')


def prepare(job):
    payload, target = Path(job['payload']), Path(job['target'])
    with payload.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != job['sha256']:
        raise ValueError('The update checksum did not match. Your application was not changed.')
    if not target.exists() or target.is_symlink():
        raise ValueError('The installed application could not be located.')
    if sys.platform == 'darwin':
        if target.suffix != '.app':
            raise ValueError('Expected an installed Lambda.app.')
        validate_archive(payload)
        stage = target.parent / ('.lambda-update-' + job['token'][:16])
        stage.mkdir(mode=0o700)
        job['stage'] = str(stage)
        subprocess.run(['/usr/bin/ditto', '-x', '-k', str(payload), str(stage)], check=True, timeout=120)
        candidate = stage / 'Lambda.app'
        info = plistlib.loads((candidate/'Contents/Info.plist').read_bytes())
        if info.get('CFBundleIdentifier') != 'ai.lambda.desktop' or info.get('CFBundleShortVersionString') != job['version']:
            raise ValueError('The downloaded application has the wrong identity or version.')
        if not (candidate/'Contents/MacOS/Lambda').is_file():
            raise ValueError('The update executable is missing.')
        # Validate the sealed bundle before closing/replacing a working install.
        subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(candidate)],
                       check=True, timeout=90, capture_output=True)
        job['candidate'] = str(candidate)
    elif sys.platform == 'linux':
        with payload.open('rb') as stream:
            if stream.read(4) != b'\x7fELF':
                raise ValueError('The update is not an AppImage.')
        stage = target.with_name('.lambda-update-' + job['token'][:16] + '.AppImage')
        shutil.copyfile(payload, stage)
        stage.chmod(0o755)
        job['stage'] = job['candidate'] = str(stage)
    elif sys.platform == 'win32':
        with payload.open('rb') as stream:
            if stream.read(2) != b'MZ':
                raise ValueError('The update is not a Windows installer.')
        if target.name.lower() != 'lambda.exe':
            raise ValueError('Expected the installed Lambda executable.')
    else:
        raise ValueError('In-app updates are not available for this system.')
    # Fail before quitting if the current install cannot be replaced by this user.
    probe = target.parent / ('.lambda-write-' + job['token'][:16])
    with probe.open('x') as stream:
        stream.write('update')
    probe.unlink()


def launch(job, receipt=True):
    target = Path(job['target'])
    executable = target/'Contents/MacOS/Lambda' if sys.platform == 'darwin' else target
    env = dict(os.environ)
    for name in ('ELECTRON_RUN_AS_NODE', 'APPIMAGE', 'APPDIR', 'OWD', 'LAMBDA_UPDATE_RECEIPT', 'LAMBDA_UPDATE_TOKEN'):
        env.pop(name, None)
    if receipt:
        env.update(LAMBDA_UPDATE_RECEIPT=job['receipt'], LAMBDA_UPDATE_TOKEN=job['token'])
    return subprocess.Popen([str(executable)], env=env, cwd=str(target.parent),
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=sys.platform != 'win32')


def apply(job):
    target = Path(job['target'])
    backup = target.with_name('.lambda-previous-' + job['token'][:16] + target.suffix)
    swapped = False
    child = None
    try:
        if sys.platform == 'win32':
            # Native NSIS update mode retains the installed location, shortcuts,
            # uninstaller and user data. No wizard and no automatic duplicate launch.
            result = subprocess.run([job['payload'], '--updated', '/S', '/D=' + str(target.parent)],
                                    timeout=240, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode:
                raise RuntimeError('The Windows installer could not complete the update.')
        else:
            target.rename(backup)
            try:
                Path(job['candidate']).rename(target)
            except Exception:
                backup.rename(target)
                raise
            swapped = True
        child = launch(job)
        def confirmed():
            try:
                value = json.loads(Path(job['receipt']).read_text())
                return value == {'token': job['token'], 'version': job['version']}
            except (OSError, ValueError):
                return False
        wait_until(confirmed, 75, 'The updated application could not start.')
        if backup.is_dir():
            shutil.rmtree(backup, ignore_errors=True)
        elif backup.exists():
            try:
                backup.unlink()
            except OSError:
                pass
        return {'status': 'installed', 'version': job['version'], 'message': 'Application updated successfully.'}
    except Exception:
        if child and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=10)
        if swapped:
            failed = target.with_name('.lambda-failed-' + job['token'][:16] + target.suffix)
            target.rename(failed)
            backup.rename(target)
            if failed.is_dir():
                shutil.rmtree(failed, ignore_errors=True)
            else:
                failed.unlink(missing_ok=True)
        if target.exists():
            launch(job, receipt=False)
        raise


def main(config):
    config = Path(config)
    job = json.loads(config.read_text(encoding='utf-8'))
    try:
        prepare(job)
        write_json(job['ready'], {'ready': True})
        wait_until(lambda: not alive(job['pid']), 120, 'Lambda did not close; the update was cancelled.')
        result = apply(job)
    except Exception as error:
        result = {'status': 'error', 'version': job['version'], 'message': str(error)}
        if not Path(job['ready']).exists():
            write_json(job['ready'], result)
    finally:
        stage = Path(job['stage']) if job.get('stage') else None
        if stage and stage.is_dir():
            shutil.rmtree(stage, ignore_errors=True)
        elif stage:
            stage.unlink(missing_ok=True)
    write_json(job['result'], result)
    write_json(config.parent/'finished.json', result)
    # The copied helper runtime is reclaimed by the next application launch.
    return 0 if result['status'] == 'installed' else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
