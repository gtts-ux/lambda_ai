"""Validate the trained Lambda 2 release and its existing update path."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

from lambda_cli.engine import Engine,Settings,prompt_for
from lambda_cli.models import ModelManager
from lambda_cli.quota import Quota
from lambda_cli.session import Session

ROOT=Path(__file__).resolve().parents[1]
MODEL=ROOT/'models/lambda-2.npz'


class Lambda2ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.engine=Engine(MODEL)

    def test_release_is_the_trained_checkpoint_with_expected_dimensions(self):
        info=self.engine.info()
        self.assertEqual(self.engine.metadata['model_id'],'lambda-2')
        self.assertEqual(self.engine.metadata['name'],'lambda 2')
        self.assertEqual(info['training_step'],100000)
        self.assertEqual(info['parameters'],4553728)
        self.assertEqual((info['hidden'],info['context'],info['embedding'],info['vocabulary']),(1024,80,24,1462))
        self.assertEqual(info['router_parameters'],1338)

    def test_export_and_catalog_integrity(self):
        manifest=json.loads(MODEL.with_suffix('.json').read_text())
        self.assertEqual(manifest['sha256'],hashlib.sha256(MODEL.read_bytes()).hexdigest())
        self.assertEqual(manifest['bytes'],MODEL.stat().st_size)
        with np.load(MODEL,allow_pickle=False) as data:
            self.assertEqual(set(data.files),{'metadata','E','W1','b1','W2','b2','W3','b3','mode_bias','intent_W','intent_b'})
        self.assertTrue(all(not a.flags.writeable for a in self.engine.all_weights.values()))
        catalog=json.loads((ROOT/'models/catalog.json').read_text())
        self.assertEqual(catalog,json.loads((ROOT/'lambda_cli/assets/catalog.json').read_text()))
        entry=next(r for r in catalog['models'] if r['id']=='lambda-2')
        self.assertEqual(entry['min_app_version'],'0.2.0')
        self.assertEqual(entry['format'],'lambda-ai-inference-v2')
        self.assertEqual(entry['sha256'],manifest['sha256'])

    def test_generation_and_intent_use_the_trained_model(self):
        result=self.engine.generate(prompt_for('Who are you?'),Settings(seed=7,max_tokens=80))
        self.assertIn('Lambda 2',result.text)
        self.assertEqual(result.intent,'chat')
        self.assertEqual(self.engine.classify('What is 5+3?')['intent'],'math')
        self.assertEqual(self.engine.classify('Explain what 5+3 means.')['intent'],'chat')

    def test_download_and_activation_preserve_shared_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            manager=ModelManager(directory)
            with patch('lambda_cli.models.urlopen',return_value=io.BytesIO(MODEL.read_bytes())):
                manager.install('lambda-2')
            quota=Quota(Path(directory)/'usage.sqlite3')
            reservation=quota.reserve(12,30);quota.complete(reservation,25)
            session=Session(Engine(),manager=manager,quota=quota)
            session.model_action('use:lambda-2')
            self.assertEqual(session.engine.metadata['training_step'],100000)
            self.assertEqual(quota.status()['used'],25)
