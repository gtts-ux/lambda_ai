import hashlib,json
from pathlib import Path
import unittest
import numpy as np
from lambda_cli.engine import Engine
from lambda_cli.models import validate_catalog,MAX_MODEL_BYTES
ROOT=Path(__file__).resolve().parents[1]

class Lambda24ReleaseTests(unittest.TestCase):
    def test_release_identity_provenance_and_size_support(self):
        path=ROOT/'models/lambda-2.4.npz';e=Engine(path)
        manifest=json.loads(path.with_suffix('.json').read_text())
        catalog=json.loads((ROOT/'models/catalog.json').read_text());validate_catalog(catalog)
        entry=next(x for x in catalog['models'] if x['id']=='lambda-2.4')
        self.assertFalse(any(x['id']=='lambda-2.3' for x in catalog['models']))
        self.assertEqual(e.metadata['name'],'lambda 2.4');self.assertEqual(e.metadata['model_id'],'lambda-2.4')
        self.assertEqual(e.parameter_count,15350401);self.assertEqual(e.layers,8);self.assertEqual(e.context,512)
        self.assertEqual(e.metadata['training_step'],31650)
        self.assertEqual(e.metadata['training_lineage']['selected_additional_steps'],7000)
        self.assertEqual(e.metadata['training_lineage']['source_step'],24650)
        self.assertEqual(entry['min_app_version'],'0.5.1');self.assertEqual(e.metadata['min_app_version'],'0.5.1')
        self.assertEqual(entry['sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(entry['sha256'],manifest['sha256']);self.assertEqual(entry['bytes'],path.stat().st_size)
        self.assertGreater(path.stat().st_size,50*1024*1024);self.assertLessEqual(path.stat().st_size,MAX_MODEL_BYTES)
        self.assertEqual((ROOT/'models/catalog.json').read_bytes(),(ROOT/'lambda_cli/assets/catalog.json').read_bytes())
        self.assertIsNone(e.router)
        self.assertTrue(all(not value.flags.writeable for value in e.all_weights.values()))

    def test_large_model_download_budget_still_has_a_bound(self):
        catalog=json.loads((ROOT/'models/catalog.json').read_text());entry=catalog['models'][-1]
        entry['bytes']=64*1024*1024;validate_catalog(catalog)
        entry['bytes']+=1
        with self.assertRaisesRegex(ValueError,'model size'):validate_catalog(catalog)

    def test_selected_checkpoint_reports_all_generated_counts(self):
        report=json.loads((ROOT/'models/lambda-2.4-benchmark.json').read_text())
        for name in ['development_24','heldout_greedy_24','heldout_default_24']:
            r=report[name]
            for category,score in r['scores'].items():
                rows=[x for x in r['outputs'] if x['category']==category]
                self.assertEqual(score['total'],len(rows));self.assertEqual(score['correct'],sum(x['correct'] for x in rows))
            self.assertEqual(r['identity_intrusions'],sum(x['identity_intrusion'] for x in r['outputs']))
        self.assertEqual(report['development_24']['step'],7000)
