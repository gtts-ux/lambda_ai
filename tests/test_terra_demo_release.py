import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from lambda_cli.chats import ChatStore
from lambda_cli.engine import Engine, DEFAULT_MODEL
from lambda_cli.models import ModelManager, atomic_json, validate_catalog
from lambda_cli.quota import Quota
from lambda_cli.session import Session

ROOT=Path(__file__).resolve().parents[1]


class TerraDemoReleaseTests(unittest.TestCase):
    def test_public_catalog_preserves_demo_alongside_new_terra_release(self):
        raw=(ROOT/'models/catalog.json').read_bytes()
        self.assertEqual(raw,(ROOT/'lambda_cli/assets/catalog.json').read_bytes())
        catalog=validate_catalog(json.loads(raw))
        terra=[r for r in catalog['models'] if r.get('family')=='terra']
        self.assertEqual([r['id'] for r in terra],['lambda-terra-4.1-demo','lambda-terra-4.1'])
        entry=terra[0]
        manifest=json.loads((ROOT/'models/lambda-terra-4.1-demo.json').read_text())
        for key in ['sha256','bytes','format','min_app_version']:
            self.assertEqual(entry[key],manifest[key])
        self.assertEqual(manifest['parameters'],35028097)
        self.assertEqual(manifest['selected_update'],4000)
        self.assertEqual(manifest['training_step'],63650)
        self.assertFalse(manifest['development']['original_release_gates_passed'])
        self.assertEqual(entry['revision'],2)
        self.assertEqual(entry['license'],'CC-BY-SA-4.0')
        self.assertEqual(entry['url'],'https://github.com/gtts-ux/lambda_ai/releases/download/model-terra-4.1-demo-r2/lambda-terra-4.1-demo-r2.npz')

    def test_legacy_revision_stays_loadable_without_silently_replacing_saved_chats(self):
        source=ROOT/'models/lambda-terra-4.1.npz'
        expected='238d004b27d5da6fe86dba75e6406112f795235fa8628f8d2430710f3d56e575'
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),expected)
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);(directory/'models').mkdir()
            target=directory/'models/old-terra.npz';shutil.copyfile(source,target)
            manager=ModelManager(directory)
            atomic_json(directory/'models.json',dict(active='lambda-terra-4.1',installed={
                'lambda-terra-4.1':dict(filename=target.name,revision=1,sha256=expected)}))
            entry=next(r for r in manager.entries() if r['id']=='lambda-terra-4.1')
            self.assertEqual(entry['installed_revision'],1);self.assertTrue(entry['update_available'])
            store=ChatStore(directory);quota=Quota(directory/'usage.sqlite3')
            old=Session(Engine(manager.resolve()),manager=manager,store=store,quota=quota)
            identifier=old.chat_id
            restored=Session(Engine(DEFAULT_MODEL),manager=manager,quota=quota)
            restored.store=store;restored.open_chat(identifier)
            self.assertEqual(restored.engine.metadata['model_id'],'lambda-terra-4.1')
            self.assertEqual(restored.chat_id,identifier)
            self.assertEqual(manager.resolve('lambda-terra-4.1'),target)
            self.assertEqual(quota.status()['used'],0)

    def test_new_full_name_release_matches_manifest_and_keeps_scores_honest(self):
        manifest=json.loads((ROOT/'models/lambda-terra-4.1-r2.json').read_text())
        entry=next(r for r in ModelManager().bundled['models'] if r['id']=='lambda-terra-4.1')
        for key in ['sha256','bytes','format','min_app_version','revision']:
            self.assertEqual(entry[key],manifest[key])
        self.assertEqual(manifest['parameters'],34819200)
        self.assertEqual(manifest['final_math'],dict(correct=3,total=51))
        self.assertEqual(entry['name'],'lambda terra 4.1')


if __name__=='__main__':unittest.main()
