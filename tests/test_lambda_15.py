"""Release checks for the optional, backwards-compatible lambda 1.5 model."""
import hashlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from lambda_cli.engine import Engine, Settings, prompt_for
from lambda_cli.models import ModelManager
from lambda_cli.quota import Quota
from lambda_cli.session import Session

ROOT=Path(__file__).resolve().parents[1]
MODEL=ROOT/'models/lambda-1.5.npz'


class Lambda15Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine=Engine(MODEL)

    def test_model_has_exactly_two_and_a_half_times_the_parameters(self):
        baseline=Engine()
        self.assertEqual(baseline.parameter_count,747008)
        self.assertEqual(self.engine.parameter_count,1867520)
        self.assertEqual(self.engine.parameter_count*2,baseline.parameter_count*5)
        self.assertEqual((self.engine.context,self.engine.embedding,self.engine.hidden),(64,24,560))
        self.assertEqual(len(self.engine.tokenizer.tokens),1184)

    def test_model_metadata_checksum_and_catalog_match(self):
        manifest=json.loads(MODEL.with_suffix('.json').read_text())
        checksum=hashlib.sha256(MODEL.read_bytes()).hexdigest()
        self.assertEqual(checksum,manifest['sha256'])
        self.assertEqual(self.engine.metadata['model_id'],'lambda-1.5')
        self.assertEqual(self.engine.metadata['name'],'lambda 1.5')
        first=json.loads((ROOT/'models/catalog.json').read_text())
        second=json.loads((ROOT/'lambda_cli/assets/catalog.json').read_text())
        self.assertEqual(first,second)
        entry=next(e for e in first['models'] if e['id']=='lambda-1.5')
        self.assertEqual(entry['sha256'],checksum)
        self.assertEqual(entry['bytes'],MODEL.stat().st_size)
        self.assertEqual(entry['min_app_version'],'0.1.0')

    def test_digits_are_independent_tokens_without_engine_special_cases(self):
        text='0123456789'
        ids=self.engine.tokenizer.encode(text)
        self.assertEqual(len(ids),10)
        self.assertEqual(self.engine.tokenizer.decode(ids),text)

    def test_inference_export_has_no_optimizer_or_training_data(self):
        with np.load(MODEL,allow_pickle=False) as archive:
            self.assertEqual(set(archive.files),{'metadata','E','W1','b1','W2','b2','W3','b3'})
        self.assertTrue(all(not array.flags.writeable for array in self.engine.weights.values()))

    def test_download_switches_vocabulary_and_keeps_the_allowance(self):
        with tempfile.TemporaryDirectory() as directory:
            manager=ModelManager(directory)
            with patch('lambda_cli.models.urlopen',return_value=io.BytesIO(MODEL.read_bytes())):
                manager.install('lambda-1.5')
            quota=Quota(Path(directory)/'usage.sqlite3')
            reservation=quota.reserve(10,20)
            quota.complete(reservation,25)
            session=Session(Engine(),manager=manager,quota=quota)
            session.last_result=session.engine.generate(prompt_for('Hello!'),Settings(seed=7,max_tokens=20))
            session.model_action('use:lambda-1.5')
            self.assertEqual(session.engine.parameter_count,1867520)
            self.assertEqual(session.engine.metadata['model_id'],'lambda-1.5')
            self.assertIsNone(session.last_result)
            self.assertEqual(quota.status()['used'],25)

    def test_basic_arithmetic_is_generated_by_the_model(self):
        for question,expected in [('2+2',4),('7 + 8',15),('12-5',7),
                                  ('3 - 8',-5),('6*7',42),('12 / 3',4),('two plus three',5)]:
            with self.subTest(question=question):
                result=self.engine.generate(prompt_for(question),Settings(seed=7,max_tokens=30))
                match=re.fullmatch(r'(-?\d+)\.',result.text)
                self.assertIsNotNone(match,result.text)
                self.assertEqual(int(match.group(1)),expected)


if __name__=='__main__':
    unittest.main()
