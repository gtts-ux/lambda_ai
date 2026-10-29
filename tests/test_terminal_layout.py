import asyncio
import tempfile
from pathlib import Path
import unittest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.formatted_text import fragment_list_to_text
from lambda_cli.engine import Engine
from lambda_cli.models import ModelManager
from lambda_cli.quota import Quota,WINDOW_SECONDS
from lambda_cli.session import Session
from lambda_cli.tui import TerminalApp,allowance_meter
from lambda_cli.chats import ChatStore

class SizedOutput(DummyOutput):
    def __init__(self,columns,rows):self.columns,self.rows=columns,rows
    def get_size(self):return Size(rows=self.rows,columns=self.columns)

class LayoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_exit_during_generation_waits_for_the_cancelled_turn_to_save(self):
        from unittest.mock import patch
        from lambda_cli.engine import Result
        with tempfile.TemporaryDirectory() as directory,create_pipe_input() as pipe,create_app_session(input=pipe,output=SizedOutput(100,35)):
            store=ChatStore(directory)
            session=Session(Engine(),quota=Quota(Path(directory)/'usage.sqlite3'),
                            manager=ModelManager(Path(directory)/'models'),store=store)
            def generate(question,on_text,cancel):
                cancel.wait(timeout=2)
                return Result('Partial reply',[],[],.1,0,0,'cancelled')
            ui=TerminalApp(session)
            with patch.object(session,'generate',side_effect=generate):
                task=asyncio.create_task(ui.app.run_async())
                await asyncio.sleep(.08);pipe.send_text('Hello!\r')
                for _ in range(40):
                    await asyncio.sleep(.01)
                    if ui.busy:break
                ui.close();await asyncio.wait_for(task,timeout=3)
            saved=store.get(session.chat_id)['payload']
            self.assertEqual(saved['turns'][-1]['finish_reason'],'cancelled')
            self.assertEqual(saved['messages'][-1],['Lambda','Partial reply'])

    async def test_f6_reopens_a_previous_saved_conversation(self):
        with tempfile.TemporaryDirectory() as directory,create_pipe_input() as pipe,create_app_session(input=pipe,output=SizedOutput(100,35)):
            from lambda_cli.engine import Result
            store=ChatStore(directory)
            session=Session(Engine(),quota=Quota(Path(directory)/'usage.sqlite3'),
                            manager=ModelManager(Path(directory)/'models'),store=store)
            session.add_user('Hello!');session.complete(Result('Hello!',[],[],.1,0,0,'stop'))
            old=session.chat_id;session.command('/rename Greeting');session.command('/new')
            ui=TerminalApp(session);task=asyncio.create_task(ui.app.run_async())
            try:
                await asyncio.sleep(.08)
                pipe.send_text('\x1b[17~') # F6
                await asyncio.sleep(.08)
                self.assertEqual(ui.view,'chats');self.assertIn('Greeting',ui.body.text)
                pipe.send_text('2\r')
                await asyncio.sleep(.1)
                self.assertEqual(ui.view,'chat');self.assertEqual(session.chat_id,old)
                self.assertIn('Hello!',ui.body.text)
            finally:
                ui.close();await task

    async def test_live_remaining_bar_reset_and_updates_tab_at_both_sizes(self):
        for columns,rows in [(64,24),(120,40)]:
            with self.subTest(size=(columns,rows)),tempfile.TemporaryDirectory() as directory:
                now=[100.];q=Quota(Path(directory)/'usage.sqlite3',clock=lambda:now[0])
                reserved=q.reserve(0,750000);q.complete(reserved,750000)
                session=Session(Engine(),quota=q,manager=ModelManager(Path(directory)/'models'))
                with create_pipe_input() as pipe,create_app_session(input=pipe,output=SizedOutput(columns,rows)):
                    ui=TerminalApp(session);task=asyncio.create_task(ui.app.run_async())
                    try:
                        await asyncio.sleep(.08)
                        self.assertIn('25.0% left',fragment_list_to_text(ui.allowance()))
                        self.assertIn('250,000 / 1,000,000',fragment_list_to_text(ui.allowance()))
                        screen=ui.app.renderer.last_rendered_screen
                        visible='\n'.join(''.join(screen.data_buffer[y][x].char for x in range(columns)) for y in range(rows))
                        self.assertIn('25.0% left',visible)
                        self.assertIn('Message',visible)
                        self.assertIn('Updates',visible)
                        pipe.send_text('\x1b[15~') # F5
                        await asyncio.sleep(.08)
                        self.assertEqual(ui.view,'updates');self.assertIn('APPLICATION & MODEL UPDATES',ui.body.text)
                        now[0]+=WINDOW_SECONDS
                        self.assertIn('100.0% left',fragment_list_to_text(ui.allowance()))
                        self.assertEqual(q.status()['used'],0)
                    finally:
                        ui.close();await task

    def test_thresholds_show_remaining_not_spent(self):
        self.assertEqual(allowance_meter(1000000,1000000,20),(1.,20,'quota.good'))
        self.assertEqual(allowance_meter(200000,1000000,20),(.2,4,'quota.low'))
        self.assertEqual(allowance_meter(0,1000000,20),(0.,0,'quota.empty'))
        self.assertEqual(allowance_meter(-5,1000000,20),(0.,0,'quota.empty'))
