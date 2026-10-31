import asyncio,json,sqlite3,tempfile
from pathlib import Path
from unittest.mock import patch
import unittest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from lambda_cli.chats import ChatStore
from lambda_cli.engine import Engine,Result,GeneratedToken
from lambda_cli.models import ModelManager
from lambda_cli.model_browser import ModelBrowser
from lambda_cli.quota import Quota
from lambda_cli.session import Session
from lambda_cli.tui import TerminalApp
from test_terminal_layout import SizedOutput
from test_transformer import fixture

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        fixture(self.root/'model.npz');self.store=ChatStore(self.root);self.manager=ModelManager(self.root/'models')
        self.session=Session(Engine(self.root/'model.npz'),quota=Quota(self.root/'usage.sqlite3'),manager=self.manager,store=self.store)
    def exchange(self,q,a):
        self.session.add_user(q);self.session.complete(Result(a,[1,2,3],[GeneratedToken(4,'end')],.1,3,0,'stop'))
    def test_search_matches_messages_and_unicode_titles_not_token_metadata(self):
        self.exchange('Hello','The albatross is a bird.');self.session.command('/rename Żółw')
        self.assertEqual(len(self.store.list('ALBATROSS')),1);self.assertEqual(len(self.store.list('ŻÓŁW')),1)
        self.assertEqual(self.store.list('generated_tokens'),[]);self.assertEqual(self.store.list('%'),[])
        self.session.command('/search albatross');self.assertIn('Żółw',self.session.chats_text())
        self.session.command('/search');self.assertEqual(self.session.chat_query,'')
    def test_pin_order_and_legacy_writes_remain_compatible(self):
        self.exchange('First','One');first=self.session.chat_id;self.session.command('/new');second=self.session.chat_id
        self.assertTrue(self.session.pin_chat(first));self.assertEqual(self.store.list()[0]['id'],first)
        payload=self.session.snapshot()
        with self.store.connect() as db:
            db.execute('INSERT INTO chats VALUES (?,?,?,?,?,?,?,?)',('b'*32,'Legacy window',1.,99999999999.,1,json.dumps(payload),'Legacy model',0))
        self.assertEqual(self.store.list()[0]['id'],first)
        self.assertFalse(self.session.pin_chat(first));self.assertEqual(self.store.list()[0]['title'],'Legacy window')
    def test_edit_forks_from_selected_question_without_later_context(self):
        self.exchange('My name is Ada.','Hello Ada.');self.exchange('I like green.','Okay.');old=self.session.chat_id
        q=self.session.prepare_revision(1,'My name is Maya.')
        self.assertNotEqual(self.session.chat_id,old);self.assertEqual(self.session.turns,[])
        prompt=self.session.engine.tokenizer.decode(self.session.build_prompt(q))
        self.assertIn('Maya',prompt);self.assertNotIn('Ada',prompt);self.assertNotIn('green',prompt)
        self.assertEqual(len(self.store.get(old)['payload']['turns']),2)
    def test_regeneration_keeps_original_and_charges_new_generation(self):
        def generate(prompt,settings,on_text,cancel):return Result('Reply',list(prompt),[GeneratedToken(4,'end')],.1,len(prompt),0,'stop')
        with patch.object(self.session.engine,'generate',side_effect=generate):
            self.session.add_user('Hello');r=self.session.generate('Hello');self.session.complete(r)
            old=self.session.chat_id;used=self.session.quota.status()['used']
            q=self.session.prepare_revision(1,kind='retry');self.session.add_user(q)
            r2=self.session.generate(q);self.session.complete(r2)
        self.assertEqual(self.session.quota.status()['used'],used+r2.charged_tokens)
        self.assertEqual(self.store.get(old)['payload']['turns'][0]['text'],'Reply')
        self.assertEqual(len(self.session.turns),1)
    def test_families_and_versions_use_catalog_ids(self):
        menu=ModelBrowser(self.manager)
        self.assertEqual([x['name'] for x in menu.rows()],['lambda 1','lambda 2'])
        menu.choose(0);self.assertEqual([x['id'] for x in menu.rows()],['lambda-1.0','lambda-1.5','lambda-1.6'])
        self.assertEqual(menu.choose(1),'use:lambda-1.5');self.assertTrue(menu.back())
        menu.choose(1);self.assertEqual(menu.rows()[-1]['id'],'lambda-2.5.1')
        self.assertEqual(menu.choose(len(menu.rows())-1),'use:lambda-2.5.1')

class WorkspaceUITests(unittest.IsolatedAsyncioTestCase):
    async def test_arrow_family_version_navigation_and_edit_prefill(self):
        with tempfile.TemporaryDirectory() as directory,create_pipe_input() as pipe,create_app_session(input=pipe,output=SizedOutput(110,38)):
            store=ChatStore(directory);manager=ModelManager(Path(directory)/'models')
            session=Session(Engine(),quota=Quota(Path(directory)/'quota.sqlite3'),manager=manager,store=store)
            session.add_user('Hello!');session.complete(Result('Hello!',[],[],.1,0,0,'stop'))
            ui=TerminalApp(session);task=asyncio.create_task(ui.app.run_async())
            try:
                await asyncio.sleep(.08);pipe.send_text('\x1bOR');await asyncio.sleep(.05) # F3
                self.assertIn('MODELS / FAMILIES',ui.body.text)
                pipe.send_text('\r');await asyncio.sleep(.05)
                self.assertIn('LAMBDA 1 VERSIONS',ui.body.text)
                with patch.object(session,'model_action',return_value='Using test model') as action:
                    pipe.send_text('\x1b[B\r');await asyncio.sleep(.12)
                    self.assertEqual(action.call_args.args[0],'use:lambda-1.5')
                pipe.send_text('\x1b[D');await asyncio.sleep(.05);self.assertIsNone(ui.models.family)
                ui.select('chat');ui.begin_edit();self.assertEqual(ui.input.text,'Hello!')
                self.assertEqual(ui.edit_turn,1);ui.cancel_edit();self.assertIsNone(ui.edit_turn)
            finally:ui.close();await task
    async def test_submitting_an_edited_question_generates_and_saves_a_separate_branch(self):
        with tempfile.TemporaryDirectory() as directory,create_pipe_input() as pipe,create_app_session(input=pipe,output=SizedOutput(100,35)):
            model=Path(directory)/'fixture.npz';fixture(model)
            session=Session(Engine(model),quota=Quota(Path(directory)/'quota.sqlite3'),manager=ModelManager(Path(directory)/'models'),store=ChatStore(directory))
            session.add_user('My name is Ada.');session.complete(Result('Hello Ada.',[],[],.1,0,0,'stop'))
            original=session.chat_id;ui=TerminalApp(session);task=asyncio.create_task(ui.app.run_async())
            def generate(prompt,settings,on_text,cancel):
                self.assertIn('Maya',session.engine.tokenizer.decode(prompt))
                self.assertNotIn('Ada',session.engine.tokenizer.decode(prompt))
                return Result('Hello Maya.',list(prompt),[GeneratedToken(4,'end')],.1,len(prompt),0,'stop')
            try:
                await asyncio.sleep(.08)
                with patch.object(session.engine,'generate',side_effect=generate) as answer:
                    pipe.send_text('/edit 1 My name is Maya.\r')
                    for _ in range(50):
                        await asyncio.sleep(.01)
                        if answer.called and not ui.busy:break
                    self.assertTrue(answer.called);self.assertFalse(ui.busy)
                self.assertNotEqual(session.chat_id,original)
                self.assertEqual(session.store.get(session.chat_id)['payload']['turns'][0]['text'],'Hello Maya.')
                self.assertEqual(session.store.get(original)['payload']['turns'][0]['text'],'Hello Ada.')
                self.assertGreater(session.quota.status()['used'],0)
            finally:ui.close();await task

    async def test_search_and_pinning_do_not_send_a_message_to_the_model(self):
        with tempfile.TemporaryDirectory() as directory,create_pipe_input() as pipe,create_app_session(input=pipe,output=SizedOutput(90,32)):
            session=Session(Engine(),quota=Quota(Path(directory)/'quota.sqlite3'),manager=ModelManager(Path(directory)/'models'),store=ChatStore(directory))
            session.add_user('Hello!');session.complete(Result('Albatross',[],[],.1,0,0,'stop'))
            ui=TerminalApp(session);task=asyncio.create_task(ui.app.run_async())
            try:
                await asyncio.sleep(.08);ui.select('chats');pipe.send_text('albatross\r');await asyncio.sleep(.08)
                self.assertEqual(session.chat_query,'albatross');self.assertEqual(len(session.turns),1)
                pipe.send_text('\x10');await asyncio.sleep(.08)
                self.assertTrue(session.store.list()[0]['pinned'])
            finally:ui.close();await task
