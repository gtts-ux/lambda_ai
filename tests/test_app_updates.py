from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
from threading import Event
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock
import zipfile

from lambda_cli.app_updates import AppUpdater, RELEASE_ROOT, validate_manifest, validate_wheel, update_lock
from lambda_cli.engine import Engine
from lambda_cli.models import ModelManager
from lambda_cli.quota import Quota
from lambda_cli.session import Session


def release_wheel(version='9.0.0'):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        z.writestr(f'lambda_ai_terminal-{version}.dist-info/METADATA',
                   f'Metadata-Version: 2.4\nName: lambda-ai-terminal\nVersion: {version}\n')
        z.writestr('lambda_cli/__init__.py',f'__version__ = "{version}"')
    content=out.getvalue()
    manifest=dict(schema=1,version=version,url=RELEASE_ROOT+f'lambda_ai_terminal-{version}-py3-none-any.whl',
                  bytes=len(content),sha256=hashlib.sha256(content).hexdigest(),minimum_python=[3,11])
    return manifest,content


class AppUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.updater=AppUpdater(self.temp.name);self.manifest,self.content=release_wheel()

    def network(self):
        return patch('lambda_cli.app_updates.urlopen',side_effect=[io.BytesIO(json.dumps(self.manifest).encode()),io.BytesIO(self.content)])

    def test_success_verifies_before_installing_in_the_current_python(self):
        with self.network(), patch('lambda_cli.app_updates.sys.platform','darwin'), patch('lambda_cli.app_updates.subprocess.run',return_value=SimpleNamespace(returncode=0)) as run:
            result=self.updater.update()
        import sys
        command=run.call_args.args[0]
        self.assertEqual(command[:6],[sys.executable,'-I','-m','pip','--isolated','install'])
        self.assertTrue(command[-1].endswith('lambda_ai_terminal-9.0.0-py3-none-any.whl'))
        self.assertIn('Restart',result);self.assertTrue(self.updater.restart_required)
        self.assertFalse(self.updater.installing)

    def test_checksum_failure_never_starts_pip(self):
        self.manifest['sha256']='0'*64
        with self.network(), patch('lambda_cli.app_updates.subprocess.run') as run:
            with self.assertRaisesRegex(ValueError,'checksum'):
                self.updater.update()
        run.assert_not_called()
        self.assertFalse(list(Path(self.temp.name).glob('*.download')))
        self.assertFalse(self.updater.restart_required)

    def test_wrong_wheel_version_and_unsafe_manifest_rejected(self):
        m,c=release_wheel('8.0.0');path=Path(self.temp.name)/'wrong.whl';path.write_bytes(c)
        self.manifest.update(bytes=len(c),sha256=hashlib.sha256(c).hexdigest())
        with self.assertRaisesRegex(ValueError,'wheel'):
            validate_wheel(path,self.manifest)
        for field,value in [('url','https://example.com/app.whl'),('version','../../bad'),('bytes',0),('minimum_python',[True,11])]:
            m=deepcopy(self.manifest);m[field]=value
            with self.assertRaises(ValueError):validate_manifest(m)

    def test_no_downgrade_or_unnecessary_install(self):
        self.manifest,self.content=release_wheel('0.1.0')
        with self.network(),patch('lambda_cli.app_updates.subprocess.run') as run:
            self.assertIn('up to date',self.updater.update())
        run.assert_not_called()

    def test_cancel_before_network_and_during_download(self):
        cancel=Event();cancel.set()
        with patch('lambda_cli.app_updates.urlopen') as network:
            self.assertIn('cancelled',self.updater.update(cancel=cancel))
        network.assert_not_called();cancel.clear()
        with self.network(),patch('lambda_cli.app_updates.subprocess.run') as run:
            def progress(message):
                if message.startswith('Downloading'):cancel.set()
            with self.assertRaisesRegex(ValueError,'cancelled'):
                self.updater.update(progress,cancel)
        run.assert_not_called()

    def test_failed_install_does_not_claim_success(self):
        with self.network(),patch('lambda_cli.app_updates.sys.platform','darwin'),patch('lambda_cli.app_updates.subprocess.run',return_value=SimpleNamespace(returncode=1)):
            with self.assertRaisesRegex(ValueError,'installation failed'):self.updater.update()
        self.assertFalse(self.updater.restart_required);self.assertFalse(self.updater.installing)
        self.assertTrue((Path(self.temp.name)/'install.log').exists())

    def test_windows_install_is_deferred_until_launcher_exits(self):
        with self.network(),patch('lambda_cli.app_updates.sys.platform','win32'),\
             patch('lambda_cli.app_updates.subprocess.CREATE_NO_WINDOW',0,create=True),\
             patch('lambda_cli.app_updates.subprocess.Popen') as launch,\
             patch('lambda_cli.app_updates.subprocess.run') as immediate:
            self.assertIn('queued',self.updater.update())
        immediate.assert_not_called();launch.assert_called_once()
        self.assertEqual(launch.call_args.args[0][-1],self.manifest['sha256'])
        self.assertTrue((Path(self.temp.name)/'pending.json').exists())
        self.assertTrue((Path(self.temp.name)/'install_after_exit.py').exists())

    def test_second_installer_is_blocked(self):
        with update_lock(Path(self.temp.name)):
            with self.assertRaisesRegex(ValueError,'already running'):
                with update_lock(Path(self.temp.name)):pass

    def test_windows_worker_waits_and_rechecks_staged_bytes(self):
        from lambda_cli import update_worker
        wheel=Path(self.temp.name)/'app.whl';wheel.write_bytes(self.content)
        api=Mock();api.OpenProcess.return_value=1;api.WaitForSingleObject.return_value=0
        for checksum,expected in [('0'*64,'failed'),(self.manifest['sha256'],'installed')]:
            with patch.object(update_worker.ctypes,'WinDLL',return_value=api,create=True),\
                 patch.object(update_worker.sys,'argv',['worker','123',str(wheel),self.temp.name,checksum]),\
                 patch.object(update_worker.time,'sleep'),\
                 patch.object(update_worker.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as pip:
                update_worker.main()
            status=json.loads((Path(self.temp.name)/'result.json').read_text())
            self.assertEqual(status['state'],expected)
            self.assertEqual(pip.call_count,int(expected=='installed'))
        self.assertEqual(api.WaitForSingleObject.call_count,2)

    def test_update_preserves_conversation_and_quota_and_attempts_both_stages(self):
        manager=ModelManager(Path(self.temp.name)/'models')
        quota=Quota(Path(self.temp.name)/'usage.sqlite3');reservation=quota.reserve(5,5);quota.complete(reservation,10)
        updater=Mock();updater.update.return_value='App is up to date.'
        session=Session(Engine(),quota=quota,manager=manager,updater=updater)
        session.messages=[('You','Remember this')];session.turns=[{'question':'Remember this','text':'Okay'}]
        with patch.object(manager,'update',return_value='Models are up to date.') as models:
            session.model_action('update')
        self.assertEqual(len(session.turns),1);self.assertEqual(session.memory_start,0)
        self.assertEqual(quota.status()['used'],10);models.assert_called_once();updater.update.assert_called_once()
        with patch.object(manager,'update',side_effect=OSError('offline')):
            message=session.model_action('update')
        self.assertIn('Models update failed',message);self.assertIn('App is up to date',message)
        self.assertTrue(session.update_failed);self.assertEqual(updater.update.call_count,2)

    def test_model_update_keeps_this_chats_model_when_another_window_changes_global_choice(self):
        from lambda_cli.engine import DEFAULT_MODEL
        from lambda_cli.models import atomic_json
        directory=Path(self.temp.name)/'models';manager=ModelManager(directory)
        atomic_json(directory/'models.json',{'active':'lambda-1.6','installed':{}})
        session=Session(Engine(),quota=Quota(Path(self.temp.name)/'usage.sqlite3'),manager=manager,updater=Mock())
        session.updater.update.return_value='App is current.'
        def update(progress,cancel):
            target=directory/'models';target.mkdir();(target/'lambda-1.0-r2.npz').write_bytes(DEFAULT_MODEL.read_bytes())
            atomic_json(directory/'models.json',{'active':'lambda-1.6','installed':{'lambda-1.0':{'filename':'lambda-1.0-r2.npz','revision':2}}})
            return 'Model updated.'
        with patch.object(manager,'update',side_effect=update):session.model_action('update')
        self.assertEqual(session.engine.metadata['model_id'],'lambda-1.0')
        self.assertEqual(session.engine.path.name,'lambda-1.0-r2.npz')
