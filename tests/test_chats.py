import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lambda_cli.chats import ChatStore
from lambda_cli.engine import Engine,Result,GeneratedToken,Settings
from lambda_cli.models import ModelManager
from lambda_cli.quota import Quota
from lambda_cli.session import Session
from test_transformer import fixture


class LocalChatTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);fixture(self.root/'model.npz')
        self.engine=Engine(self.root/'model.npz');self.store=ChatStore(self.root)
        self.manager=ModelManager(self.root/'models');self.quota=Quota(self.root/'usage.sqlite3')

    def session(self,resume=False):
        return Session(self.engine,quota=self.quota,manager=self.manager,store=self.store,resume=resume)

    def exchange(self,session,q,a):
        session.add_user(q)
        session.complete(Result(a,[1,2,3],[GeneratedToken(4,'<end>')],.01,3,0,'stop'))

    def test_restart_restores_text_context_settings_and_custom_model(self):
        first=self.session();self.exchange(first,'My name is Ada.','Hello, Ada.')
        first.command('/temperature 0.7');first.command('/topk 1');first.command('/rename Notes')
        identifier=first.chat_id;count=len(self.store.list())
        second=self.session(resume=True)
        self.assertEqual(second.chat_id,identifier);self.assertEqual(second.chat_title,'Notes')
        self.assertEqual(second.messages,first.messages)
        self.assertEqual(second.settings.temperature,.7);self.assertEqual(second.settings.top_k,1)
        self.assertEqual(second.engine.path,self.engine.path)
        self.assertIn('My name is Ada.',second.engine.tokenizer.decode(second.build_prompt('What is my name?')))
        self.assertEqual(len(self.store.list()),count) # Resuming must not create blank chats.
        self.assertIsNone(second.last_result) # Do not decode old IDs with a new tokenizer.

    def test_new_chat_preserves_old_one_and_has_independent_context(self):
        session=self.session();self.exchange(session,'My name is Ada.','Hello, Ada.')
        old=session.chat_id;ticket=self.quota.reserve(1,9);self.quota.complete(ticket,10)
        session.command('/new');new=session.chat_id
        self.assertNotEqual(new,old);self.assertEqual(session.messages,[])
        self.assertNotIn('Ada',session.engine.tokenizer.decode(session.build_prompt('What is my name?')))
        self.exchange(session,'My favorite color is green.','Your favorite color is green.')
        session.command('/chat '+old[:8])
        prompt=session.engine.tokenizer.decode(session.build_prompt('What is my name?'))
        self.assertIn('Ada',prompt);self.assertNotIn('green',prompt)
        self.assertEqual(self.quota.status()['used'],10)
        self.assertEqual(len(self.store.list()),2)
        self.assertIn('My name is Ada.',session.chats_text())

    def test_pending_user_message_and_model_boundary_survive_restart(self):
        session=self.session();self.exchange(session,'My name is Ada.','Hello, Ada.')
        session.memory_start=len(session.turns);session.persist()
        session.add_user('An interrupted question')
        resumed=self.session(resume=True)
        self.assertEqual(resumed.messages[-1],('You','An interrupted question'))
        self.assertEqual(resumed.memory_start,1)
        self.assertNotIn('Ada',resumed.engine.tokenizer.decode(resumed.build_prompt('Hello')))

    def test_concurrent_windows_preserve_both_snapshots(self):
        first=self.session();self.exchange(first,'First question','First answer')
        original=first.chat_id;second=self.session(resume=True)
        self.exchange(first,'Second question','Second answer')
        self.exchange(second,'Another branch','Other answer')
        self.assertNotEqual(second.chat_id,original)
        self.assertIn('separate copy',second.persistence_notice)
        old=self.store.get(original)['payload'];copy=self.store.get(second.chat_id)['payload']
        self.assertEqual(len(old['turns']),2);self.assertEqual(len(copy['turns']),2)
        self.assertEqual(old['turns'][-1]['text'],'Second answer')
        self.assertEqual(copy['turns'][-1]['text'],'Other answer')

    def test_bad_reference_or_missing_model_keeps_current_chat(self):
        session=self.session();self.exchange(session,'Question','Answer');first=session.chat_id
        with self.assertRaises(ValueError):session.command('/chat ../../outside')
        self.assertEqual(session.chat_id,first)
        payload=session.snapshot();payload['model_path']=str(self.root/'missing.npz')
        missing=self.store.create(payload,'Missing model')
        with self.assertRaisesRegex(ValueError,'needs'):session.command('/chat '+missing['id'])
        self.assertEqual(session.chat_id,first);self.assertEqual(session.messages[-1],('Lambda','Answer'))

    def test_named_model_is_restored_with_the_chat(self):
        session=Session(Engine(),quota=self.quota,manager=self.manager,store=self.store)
        self.exchange(session,'Hello!','Hello!');old=session.chat_id
        session.command('/new')
        session.engine=self.engine;session.persist();custom=session.chat_id
        session.command('/chat '+old)
        self.assertEqual(session.engine.metadata['model_id'],'lambda-1.0')
        session.command('/chat '+custom)
        self.assertEqual(session.engine.path,self.engine.path)

    def test_selecting_current_model_keeps_saved_context(self):
        session=Session(Engine(),quota=self.quota,manager=self.manager,store=self.store)
        self.exchange(session,'Hello!','Hello!')
        session.model_action('use:lambda-1.0')
        self.assertEqual(session.memory_start,0)
        self.assertEqual(self.store.get(session.chat_id)['payload']['memory_start'],0)

    def test_number_opens_the_entry_the_user_was_shown(self):
        session=self.session();self.exchange(session,'First topic','First answer');old=session.chat_id
        session.command('/new');session.chats_text()
        # A second window moves the older chat to the top after the list was drawn.
        row=self.store.get(old);self.store.save(old,row['revision'],row['title'],row['payload'])
        session.command('/chat 2')
        self.assertEqual(session.chat_id,old)

    def test_numeric_uuid_prefix_and_title_validation(self):
        session=self.session();session.command('/rename Work notes')
        self.assertEqual(self.store.get(session.chat_id)['title'],'Work notes')
        with self.assertRaises(ValueError):session.command('/rename Bad\x1btitle')
        # Eight-digit IDs are IDs, not list indices.
        row=self.store.get(session.chat_id)
        with self.store.connect() as db:db.execute('UPDATE chats SET id=? WHERE id=?',('12345678'+'a'*24,row['id']))
        session.chat_id=None
        session.command('/chat 12345678')
        self.assertEqual(session.chat_id,'12345678'+'a'*24)
