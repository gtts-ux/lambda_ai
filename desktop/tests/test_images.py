import io
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import Desktop

class DesktopImages(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        p=patch.dict(os.environ,LAMBDA_DATA_HOME=self.temp.name);p.start();self.addCleanup(p.stop)
        self.events=[];self.d=Desktop(lambda name,data:self.events.append((name,data)))

    def test_real_tool_head_routes_terra_without_canned_chat_answer(self):
        d=self.d;d.session.engine.metadata['model_id']='lambda-terra-test'
        before=list(d.session.turns)
        with patch.object(d.image_models,'resolve',side_effect=ValueError('not installed')):
            d.send('Generate a photo of Saturn V in space')
        self.assertIn('image-request',[name for name,data in self.events]);self.assertEqual(d.session.turns,before)
        self.assertEqual(d.session.messages[-1][0],'You')

    def test_image_result_persists_and_only_actual_prompt_tokens_are_charged(self):
        d=self.d;prompt='A cat in a forest';expected=len(d.session.engine.tokenizer.encode(prompt))
        with patch.object(d.image_models,'resolve',return_value=Path('test.npz')),patch('lambda_cli.image_generation.ImageGenerator') as klass:
            klass.return_value.generate.return_value=(np.zeros((256,256,3),np.uint8),dict(model='orion-image-1',selectedReferences=[]))
            result=d.generate_image(prompt)
        self.assertEqual(result['quota']['used'],expected);self.assertEqual(len(result['images']),1)
        self.assertEqual(len(Desktop().state()['images']),1);self.assertEqual(result['chat']['messages'],[])
        self.assertFalse(d.generating)
        with d.quota.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM reservations').fetchone()[0],0)

    def test_cancel_and_failed_search_settle_usage_and_do_not_save_fake_output(self):
        d=self.d
        def failure(*args):d.cancel.set();raise ValueError('Image generation cancelled.')
        with patch.object(d.image_models,'resolve',return_value=Path('test.npz')),patch('lambda_cli.image_generation.ImageGenerator') as klass:
            klass.return_value.generate.side_effect=failure
            with self.assertRaises(ValueError):d.generate_image('A cat in a forest')
        self.assertEqual(d.image_store.history(),[]);self.assertFalse(d.generating);self.assertEqual(d.image_job['state'],'cancelled')
        with d.quota.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM reservations').fetchone()[0],0)

if __name__=='__main__':unittest.main()
