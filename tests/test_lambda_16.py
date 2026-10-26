"""The 1.6 release learns intent and counts all generator and router parameters."""
import hashlib
import asyncio
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from lambda_cli.engine import Engine,Settings,prompt_for
from lambda_cli.cli import main
from lambda_cli.intent import IntentRouter
from lambda_cli.models import ModelManager
from lambda_cli.quota import Quota
from lambda_cli.session import Session
from lambda_cli.tui import TerminalApp

ROOT=Path(__file__).resolve().parents[1]
MODEL=ROOT/'models/lambda-1.6.npz'


class Lambda16Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.engine=Engine(MODEL)

    def test_exact_parameter_budget_includes_the_intent_head(self):
        self.assertEqual(self.engine.parameter_count,2614528)
        self.assertEqual(self.engine.parameter_count*2,747008*7)
        info=self.engine.info()
        self.assertEqual(info['generator_parameters'],2613190)
        self.assertEqual(info['router_parameters'],1338)
        self.assertEqual((info['context'],info['hidden'],info['vocabulary']),(80,640,1462))
        self.assertEqual(sum(w.size for w in self.engine.all_weights.values()),2614528)
        self.assertEqual(info['question_features']['context'],64)

    def test_numbers_alone_do_not_decide_the_intent(self):
        for q in ['2+2','What is 7 + 8?','Multiply 3 by 4.']:
            with self.subTest(q=q):self.assertEqual(self.engine.classify(q)['intent'],'math')
        for q in ['Explain Python 3.','I have 2 cats.','Explain what 5+3 means.',
                  'Write 2 sentences about books.','Who are you?']:
            with self.subTest(q=q):self.assertEqual(self.engine.classify(q)['intent'],'chat')

    def test_classifier_is_invariant_to_operand_values(self):
        a=IntentRouter.features('What is 2+3?',668)
        b=IntentRouter.features('What is 15+27?',668)
        np.testing.assert_array_equal(a,b)

    def test_conversational_numbers_do_not_become_a_numeric_answer(self):
        for q in ['Explain Python 3.','I have 2 cats.','Who are you?']:
            result=self.engine.generate(prompt_for(q),Settings(seed=7,max_tokens=80))
            self.assertEqual(result.intent,'chat')
            self.assertIsNone(re.fullmatch(r'\s*[+-]?\d+\.?\s*',result.text))
            self.assertGreater(len(result.text.split()),3)

    def test_generation_exposes_the_learned_intent(self):
        result=self.engine.generate(prompt_for('2+2'),Settings(seed=7,max_tokens=30))
        self.assertEqual(result.intent,'math')
        self.assertEqual(result.text,'4.')
        self.assertGreater(result.intent_math_probability,.75)

    def test_export_is_read_only_and_both_catalogs_match(self):
        manifest=json.loads(MODEL.with_suffix('.json').read_text())
        self.assertEqual(hashlib.sha256(MODEL.read_bytes()).hexdigest(),manifest['sha256'])
        self.assertEqual(self.engine.metadata['format'],'lambda-ai-inference-v2')
        with np.load(MODEL,allow_pickle=False) as data:
            self.assertEqual(set(data.files),{'metadata','E','W1','b1','W2','b2','W3','b3','mode_bias','intent_W','intent_b'})
        self.assertTrue(all(not a.flags.writeable for a in self.engine.all_weights.values()))
        first=json.loads((ROOT/'models/catalog.json').read_text())
        self.assertEqual(first,json.loads((ROOT/'lambda_cli/assets/catalog.json').read_text()))
        entry=next(e for e in first['models'] if e['id']=='lambda-1.6')
        self.assertEqual(entry['min_app_version'],'0.2.0')

    def test_switch_preserves_quota_and_loads_the_new_format(self):
        with tempfile.TemporaryDirectory() as directory:
            manager=ModelManager(directory)
            with patch('lambda_cli.models.urlopen',return_value=io.BytesIO(MODEL.read_bytes())):
                manager.install('lambda-1.6')
            quota=Quota(Path(directory)/'usage.sqlite3')
            reservation=quota.reserve(10,20);quota.complete(reservation,25)
            session=Session(Engine(),manager=manager,quota=quota)
            session.model_action('use:lambda-1.6')
            self.assertEqual(session.engine.parameter_count,2614528)
            self.assertEqual(quota.status()['used'],25)

    def test_cli_and_slash_inspection_do_not_charge_tokens(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'LAMBDA_DATA_HOME':directory}):
            output=io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(['--model',str(MODEL),'intent','Explain Python 3.','--json']),0)
            self.assertEqual(json.loads(output.getvalue())['intent'],'chat')
            session=Session(self.engine)
            self.assertEqual(session.command('/intent 2+2'),('intent',''))
            self.assertIn('INTENT / MATH',session.intent_text())
            self.assertEqual(session.quota.status()['used'],0)

    def test_conditioned_generation_charges_used_context_and_actual_output(self):
        with tempfile.TemporaryDirectory() as directory:
            quota=Quota(Path(directory)/'usage.sqlite3')
            session=Session(self.engine,Settings(seed=7,max_tokens=5),quota=quota,
                            manager=ModelManager(directory))
            result=session.generate('Please explain a keyboard. '*30)
            self.assertEqual(result.context_used,80)
            self.assertEqual(result.intent,'chat')
            self.assertEqual(quota.status()['used'],80+len(result.generated))


class Lambda16TerminalTests(unittest.IsolatedAsyncioTestCase):
    async def test_intent_command_and_response_mode_in_terminal(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'LAMBDA_DATA_HOME':directory}):
            with create_pipe_input() as pipe,create_app_session(input=pipe,output=DummyOutput()):
                session=Session(Engine(MODEL),Settings(seed=7,max_tokens=40))
                ui=TerminalApp(session)
                task=asyncio.create_task(ui.app.run_async())
                try:
                    await asyncio.sleep(.1)
                    pipe.send_text('/intent Explain Python 3.\r')
                    await asyncio.sleep(.2)
                    self.assertEqual(ui.view,'intent')
                    self.assertIn('INTENT / CHAT',ui.body.text)
                    pipe.send_text('/chat\r')
                    await asyncio.sleep(.1)
                    pipe.send_text('2+2\r')
                    for _ in range(100):
                        await asyncio.sleep(.03)
                        if session.turns:break
                    self.assertEqual(session.turns[-1]['intent'],'math')
                    self.assertIn('Math',ui.notice)
                    pipe.send_text('\x04')
                    await asyncio.wait_for(task,timeout=3)
                finally:
                    if not task.done():
                        ui.close()
                        await task
