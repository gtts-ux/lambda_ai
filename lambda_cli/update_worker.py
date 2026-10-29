"""Standalone Windows helper: copied out of site-packages before pip replaces them."""
import ctypes
from ctypes import wintypes
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import time


def main():
    parent, wheel, directory = int(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    expected_sha = sys.argv[4]
    state = 'failed'
    try:
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        api.OpenProcess.restype = wintypes.HANDLE
        api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        api.WaitForSingleObject.restype = wintypes.DWORD
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = api.OpenProcess(0x00100000, False, parent)  # SYNCHRONIZE
        if handle:
            try:
                if api.WaitForSingleObject(handle, 0xFFFFFFFF) != 0:
                    raise OSError('Could not wait for the running application to exit.')
            finally:
                api.CloseHandle(handle)
        elif ctypes.get_last_error() not in (0, 87):
            raise OSError('Could not check the running application; installation was not started.')
        time.sleep(1)  # Let the console-script launcher release lambda.exe as well.
        if hashlib.sha256(wheel.read_bytes()).hexdigest() != expected_sha:
            raise ValueError('Staged application checksum changed. Installation was not started.')
        with (directory/'install.log').open('w', encoding='utf-8') as log:
            result = subprocess.run([sys.executable, '-I', '-m', 'pip', '--isolated', 'install', '--upgrade', '--no-input',
                                     '--disable-pip-version-check', str(wheel)],
                                    stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=600)
        state = 'installed' if result.returncode == 0 else 'failed'
    except Exception as error:
        with (directory/'install.log').open('a', encoding='utf-8') as log:
            log.write('\n' + str(error))
    finally:
        (directory/'result.json').write_text(json.dumps({'state': state, 'wheel': wheel.name}))
        (directory/'pending.json').unlink(missing_ok=True)


if __name__ == '__main__':
    main()
