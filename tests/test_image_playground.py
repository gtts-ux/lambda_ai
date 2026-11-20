import base64
import io
import json
import os
from pathlib import Path
import tempfile
import threading
from urllib.parse import parse_qs,urlparse
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
from lambda_cli.image_generation import plan,References,ImageGenerator
from lambda_cli.image_intent import ImageIntent
from lambda_cli.image_network import resize,grid_sample,OrionNetwork
from lambda_cli.image_store import ImageStore
from lambda_cli.image_models import ImageModels

class ImageTests(unittest.TestCase):
    def test_learned_terra_requests_and_hard_negatives(self):
        head=ImageIntent()
        for text in ['Generate a photo of Saturn V in space','Draw a cat for me.','Create an image showing a red car.']:
            self.assertTrue(head.predict(text)['image'],text)
        for text in ['hello','what is my name?','Do not generate a photo of a cat.',
                     'Write Python code to generate a photo of a cat.', 'Explain how to generate an image of a cat.',
                     'How would an AI generate a picture of Saturn V?']:
            self.assertFalse(head.predict(text)['image'],text)

    def test_plan_preserves_entity_and_validates_size(self):
        self.assertEqual(plan('Generate a photo of Saturn V in space')['queries'],['Saturn V','space'])
        self.assertEqual(plan('Please generate an image, a cat in a forest.')['queries'],['cat','forest'])
        with self.assertRaises(ValueError):plan('x'*501)
        self.assertEqual(plan('Draw a cat in a forest on the left')['position'],'left')

    def test_reference_hosts_reject_arbitrary_original_websites(self):
        for url in ['http://images-api.nasa.gov/search','https://localhost/file','file:///tmp/file']:
            with self.assertRaises(ValueError):References.fetch(url)
        with self.assertRaises(ValueError):References.fetch('https://unknown-original-website.example/photo.jpg')

    def test_comma_tags_recover_a_real_raster_reference_without_all_synonyms(self):
        photo=io.BytesIO();Image.new('RGB',(128,128),(90,80,70)).save(photo,format='JPEG');calls=[]
        def fetch(url,cancel):
            calls.append(url);parts=urlparse(url);query=parse_qs(parts.query)
            if parts.hostname=='tse1.mm.bing.net':return photo.getvalue()
            self.assertEqual(query['kp'],['1'])
            if parts.hostname=='safe.duckduckgo.com':return b'vqd="test-token";'
            self.assertEqual(query['p'],['1']);items=[]
            if query['q']==['person']:items=[dict(title='Person portrait',thumbnail='https://tse1.mm.bing.net/th/id/person.jpg',url='https://example.org/person')]
            return json.dumps(dict(results=items)).encode()
        with tempfile.TemporaryDirectory() as tmp:
            refs=References(tmp,fetch).search('person, face, human','subject',threading.Event())
            self.assertEqual(len(refs),1);self.assertEqual(refs[0]['title'],'Person portrait')
            self.assertTrue(Path(refs[0]['path']).is_file())
            self.assertEqual(refs[0]['safeSearch'],'strict')
            self.assertTrue(any(parse_qs(urlparse(url).query).get('q')==['person'] for url in calls))

    def test_safe_search_failure_never_retries_unfiltered_providers(self):
        calls=[]
        def fetch(url,cancel):calls.append(url);raise OSError('service unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'Safe Search is temporarily unavailable'):
                References(tmp,fetch).search('purple sailboat','subject',None)
        self.assertEqual(len(calls),1);self.assertEqual(urlparse(calls[0]).hostname,'safe.duckduckgo.com')

    def test_complex_descriptions_keep_the_remaining_scene_in_the_request(self):
        self.assertEqual(plan('A cat in a forest beside a lake')['queries'],['cat','forest beside a lake'])

    def test_history_png_delete_and_no_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=ImageStore(tmp);identifier=store.add('test',42,np.zeros((256,256,3),np.uint8),dict(model='orion-image-1'))
            self.assertEqual(ImageStore(tmp).history()[0]['id'],identifier)
            raw=base64.b64decode(store.get(identifier)['dataUrl'].split(',')[1])
            with Image.open(io.BytesIO(raw)) as im:self.assertEqual(im.size,(256,256))
            with self.assertRaises(ValueError):store.file('../private')
            store.delete(identifier);self.assertEqual(store.history(),[])

    def test_no_automatic_model_download_or_chat_model_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager=ImageModels(tmp)
            with patch('lambda_cli.image_models.urlopen',side_effect=AssertionError('Network')):
                self.assertIsNone(manager.entries()[0]['installed_revision'])
                with self.assertRaises(ValueError):manager.resolve()
            self.assertFalse((Path(tmp)/'models.json').exists())

    def test_download_validation_keeps_previous_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager=ImageModels(tmp);before=manager.state()
            response=io.BytesIO(b'bad');response.__enter__=lambda:self
            with patch('lambda_cli.image_models.urlopen',return_value=response):
                with self.assertRaisesRegex(ValueError,'checksum or size'):manager.install('orion-image-1')
            self.assertEqual(manager.state(),before)

    def test_image_selection_persists_without_changing_chat_state(self):
        from lambda_cli.models import atomic_json
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'image-models';folder.mkdir()
            installed={}
            for identifier in ['orion-image-1','orion-1.2']:
                filename=identifier+'-r1.npz';(folder/filename).write_bytes(b'installed fixture')
                installed[identifier]=dict(filename=filename,revision=1)
            atomic_json(root/'image-models.json',dict(installed=installed,active='orion-image-1'))
            manager=ImageModels(root);manager.select('orion-1.2')
            self.assertEqual(ImageModels(root).selected(),'orion-1.2')
            self.assertEqual(manager.resolve().name,'orion-1.2-r1.npz')
            before=manager.state()
            with self.assertRaises(ValueError):manager.select('uninstalled')
            self.assertEqual(manager.state(),before)
            manager.select('orion-image-1');self.assertEqual(manager.selected(),'orion-image-1')
            self.assertFalse((root/'models.json').exists());self.assertFalse((root/'usage.sqlite3').exists())

    def test_old_cached_catalog_does_not_hide_new_bundled_model(self):
        from lambda_cli.models import atomic_json
        with tempfile.TemporaryDirectory() as tmp:
            manager=ImageModels(tmp)
            atomic_json(Path(tmp)/'image-catalog.json',dict(schema=1,models=[manager.bundled['models'][0]]))
            self.assertIn('orion-1.2',[row['id'] for row in manager.entries()])

    def test_full_scene_keeps_clothing_description_and_never_masks_or_crops(self):
        class Network:
            generation_mode='full-scene-reference'
            metadata=dict(model_id='orion-1.2',name='orion 1.2')
            def mask(*args):raise AssertionError('Full-frame model must not mask/crop an object')
            def sample(self,refs,matte,caption,**kwargs):
                self.caption=caption
                np.testing.assert_array_equal(matte,np.ones_like(matte))
                return np.zeros((1,3,64,64),np.float32)
            def detail(self,coarse,refs,matte):return np.zeros((1,3,256,256),np.float32)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'reference.png';Image.new('RGB',(120,200),'red').save(path)
            row=dict(path=str(path),title='fixture',provider='DuckDuckGo Safe Search')
            with patch('lambda_cli.image_generation.OrionNetwork',return_value=Network()):
                generator=ImageGenerator('fixture',tmp)
            with patch.object(generator.references,'search',return_value=[row]) as search:
                pixels,metadata=generator.generate('person in suit')
            self.assertEqual(search.call_args.args[:2],('person in suit','scene'))
            self.assertEqual(generator.model.caption,'full scene: person in suit')
            self.assertEqual(metadata['model'],'orion-1.2');self.assertEqual(pixels.shape,(256,256,3))

    def test_generation_mode_must_match_model_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'invalid.npz'
            np.savez(path,metadata=np.asarray(json.dumps(dict(format='orion-image-v1',model_id='orion-1.2'))))
            with self.assertRaisesRegex(ValueError,'generation mode'):OrionNetwork(path)

    def test_numpy_resize_and_identity_spatial_transform(self):
        x=np.arange(48,dtype=np.float32).reshape(1,3,4,4)
        np.testing.assert_allclose(grid_sample(x,np.asarray([[[1,0,0],[0,1,0]]],np.float32)),x,atol=1e-5)
        self.assertEqual(resize(x,8).shape,(1,3,8,8));self.assertEqual(resize(x,8,nearest=True).shape,(1,3,8,8))

    @unittest.skipUnless(os.environ.get('LAMBDA_ORION_MODEL'),'Optional real Orion artifact')
    def test_real_native_neural_pixels_without_external_runtime(self):
        model=OrionNetwork(os.environ['LAMBDA_ORION_MODEL'])
        refs=np.zeros((1,2,3,256,256),np.float32);matte=np.ones((1,1,256,256),np.float32)
        coarse=model.sample(np.zeros((1,2,3,64,64),np.float32),resize(matte,64),'a cat in space',steps=2)
        out=model.detail(coarse,refs,matte)
        self.assertEqual(out.shape,(1,3,256,256));self.assertTrue(np.isfinite(out).all())

if __name__=='__main__':unittest.main()
