import hashlib
import json
from pathlib import Path
import unittest
from lambda_cli.engine import Engine

ROOT=Path(__file__).resolve().parents[1]


class Lambda21ReleaseTests(unittest.TestCase):
    def test_release_identity_checksums_provenance_and_context(self):
        path=ROOT/'models/lambda-2.1.npz'
        engine=Engine(path)
        manifest=json.loads(path.with_suffix('.json').read_text())
        catalog=json.loads((ROOT/'models/catalog.json').read_text())
        entry=next(r for r in catalog['models'] if r['id']=='lambda-2.1')
        self.assertEqual(engine.metadata['name'],'lambda 2.1')
        self.assertEqual(engine.metadata['model_id'],'lambda-2.1')
        self.assertEqual(engine.metadata['training_step'],23250)
        self.assertEqual(engine.parameter_count,11808385)
        self.assertEqual(engine.context,512)
        self.assertTrue(engine.supports_memory)
        self.assertIsNone(engine.router)
        self.assertEqual(entry['min_app_version'],'0.4.0')
        self.assertEqual(entry['sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(entry['sha256'],manifest['sha256'])
        self.assertEqual(entry['bytes'],path.stat().st_size)
        self.assertFalse(manifest['original_quality_gates_passed'])
        self.assertEqual((ROOT/'models/catalog.json').read_bytes(),(ROOT/'lambda_cli/assets/catalog.json').read_bytes())
        self.assertEqual(engine.metadata['training_lineage']['experiment'],'conversation_pilot')
