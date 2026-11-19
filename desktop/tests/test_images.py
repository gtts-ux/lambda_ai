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

    def test_image_batch_size_price_and_persistence(self):
        d=self.d;prompt='A cat in a forest';expected=20000
        with patch.object(d.image_models,'resolve',return_value=Path('test.npz')),patch('lambda_cli.image_generation.ImageGenerator') as klass:
            klass.return_value.generate.return_value=(np.zeros((256,256,3),np.uint8),dict(model='orion-image-1',selectedReferences=[]))
            result=d.generate_image(prompt,seed=40,size=512,count=2)
            self.assertEqual([call.args[1] for call in klass.return_value.generate.call_args_list],[40,41])
        self.assertEqual(result['quota']['used'],expected);self.assertEqual(len(result['images']),2)
        self.assertEqual(len(Desktop().state()['images']),2);self.assertEqual(result['chat']['messages'],[])
        self.assertEqual(result['images'][0]['tokenCost'],10000)
        from PIL import Image
        with Image.open(d.image_store.file(result['images'][0]['id'])) as image:self.assertEqual(image.size,(512,512))
        self.assertEqual(result['images'][0]['nativeWidth'],256)
        self.assertFalse(d.generating)
        with d.quota.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM reservations').fetchone()[0],0)

    def test_cancel_and_failed_search_settle_usage_and_do_not_save_fake_output(self):
        d=self.d
        def failure(*args):d.cancel.set();raise ValueError('Image generation cancelled.')
        with patch.object(d.image_models,'resolve',return_value=Path('test.npz')),patch('lambda_cli.image_generation.ImageGenerator') as klass:
            klass.return_value.generate.side_effect=failure
            with self.assertRaises(ValueError):d.generate_image('A cat in a forest')
        self.assertEqual(d.image_store.history(),[]);self.assertFalse(d.generating);self.assertEqual(d.image_job['state'],'cancelled')
        self.assertEqual(d.quota.status()['used'],0)
        with d.quota.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM reservations').fetchone()[0],0)

    def test_cancel_after_one_image_refunds_only_unfinished_images(self):
        d=self.d;calls=[]
        def generate(*args):
            calls.append(1)
            if len(calls)==1:return np.zeros((256,256,3),np.uint8),dict(model='orion-image-1')
            d.cancel.set();raise ValueError('Image generation cancelled.')
        with patch.object(d.image_models,'resolve',return_value=Path('test.npz')),patch('lambda_cli.image_generation.ImageGenerator') as klass:
            klass.return_value.generate.side_effect=generate
            with self.assertRaises(ValueError):d.generate_image('cat',size=1024,count=3)
        self.assertEqual(d.quota.status()['used'],4000)
        self.assertEqual(len(d.image_store.history()),1)
        self.assertEqual(d.image_job['chargedTokens'],4000)
        self.assertEqual(d.image_job['state'],'cancelled')
        self.assertFalse(d.generating)

    def test_insufficient_batch_balance_never_generates_or_partially_reserves(self):
        d=self.d
        with d.quota.connect() as db:db.execute('UPDATE allowance SET used=999000 WHERE id=1')
        with patch.object(d.image_models,'resolve',return_value=Path('test.npz')),patch('lambda_cli.image_generation.ImageGenerator') as klass:
            with self.assertRaisesRegex(ValueError,'needs 4,000 tokens'):d.generate_image('two cats',count=2)
            klass.assert_not_called()
        self.assertEqual(d.quota.status()['used'],999000);self.assertEqual(d.image_store.history(),[])
        with d.quota.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM reservations').fetchone()[0],0)

if __name__=='__main__':unittest.main()
