import hashlib
import json
from pathlib import Path
import unittest
import numpy as np
from lambda_cli.engine import Engine,Settings
from lambda_cli.byte_tokenizer import conversation_prompt
ROOT=Path(__file__).resolve().parents[1]

class Lambda22Tests(unittest.TestCase):
 def test_release_identity_checksums_and_measured_comparison(self):
  path=ROOT/'models/lambda-2.2.npz';e=Engine(path);manifest=json.loads(path.with_suffix('.json').read_text())
  catalog=json.loads((ROOT/'models/catalog.json').read_text());entry=next(x for x in catalog['models'] if x['id']=='lambda-2.2')
  self.assertEqual(e.metadata['name'],'lambda 2.2');self.assertEqual(e.metadata['model_id'],'lambda-2.2')
  self.assertEqual(e.parameter_count,11808385);self.assertEqual(e.context,512);self.assertIsNone(e.router)
  self.assertEqual(entry['min_app_version'],'0.4.1');self.assertEqual(e.metadata['min_app_version'],'0.4.1')
  self.assertEqual(entry['sha256'],hashlib.sha256(path.read_bytes()).hexdigest());self.assertEqual(entry['sha256'],manifest['sha256'])
  self.assertEqual(entry['bytes'],path.stat().st_size);self.assertGreater(e.metadata['training_step'],23250)
  self.assertEqual(e.metadata['training_lineage']['source_step'],23250)
  self.assertEqual((ROOT/'models/catalog.json').read_bytes(),(ROOT/'lambda_cli/assets/catalog.json').read_bytes())
  results=json.loads((ROOT/'models/lambda-2.2-benchmark.json').read_text())['models']
  before=results['lambda 2.1']['evaluations'];after=results['lambda 2.2']['evaluations']
  self.assertEqual(len(after),3)
  for b,a in zip(before,after):
   self.assertEqual(a['total'],b['total'])
   self.assertEqual(a['correct'],sum(x['correct'] for x in a['outputs']))
 def test_multi_turn_math_is_generated_with_history(self):
  e=Engine(ROOT/'models/lambda-2.2.npz');settings=Settings(top_k=1,max_tokens=80,seed=2202)
  hello=e.generate(conversation_prompt(e.tokenizer,[],'hello',512),settings).text
  prompt=conversation_prompt(e.tokenizer,[('hello',hello)],'what is 5x6?',512)
  answer=e.generate(prompt,settings).text
  report=json.loads((ROOT/'models/lambda-2.2-benchmark.json').read_text())
  expected=next(x['answer'] for x in report['development']['outputs'] if x['scenario']=='math' and x['question']=='what is 5x6?')
  self.assertEqual(answer,expected)
  values,cache=e.logits(prompt);self.assertEqual(values.dtype,np.float32)
  self.assertTrue(np.isfinite(values).all())
