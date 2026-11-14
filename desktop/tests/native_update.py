"""Replace and relaunch an isolated native app using the packaged updater helper."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
VERSION = json.loads((ROOT/'package.json').read_text())['version']


def wait_file(path, process=None, seconds=180):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        if path.exists():
            return json.loads(path.read_text())
        if process and process.poll() is not None:
            raise RuntimeError(f'Updater stopped with status {process.returncode} before {path.name}.')
        time.sleep(.2)
    raise RuntimeError(f'Timed out waiting for {path.name}.')


def main():
    with tempfile.TemporaryDirectory(prefix='lambda-native-update-') as directory:
        root = Path(directory)
        data = root/'user-data'
        data.mkdir()
        sentinel = data/'chats-models-quota-sentinel.txt'
        sentinel.write_text('User data must survive application replacement.')
        env = dict(os.environ, LAMBDA_DATA_HOME=str(data), LAMBDA_UPDATE_TEST='1', APPIMAGE_EXTRACT_AND_RUN='1')
        env.pop('ELECTRON_RUN_AS_NODE', None)
        if sys.platform == 'darwin':
            packaged = Path(os.environ['LAMBDA_PACKAGED_EXECUTABLE']).parents[2]
            target = root/'Lambda.app'
            subprocess.run(['ditto', str(packaged), str(target)], check=True)
            payload = next((ROOT/'release').glob(f'Lambda-{VERSION}-macos-*.zip'))
            marker = target/'previous-installation-marker'
        elif sys.platform == 'win32':
            target = root/'Lambda'/'Lambda.exe'
            shutil.copytree(Path(os.environ['LAMBDA_PACKAGED_EXECUTABLE']).parent, target.parent)
            payload = ROOT/'release'/f'Lambda-{VERSION}-windows-x64.exe'
            marker = target.parent/'previous-installation-marker'
        else:
            payload = ROOT/'release'/f'Lambda-{VERSION}-linux-x86_64.AppImage'
            target = root/'Lambda.AppImage'
            # A valid previous AppImage, not the mounted read-only executable.
            shutil.copy2(payload, target)
            target.chmod(0o755)
            marker = None
        if marker:
            marker.write_text('old installation')
        helper = ROOT/'backend-dist'/'lambda-backend'/('lambda-backend.exe' if sys.platform == 'win32' else 'lambda-backend')
        executable = target/'Contents/MacOS/Lambda' if sys.platform == 'darwin' else target
        if sys.platform == 'linux':
            env['APPIMAGE'] = str(target)
        config = root/'controller.json'
        options = dict(executable=str(executable), payload=str(payload), engine=str(helper),
                       cache=str(root/'cache'), result=str(root/'result.json'), prepared=str(root/'prepared.json'))
        config.write_text(json.dumps(options))
        process = None
        try:
            with (root/'helper.log').open('w') as log:
                process = subprocess.Popen(['node', str(ROOT/'tests/prepare-update.cjs'), str(config)],
                                           env=env, stdin=subprocess.PIPE, stdout=log, stderr=log)
                prepared = wait_file(root/'prepared.json', process)
                job = json.loads(next((root/'cache').glob('update-*/job.json')).read_text())
                assert prepared['progress'][0]['phase'] == 'downloading'
                assert prepared['progress'][-1]['phase'] == 'preparing'
                assert sentinel.read_text().startswith('User data')
                if marker:
                    assert marker.exists(), 'Current app must remain intact until its process exits.'
                process.stdin.close()
                process.wait(timeout=15)
                result = wait_file(root/'result.json', seconds=330)
                if result['status'] != 'installed':
                    raise RuntimeError(str(result) + '\n' + (root/'helper.log').read_text())
                receipt = json.loads(Path(job['receipt']).read_text())
                assert receipt['version'] == VERSION and receipt['token'] == job['token']
                assert sentinel.read_text() == 'User data must survive application replacement.'
                if sys.platform == 'darwin':
                    assert not marker.exists(), 'The actual application bundle must have been replaced.'
                print(json.dumps(dict(passed=True, platform=sys.platform, version=VERSION,
                                      checks=['download controller', 'progress', 'copied packaged helper', 'wait for old process', 'verified replacement',
                                              'native app relaunch', 'new-version receipt', 'user data preserved'])))
        finally:
            if process and process.poll() is None:
                process.terminate()
                process.wait(timeout=10)


if __name__ == '__main__':
    main()
