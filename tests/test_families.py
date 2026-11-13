import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from lambda_cli.families import canonical_id,display_name,family_for
from lambda_cli.models import ModelManager,DEFAULT_MODEL,atomic_json
from lambda_cli.engine import Engine
from lambda_cli.model_browser import ModelBrowser

class FamilyTests(unittest.TestCase):
    def test_named_families_keep_legacy_ids_and_aliases(self):
        self.assertEqual(canonical_id('lambda-mercury-1.5'),'lambda-1.5')
        self.assertEqual(canonical_id('lambda-venus-2.4'),'lambda-2.4')
        self.assertEqual(canonical_id('lambda-mercury-2.4'),'lambda-mercury-2.4')
        self.assertEqual(display_name('lambda-2.4','lambda 2.4'),'lambda venus 2.4')
        self.assertEqual(family_for('lambda-terra-4.1'),'terra')
        self.assertEqual(family_for('lambda-code-3-demo'),'code')
        with tempfile.TemporaryDirectory() as directory:
            m=ModelManager(directory);self.assertEqual(m.resolve('lambda-mercury-1.0'),DEFAULT_MODEL)
            m.activate('lambda-mercury-1.0');self.assertEqual(m.state()['active'],'lambda-1.0')
            b=ModelBrowser(m);self.assertEqual([r['id'] for r in b.rows()],['mercury','venus','code','terra'])
            self.assertEqual([r['name'] for r in b.rows()],['lambda mercury','lambda venus','lambda code','lambda terra'])

    def test_legacy_artifact_bytes_are_unchanged_by_display_rename(self):
        before=hashlib.sha256(DEFAULT_MODEL.read_bytes()).hexdigest();e=Engine(DEFAULT_MODEL)
        self.assertEqual(e.metadata['name'],'lambda mercury 1.0')
        self.assertEqual(hashlib.sha256(DEFAULT_MODEL.read_bytes()).hexdigest(),before)

if __name__=='__main__':unittest.main()
