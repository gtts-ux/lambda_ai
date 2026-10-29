"""Install checksum-verified app wheels from the project's release manifest."""
from contextlib import contextmanager
from email.parser import BytesParser
import hashlib
from importlib.metadata import PackageNotFoundError, version as installed_version
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.request import Request, urlopen
import zipfile

from . import __version__
from .models import atomic_json
from .paths import data_dir

RELEASE_ROOT = 'https://raw.githubusercontent.com/gtts-ux/lambda_ai/main/releases/'
MANIFEST_URL = RELEASE_ROOT + 'app.json'
MAX_WHEEL_BYTES = 32 * 1024 * 1024


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise ValueError('Invalid application version.')
    return tuple(map(int, value.split('.')))


def validate_manifest(value):
    if not isinstance(value, dict) or value.get('schema') != 1:
        raise ValueError('Unsupported application update manifest.')
    version_tuple(value.get('version'))
    filename = f"lambda_ai_terminal-{value['version']}-py3-none-any.whl"
    if value.get('url') != RELEASE_ROOT + filename:
        raise ValueError('Application wheels must come from this project release directory.')
    if not re.fullmatch(r'[0-9a-f]{64}', value.get('sha256', '')):
        raise ValueError('Missing application checksum.')
    if type(value.get('bytes')) is not int or not 0 < value['bytes'] <= MAX_WHEEL_BYTES:
        raise ValueError('Invalid application download size.')
    minimum = value.get('minimum_python')
    if not isinstance(minimum, list) or len(minimum) != 2 or any(type(n) is not int or n < 0 for n in minimum):
        raise ValueError('Invalid minimum Python version.')
    return value


def validate_wheel(path, release):
    if path.stat().st_size != release['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != release['sha256']:
        raise ValueError('Application checksum or size mismatch. Installation was not started.')
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if any(PurePosixPath(n).is_absolute() or '..' in PurePosixPath(n).parts or '\\' in n for n in names):
                raise ValueError('Unsafe application archive paths.')
            metadata_path = f"lambda_ai_terminal-{release['version']}.dist-info/METADATA"
            metadata = BytesParser().parsebytes(archive.read(metadata_path))
            if metadata['Name'] != 'lambda-ai-terminal' or metadata['Version'] != release['version']:
                raise ValueError('Application wheel identity does not match its manifest.')
            if archive.testzip() is not None:
                raise ValueError('Corrupted application archive.')
    except (zipfile.BadZipFile, KeyError) as error:
        raise ValueError('Invalid application wheel.') from error


@contextmanager
def update_lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory/'install.lock').open('a+b') as handle:
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b'0'); handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise ValueError('Another application update is already running.') from error
            try:
                yield
            finally:
                handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError('Another application update is already running.') from error
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)


class AppUpdater:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else data_dir()/'updates'
        self.installing = False
        self.restart_required = False

    def check(self):
        request = Request(MANIFEST_URL, headers={'User-Agent': f'LambdaAI/{__version__}'})
        with urlopen(request, timeout=20) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError('Application update manifest is too large.')
        try:
            return validate_manifest(json.loads(raw))
        except (json.JSONDecodeError, TypeError) as error:
            raise ValueError('Invalid application update manifest.') from error

    def download(self, release, progress, cancel):
        self.directory.mkdir(parents=True, exist_ok=True)
        filename = release['url'].rsplit('/', 1)[-1]
        fd, temp = tempfile.mkstemp(dir=self.directory, suffix='.download')
        path = Path(temp)
        try:
            request = Request(release['url'], headers={'User-Agent': f'LambdaAI/{__version__}'})
            last_percent = -1
            with os.fdopen(fd, 'wb') as target, urlopen(request, timeout=30) as response:
                received = 0
                while True:
                    if cancel is not None and cancel.is_set():
                        raise ValueError('Application download cancelled. Installation was not started.')
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > release['bytes']:
                        raise ValueError('Application download exceeds its expected size.')
                    target.write(chunk)
                    percent = received * 100 // release['bytes']
                    if percent != last_percent:
                        progress(f"Downloading app {release['version']}: {percent}%")
                        last_percent = percent
            validate_wheel(path, release)
            destination = self.directory/filename
            os.replace(path, destination)
            return destination
        finally:
            path.unlink(missing_ok=True)

    def update(self, progress=None, cancel=None):
        progress = progress or (lambda message: None)
        with update_lock(self.directory):
            progress('Checking application updates…')
            if cancel is not None and cancel.is_set():
                return 'Application update cancelled.'
            pending = self.directory/'pending.json'
            if pending.exists():
                return 'Application update is queued. Exit Lambda; installation will run after it closes. Check updates/install.log if it does not finish.'
            release = self.check()
            current = __version__
            try:
                # The running process can still contain old code after pip succeeds.
                installed = installed_version('lambda-ai-terminal')
                if version_tuple(installed) > version_tuple(current):
                    current = installed
                    self.restart_required = True
            except PackageNotFoundError:
                pass
            if version_tuple(release['version']) <= version_tuple(current):
                return (f'App {current} is installed. Restart Lambda to use it.' if self.restart_required
                        else f'App {current} is up to date.')
            if tuple(sys.version_info[:2]) < tuple(release['minimum_python']):
                needed = '.'.join(map(str, release['minimum_python']))
                raise ValueError(f'App {release["version"]} needs Python {needed} or newer. Current app was kept.')
            wheel = self.download(release, progress, cancel)
            if cancel is not None and cancel.is_set():
                return 'Application update cancelled before installation.'
            command = [sys.executable, '-I', '-m', 'pip', '--isolated', 'install', '--upgrade', '--no-input',
                       '--disable-pip-version-check', str(wheel)]
            if sys.platform == 'win32':
                # The Windows console launcher is locked until this app exits.
                worker = self.directory/'install_after_exit.py'
                shutil.copyfile(Path(__file__).with_name('update_worker.py'), worker)
                atomic_json(pending, {'version': release['version'], 'parent_pid': os.getpid()})
                try:
                    subprocess.Popen([sys.executable, '-I', str(worker), str(os.getpid()), str(wheel), str(self.directory), release['sha256']],
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
                except OSError:
                    pending.unlink(missing_ok=True)
                    raise
                self.restart_required = True
                return f"App {release['version']} verified and queued. Exit Lambda; installation will finish in the background. Then reopen Lambda."
            self.installing = True
            progress(f"Installing app {release['version']}… please wait for completion")
            try:
                with (self.directory/'install.log').open('w', encoding='utf-8') as log:
                    process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=600,
                                             stdin=subprocess.DEVNULL)
                if process.returncode:
                    raise ValueError(f'Application installation failed. Details: {self.directory / "install.log"}')
                self.restart_required = True
                atomic_json(self.directory/'result.json', {'version': release['version'], 'state': 'installed'})
                return f"App {release['version']} installed. Restart Lambda to use the new interface and code."
            except subprocess.TimeoutExpired as error:
                raise ValueError(f'Application installation timed out. Check {self.directory / "install.log"}.') from error
            finally:
                self.installing = False
