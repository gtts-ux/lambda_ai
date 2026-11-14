import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend import Desktop
from lambda_cli.engine import Result,GeneratedToken


class DesktopBackendTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.environment=patch.dict(os.environ,{'LAMBDA_DATA_HOME':self.directory.name})
        self.environment.start();self.addCleanup(self.environment.stop)
        self.desktop=Desktop()

    def test_real_generation_persists_and_shares_existing_allowance(self):
        d=self.desktop
        value=d.dispatch('send',{'text':'hello'})
        self.assertEqual(len(value['chat']['messages']),2)
        self.assertGreater(value['quota']['used'],0)
        reopened=Desktop().state()
        self.assertEqual(reopened['chat']['id'],value['chat']['id'])
        self.assertEqual(reopened['chat']['messages'],value['chat']['messages'])
        self.assertEqual(reopened['quota']['used'],value['quota']['used'])

    def test_catalog_and_uninstalled_selection_never_download_weights(self):
        d=self.desktop
        with patch.object(d.manager,'install',side_effect=AssertionError('Unexpected download')):
            self.assertEqual(d.state()['chat']['modelId'],'lambda-1.0')
            with self.assertRaisesRegex(ValueError,'Download this model'):
                d.dispatch('select_model',{'id':'lambda-2.4'})
            with patch.object(d.manager,'refresh_catalog') as refresh:
                d.dispatch('refresh_catalog',{})
                refresh.assert_called_once()

    def test_single_explicit_download_and_preferences(self):
        d=self.desktop
        with patch.object(d.manager,'install') as install:
            d.dispatch('download',{'id':'lambda-2.4'})
            self.assertEqual(install.call_count,1)
            self.assertEqual(install.call_args.args[0],'lambda-2.4')
        d.dispatch('preferences',{'values':{'theme':'dark','accent':'sage','fontSize':18}})
        self.assertEqual(Desktop().preferences['theme'],'dark')
        before=Path(d.preferences_path).read_bytes();d.generating=True
        with self.assertRaises(ValueError):d.dispatch('preferences',{'values':{'responseTokens':384}})
        self.assertEqual(Path(d.preferences_path).read_bytes(),before)

    def test_archiving_keeps_messages_and_can_be_restored(self):
        d=self.desktop;d.dispatch('send',{'text':'hello'})
        identifier=d.session.chat_id;before=d.store.get(identifier)['payload']
        d.dispatch('archive_chat',{'id':identifier})
        self.assertEqual(d.chats(),[])
        self.assertEqual(d.chats(archived=True)[0]['id'],identifier)
        self.assertEqual(d.store.get(identifier)['payload']['messages'],before['messages'])
        self.assertIsNone(d.store.active())
        d.dispatch('restore_chat',{'id':identifier});d.dispatch('open_chat',{'id':identifier})
        self.assertEqual(d.session.chat_id,identifier)

    def test_cancellation_settles_reserved_tokens_and_preserves_partial_reply(self):
        d=self.desktop;entered=threading.Event();errors=[]
        def generate(prompt,settings,progress,cancel):
            entered.set();progress('Hello',3);cancel.wait(3)
            ids=prompt if isinstance(prompt,list) else d.session.engine.tokenizer.encode(prompt)
            return Result('Hello',ids,[GeneratedToken(5,'x')]*3,.1,min(len(ids),d.session.engine.context),0,'cancelled')
        def send():
            try:d.dispatch('send',{'text':'hello'})
            except Exception as error:errors.append(error)
        with patch.object(d.session.engine,'generate',side_effect=generate):
            thread=threading.Thread(target=send);thread.start();self.assertTrue(entered.wait(2))
            d.dispatch('stop',{});thread.join(3)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        state=d.state();self.assertFalse(state['generating'])
        self.assertEqual(state['chat']['messages'][-1]['text'],'Hello')
        self.assertEqual(state['quota']['used'],d.session.last_result.context_used+3)
        with d.quota.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM reservations').fetchone()[0],0)

    def test_delete_removes_only_requested_chat_and_keeps_quota(self):
        d=self.desktop;d.dispatch('send',{'text':'hello'})
        first=d.session.chat_id;d.new_chat();d.dispatch('send',{'text':'hello'})
        second=d.session.chat_id;used=d.quota.status()['used']
        d.dispatch('pin_chat',{'id':second});d.dispatch('delete_chat',{'id':second})
        self.assertEqual([r['id'] for r in d.chats()],[first])
        self.assertIsNone(d.session.chat_id);self.assertIsNone(d.store.active())
        self.assertEqual(d.quota.status()['used'],used)
        with self.assertRaises(ValueError):d.store.get(second)
        self.assertEqual(Desktop().chats()[0]['id'],first)
        d.generating=True
        with self.assertRaises(ValueError):d.dispatch('delete_chat',{'id':first})
        self.assertEqual(len(d.chats()),1)

    def test_profile_is_real_input_context_and_never_a_generated_answer(self):
        from lambda_cli.byte_tokenizer import ByteTokenizer
        d=self.desktop
        d.dispatch('preferences',{'values':{'displayName':'Taylor','age':'24','location':'Warsaw','interests':'music','shareProfile':True}})
        class Model:
            supports_memory=True
            tokenizer=ByteTokenizer(dict(type="lambda-byte-bpe-v1",bytes=[bytes([i]).hex() for i in range(256)],merges=[]))
            context=512
        with patch.object(d.session,'engine',Model()):
            prompt=d.session.build_prompt('What is my age?')
            text=Model.tokenizer.decode(prompt)
            self.assertIn('My name is Taylor.',text);self.assertIn('I am 24 years old.',text)
            self.assertIn('What is my age?',text);self.assertLessEqual(len(prompt),512)
            d.preferences['shareProfile']=False
            self.assertNotIn('Taylor',Model.tokenizer.decode(d.session.build_prompt('What is my age?')))
        self.assertEqual(d.session.turns,[]);self.assertEqual(d.session.messages,[])
        self.assertEqual(Desktop().preferences['age'],'24')
        with self.assertRaises(ValueError):d.dispatch('preferences',{'values':{'age':'999'}})


if __name__=='__main__':unittest.main()
