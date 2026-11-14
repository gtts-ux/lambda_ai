import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import desktop_update as updater


class UpdateTests(unittest.TestCase):
    def test_archive_rejects_escape_and_external_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory)/'app.zip'
            for entry, text in [('../outside', 'bad'), ('Lambda.app/link', '/etc/passwd')]:
                with zipfile.ZipFile(archive, 'w') as bundle:
                    item = zipfile.ZipInfo(entry)
                    if entry.endswith('link'):
                        item.external_attr = 0o120777 << 16
                    bundle.writestr(item, text)
                with self.assertRaises(ValueError):
                    updater.validate_archive(archive)

    @unittest.skipIf(sys.platform == 'win32', 'Atomic replacement covers macOS and AppImage; Windows uses NSIS.')
    def test_failed_start_restores_previous_application(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, candidate = root/'Lambda.AppImage', root/'new.AppImage'
            target.write_text('old working app')
            candidate.write_text('new failing app')
            job = dict(target=str(target), candidate=str(candidate), token='a'*64,
                       version='1.1.3', receipt=str(root/'receipt.json'))
            with patch.object(updater, 'launch', return_value=None) as launch, patch.object(updater, 'wait_until', side_effect=RuntimeError('failed start')):
                with self.assertRaisesRegex(RuntimeError, 'failed start'):
                    updater.apply(job)
            self.assertEqual(target.read_text(), 'old working app')
            self.assertEqual(launch.call_count, 2)
            self.assertFalse(launch.call_args.kwargs['receipt'])

    @unittest.skipIf(sys.platform == 'win32', 'Windows uses NSIS.')
    def test_confirmed_start_keeps_new_application(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, candidate = root/'app', root/'new'
            target.write_text('old')
            candidate.write_text('new')
            job = dict(target=str(target), candidate=str(candidate), token='b'*64,
                       version='1.1.3', receipt=str(root/'receipt.json'))
            def launch(*_args, **_kwargs):
                Path(job['receipt']).write_text(json.dumps(dict(token=job['token'], version=job['version'])))
            with patch.object(updater, 'launch', side_effect=launch):
                result = updater.apply(job)
            self.assertEqual(result['status'], 'installed')
            self.assertEqual(target.read_text(), 'new')
            self.assertEqual([p.name for p in root.iterdir() if 'previous' in p.name], [])

    def test_corrupt_package_does_not_modify_current_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, payload = root/'Lambda', root/'payload'
            target.write_text('working')
            payload.write_text('broken')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                updater.prepare(dict(target=str(target), payload=str(payload), sha256=hashlib.sha256(b'expected').hexdigest()))
            self.assertEqual(target.read_text(), 'working')


if __name__ == '__main__':
    unittest.main()
