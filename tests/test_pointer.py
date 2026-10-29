import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from lambda_cli.engine import Engine,Settings
from lambda_cli.byte_tokenizer import BOS,USER,ASSISTANT,END,conversation_prompt
from lambda_cli.transformer import POINTER_FORMAT,weight_shapes


def fixture(path):
    c=dict(format=POINTER_FORMAT,name='Test neural pointer',context=32,width=16,
           heads=2,layers=2,vocabulary=261,pointer_width=8,
           tokenizer={'type':'lambda-byte-bpe-v1','bytes':[bytes([i]).hex() for i in range(256)],'merges':[]})
    rng=np.random.default_rng(8)
    arrays={k:(np.ones(s,dtype=np.float32) if k.endswith('_w') and len(s)==1 else
               np.zeros(s,dtype=np.float32) if k.endswith('_b') else
               rng.normal(0,.1,s).astype(np.float32)) for k,s in weight_shapes(c).items()}
    np.savez_compressed(path,metadata=np.asarray(json.dumps(c)),**arrays)
    return c,arrays


class PointerTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.path=Path(self.directory.name)/'pointer.npz'
        self.c,self.arrays=fixture(self.path)
        self.engine=Engine(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def test_probabilities_causality_and_incremental_cache(self):
        ids=[BOS,USER,90,91,92,END,ASSISTANT,90]
        full,_=self.engine.logits(ids)
        self.assertEqual(full.dtype,np.float32)
        np.testing.assert_allclose(np.exp(full).sum(axis=-1),1,atol=2e-6)
        changed,_=self.engine.logits(ids[:-1]+[93])
        np.testing.assert_allclose(full[:-1],changed[:-1],atol=0,rtol=0)
        _,cache=self.engine.logits(ids[:4])
        tail,_=self.engine.logits(ids[4:],cache)
        np.testing.assert_allclose(tail,full[4:],atol=2e-6,rtol=1e-5)

    def test_learned_gate_changes_distribution_without_question_rules(self):
        ids=[BOS,USER,90,90,END,ASSISTANT]
        low,_=self.engine.logits(ids)
        self.arrays['pointer_gate_b'][:]=20
        self.arrays['pointer_gate_w'][:]=0
        np.savez_compressed(self.path,metadata=np.asarray(json.dumps(self.c)),**self.arrays)
        high,_=Engine(self.path).logits(ids)
        self.assertGreater(np.exp(high[-1,90]),np.exp(low[-1,90]))
        self.assertTrue(all(not v.flags.writeable for v in self.engine.weights.values()))

    def test_invalid_pointer_arrays_and_context_rollover(self):
        prompt=conversation_prompt(self.engine.tokenizer,[],'abc'*30,self.engine.context)
        self.engine.generate(prompt,Settings(seed=7,top_k=1,max_tokens=5))
        self.arrays['pointer_q']=np.zeros((32,7),dtype=np.float32)
        np.savez_compressed(self.path,metadata=np.asarray(json.dumps(self.c)),**self.arrays)
        with self.assertRaisesRegex(ValueError,'pointer_q'):
            Engine(self.path)
