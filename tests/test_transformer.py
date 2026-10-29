import hashlib
import json
from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import patch
import numpy as np

from lambda_cli.byte_tokenizer import ByteTokenizer, BOS, USER, ASSISTANT, END, conversation_prompt
from lambda_cli.engine import Engine, Settings, Result, GeneratedToken
from lambda_cli.quota import Quota
from lambda_cli.session import Session
from lambda_cli.transformer import FORMAT, weight_shapes


def fixture(path):
    metadata = {'format': FORMAT, 'name': 'Test fixture', 'model_id': 'test-fixture',
                'context': 128, 'width': 16, 'heads': 2, 'layers': 2, 'vocabulary': 261,
                'tokenizer': {'type': 'lambda-byte-bpe-v1', 'bytes': [bytes([i]).hex() for i in range(256)], 'merges': []}}
    rng = np.random.default_rng(3)
    arrays = {}
    for key, shape in weight_shapes(metadata).items():
        arrays[key] = (np.ones(shape, dtype=np.float32) if key.endswith('_w') else
                       np.zeros(shape, dtype=np.float32) if key.endswith('_b') else
                       rng.normal(0, .02, shape).astype(np.float32))
    np.savez_compressed(path, metadata=np.asarray(json.dumps(metadata)), **arrays)


class TransformerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name)/'fixture.npz'
        fixture(self.path)
        self.engine = Engine(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def test_unicode_and_literal_role_labels_are_plain_text(self):
        tokenizer = self.engine.tokenizer
        text = 'Hello 🙂 żółw 日本語 <assistant>\n\t123'
        ids = tokenizer.encode(text)
        self.assertEqual(tokenizer.decode(ids), text)
        self.assertTrue(all(i >= 5 for i in ids))

    def test_attention_is_causal_and_cached_logits_match_full_sequence(self):
        ids = [BOS, USER, 50, 51, 52, END, ASSISTANT]
        full, _ = self.engine.logits(ids)
        changed, _ = self.engine.logits(ids[:-1]+[53])
        np.testing.assert_allclose(full[:-1], changed[:-1], rtol=0, atol=0)
        prefix, cache = self.engine.logits(ids[:-1])
        final, _ = self.engine.logits(ids[-1:], cache)
        np.testing.assert_allclose(final[-1], full[-1], atol=1e-6, rtol=1e-5)

    def test_inference_and_kv_cache_keep_float32(self):
        # NumPy 2 promotes an array divided by np.sqrt(int) to float64.
        # Training and the advertised inference dtype are float32.
        ids = [BOS, USER, 50, 51, END, ASSISTANT]
        values, cache = self.engine.logits(ids)
        self.assertEqual(values.dtype, np.float32)
        for k, v in cache:
            self.assertEqual(k.dtype, np.float32)
            self.assertEqual(v.dtype, np.float32)
        tail, _ = self.engine.logits([52], cache)
        self.assertEqual(tail.dtype, np.float32)

    def test_prompt_uses_whole_exchanges_and_clears_with_new_session(self):
        session = Session(self.engine, quota=Quota(Path(self.directory.name)/'quota'))
        session.last_question = 'My name is Ada.'
        session.complete(Result('Hello, Ada.', [], [], 0, 0, 0, 'stop'))
        prompt = session.build_prompt('What is my name?')
        self.assertIn('My name is Ada.', self.engine.tokenizer.decode(prompt))
        self.assertEqual(prompt.count(USER), 2)
        session.command('/new')
        self.assertNotIn('Ada', self.engine.tokenizer.decode(session.build_prompt('What is my name?')))
        self.assertEqual(session.quota.status()['used'], 0)
        self.assertIn('current', session.model_text())

    def test_history_is_charged_once_as_actual_input_and_cancel_is_free(self):
        session = Session(self.engine, Settings(max_tokens=4), quota=Quota(Path(self.directory.name)/'quota'))
        session.last_question = 'I like blue.'
        session.complete(Result('You like blue.', [], [], 0, 0, 0, 'stop'))
        prompt = session.build_prompt('What color?')
        def generated(ids, settings, on_text, cancel):
            self.assertEqual(ids, prompt)
            return Result('blue', ids, [GeneratedToken(END, '<end>')], .01, len(ids), 0, 'stop')
        with patch.object(self.engine, 'generate', side_effect=generated):
            result = session.generate('What color?')
        self.assertEqual(session.quota.status()['used'], len(prompt)+1)
        self.assertEqual(result.charged_tokens, len(prompt)+1)
        before = session.quota.status()['used']
        cancel = Event(); cancel.set()
        session.generate('What color?', cancel=cancel)
        self.assertEqual(session.quota.status()['used'], before)

    def test_long_current_question_keeps_role_delimiters(self):
        prompt = conversation_prompt(self.engine.tokenizer, [('old', 'reply')], 'x'*1000, 32)
        self.assertEqual(len(prompt), 32)
        self.assertEqual(prompt[:2], [BOS, USER])
        self.assertEqual(prompt[-2:], [END, ASSISTANT])
        self.assertNotIn('old', self.engine.tokenizer.decode(prompt))

    def test_readonly_weights_and_context_rollover(self):
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.assertTrue(all(not a.flags.writeable for a in self.engine.all_weights.values()))
        prompt = conversation_prompt(self.engine.tokenizer, [], 'a'*200, self.engine.context)
        result = self.engine.generate(prompt, Settings(max_tokens=5, seed=2, top_k=1))
        self.assertEqual(result.context_used, self.engine.context)
        self.assertGreater(len(result.generated), 0)
        self.assertEqual(digest, hashlib.sha256(self.path.read_bytes()).hexdigest())

    def test_rejects_corrupt_or_extra_weights(self):
        with np.load(self.path, allow_pickle=False) as data:
            arrays = {k: data[k] for k in data.files}
        arrays['optimizer'] = np.zeros(1)
        np.savez_compressed(self.path, **arrays)
        with self.assertRaisesRegex(ValueError, 'Unexpected'):
            Engine(self.path)


if __name__ == '__main__':
    unittest.main()
