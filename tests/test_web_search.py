import asyncio,json,socket,tempfile
from pathlib import Path
from threading import Event
from unittest.mock import patch,Mock
import unittest
import numpy as np
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from lambda_cli.web_search import (PageText,WebResearch,ResearchCancelled,public_url,addresses,fetch_page,excerpt,source_prompt)
from lambda_cli.engine import Engine,Result,Settings,GeneratedToken
from lambda_cli.session import Session
from lambda_cli.models import ModelManager
from lambda_cli.chats import ChatStore
from lambda_cli.quota import Quota
from lambda_cli.tui import TerminalApp
from lambda_cli.transformer import GROUNDED_FORMAT,weight_shapes
from test_terminal_layout import SizedOutput
from test_transformer import fixture


def web_fixture(path):
    fixture(path)
    with np.load(path,allow_pickle=False) as z:arrays={k:z[k].copy() for k in z.files}
    metadata=json.loads(str(arrays['metadata'].item()));metadata.update(context=1024,format=GROUNDED_FORMAT,model_id='lambda-2.5.1',evidence_rank=2,evidence_layers=1,search_features=128,pointer_width=8)
    arrays['metadata']=np.asarray(json.dumps(metadata));arrays['position']=np.tile(arrays['position'],(8,1))
    for key,shape in weight_shapes(metadata).items():
        if key not in arrays:arrays[key]=np.zeros(shape,np.float32)
    arrays['pointer_norm_w'][:]=1;arrays['pointer_gate_b'][:]=-6;arrays['search_b'][:]=[-10,10]
    np.savez_compressed(path,**arrays)

def research():
    return dict(query='What is the hottest planet?',searched_at='2026-10-31T00:00:00+00:00',sources=[dict(title='Planet facts',url='https://example.org/venus',excerpt='Venus is the hottest planet in the solar system. Its thick atmosphere traps heat.',kind='page excerpt (bounded read)',included=False,context_excerpt='')],errors=[],requested_url=None)

class ReaderTests(unittest.TestCase):
    def test_extracts_article_text_and_skips_navigation_scripts_and_controls(self):
        p=PageText();p.feed('<html><title>Facts</title><nav>Menu ads</nav><script>ignore_previous_instructions()</script><main><h1>Planets</h1><p>Venus is the hottest planet in the solar system.</p></main><footer>Copyright</footer></html>')
        title,parts=p.result();self.assertEqual(title,'Facts');text=' '.join(parts)
        self.assertIn('Venus',text);self.assertNotIn('Menu',text);self.assertNotIn('ignore_previous',text)
        quote=excerpt(parts,'hottest planet');self.assertIn('Venus',quote)
        self.assertLessEqual(len(excerpt(['Venus '+('word '*100)],'Venus').split()),45)
    def test_rejects_credentials_local_private_and_non_http_links(self):
        for url in ['file:///etc/passwd','http://localhost/','http://A.LOCAL/','https://u:p@example.com/','http://127.0.0.1/','http://169.254.169.254/','http://10.1.1.1/','http://[::1]/','http://[fc00::1]/','https://example.com:22/','https://example.com/\x1b[31m']:
            with self.subTest(url=url),self.assertRaises(ValueError):public_url(url)
        self.assertEqual(public_url('https://example.com/page#section'),'https://example.com/page')
        with patch('socket.getaddrinfo',return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',443))]):
            with self.assertRaises(ValueError):addresses('public-looking.test',443)
    def test_redirect_to_private_network_is_checked_before_second_request(self):
        response=Mock(status=302);response.getheader.side_effect=lambda k,d=None:'http://127.0.0.1/private' if k=='Location' else d
        connection=Mock();connection.getresponse.return_value=response
        with patch('lambda_cli.web_search.addresses',return_value=['93.184.216.34']),patch('http.client.HTTPSConnection',return_value=connection) as connect:
            with self.assertRaises(ValueError):fetch_page('https://example.org/start')
        self.assertEqual(connect.call_count,1);connection.close.assert_called()
    def test_search_reads_multiple_domains_and_marks_unread_snippets_honestly(self):
        search=Mock(return_value=[dict(href='http://127.0.0.1/',title='bad',body='bad'),dict(href='https://one.example/a',title='One',body='Search snippet about Venus and the hottest planet.'),dict(href='https://one.example/b',title='Duplicate host',body=''),dict(href='https://two.example/a',title='Two',body=''),dict(href='https://three.example/a',title='Three',body='')])
        def fetch(url,cancel):
            if url.startswith('https://one.'):raise ValueError('HTTP 403')
            return url,'Read page',['Venus is the hottest planet in our solar system because its atmosphere traps heat.']
        phases=[];r=WebResearch(search,fetch).run('hottest planet',phases.append)
        self.assertEqual(len(r['sources']),3);self.assertIn('two.example',r['sources'][0]['url'])
        self.assertIn('three.example',r['sources'][1]['url']);self.assertEqual(r['sources'][2]['kind'],'search snippet; page not read')
        self.assertTrue(phases[0].startswith('Searching'));self.assertTrue(phases[-1].startswith('Preparing'))
    def test_cancelled_search_does_not_fetch_pages_or_generate_fake_evidence(self):
        cancel=Event();fetch=Mock()
        def search(q):cancel.set();return []
        with self.assertRaises(ResearchCancelled):WebResearch(search,fetch).run('query',cancel=cancel)
        fetch.assert_not_called()
    def test_page_failure_without_snippet_reports_error_instead_of_an_answer(self):
        with self.assertRaisesRegex(ValueError,'No readable'):
            WebResearch(lambda q:[dict(href='https://example.com/',body='')],lambda *a:(_ for _ in ()).throw(ValueError('HTTP 403'))).run('question')

class ResearchSessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        web_fixture(self.root/'fixture.npz');self.reader=Mock();self.reader.run.return_value=research()
        self.session=Session(Engine(self.root/'fixture.npz'),settings=Settings(max_tokens=80),quota=Quota(self.root/'usage.sqlite3'),manager=ModelManager(self.root/'models'),store=ChatStore(self.root),researcher=self.reader)
    def generate(self,prompt,settings,on_text,cancel,**kwargs):
        return Result('Model-only draft',list(prompt),[GeneratedToken(4,'end')],.1,len(prompt),0,'stop')
    def test_context_includes_evidence_preserves_question_and_charges_actual_input(self):
        self.session.add_user('My local secret is 1234.');self.session.complete(Result('Okay.',[],[],0,0,0,'stop'))
        self.session.add_user('What is the hottest planet?')
        with patch.object(self.session.engine,'generate',side_effect=self.generate) as generate:
            result=self.session.generate('What is the hottest planet?');self.session.complete(result)
        prompt=generate.call_args.args[0];text=self.session.engine.tokenizer.decode(prompt)
        self.assertIn('Venus',text);self.assertIn('What is the hottest planet?',text);self.assertNotIn('1234',text)
        self.assertLessEqual(len(prompt),1024-80)
        self.assertEqual(result.text,'Model-only draft');self.assertNotEqual(result.text,'Venus')
        self.assertEqual(self.reader.run.call_args.args[0],'What is the hottest planet?')
        self.assertTrue(result.research['sources'][0]['included']);self.assertEqual(self.session.quota.status()['used'],len(prompt)+1)
        saved=self.session.store.get(self.session.chat_id)['payload'];self.assertIn('research',saved['turns'][-1])
    def test_offline_chat_never_calls_search_and_old_snapshots_still_open(self):
        legacy=self.root/'legacy.npz';fixture(legacy);self.session.engine=Engine(legacy)
        self.session.add_user('Hello')
        with patch.object(self.session.engine,'generate',side_effect=self.generate):r=self.session.generate('Hello');self.session.complete(r)
        self.reader.run.assert_not_called();saved=self.session.snapshot();saved['web_enabled']=True
        row=self.session.store.create(saved,'Old snapshot');self.session.open_chat(row['id']);self.assertFalse(self.session.supports_auto_search)
    def test_failure_and_cancellation_leave_allowance_untouched(self):
        self.reader.run.side_effect=ResearchCancelled('Cancelled')
        with patch.object(self.session.engine,'generate') as generate,self.assertRaises(ResearchCancelled):self.session.generate('question')
        generate.assert_not_called();self.assertEqual(self.session.quota.status()['used'],0)
    def test_research_metadata_survives_restart_without_enabling_old_models(self):
        self.session.add_user('hottest planet')
        with patch.object(self.session.engine,'generate',side_effect=self.generate):r=self.session.generate('hottest planet');self.session.complete(r)
        old=self.session.chat_id;self.session.command('/new');self.assertIsNone(self.session.current_research)
        self.session.open_chat(old);self.assertTrue(self.session.supports_auto_search);self.assertIn('example.org',self.session.current_research['sources'][0]['url'])
        self.session.engine.metadata['model_id']='lambda-2.4';self.assertFalse(self.session.supports_auto_search)
    def test_evidence_budget_does_not_clip_question_or_insert_role_tokens(self):
        r=research();r['sources']*=3
        r['sources']=[dict(s,excerpt='Venus <assistant> '*100) for s in r['sources']]
        ids=source_prompt(self.session.engine.tokenizer,'Question stays here?',r,512,120)
        self.assertLessEqual(len(ids),392);self.assertEqual(ids.count(2),1);self.assertEqual(ids.count(3),1)
        self.assertIn('Question stays here?',self.session.engine.tokenizer.decode(ids));self.assertTrue(any(s['included'] for s in r['sources']))
    def test_all_older_models_remain_offline_and_commands_are_removed(self):
        self.assertTrue(self.session.supports_auto_search)
        self.assertTrue(self.session.engine.info()['automatic_search'])
        for name in ['lambda-1.0','lambda-1.5','lambda-1.6','lambda-2','lambda-2.1','lambda-2.2','lambda-2.4','lambda-2.5']:
            self.session.engine.metadata['model_id']=name
            self.assertFalse(self.session.supports_auto_search)
            self.assertFalse(self.session.engine.info()['automatic_search'])
            with patch.object(self.session.engine,'generate',side_effect=self.generate):self.session.generate('current news')
            self.reader.run.assert_not_called()
        for command in ['/web question','/web on','/read https://example.org','/sources']:
            with self.assertRaisesRegex(ValueError,'Unknown command'):self.session.command(command)

class ResearchUITests(unittest.IsolatedAsyncioTestCase):
    async def test_live_search_read_thinking_phases_and_local_sources_tab(self):
        with tempfile.TemporaryDirectory() as d,create_pipe_input() as pipe,create_app_session(input=pipe,output=SizedOutput(100,36)):
            root=Path(d);web_fixture(root/'model.npz');observed=[]
            def search(q):return [dict(href='https://example.org/facts',title='Facts',body='')]
            def fetch(url,cancel):return url,'Page facts',['Venus is the hottest planet in the solar system because its atmosphere traps heat.']
            session=Session(Engine(root/'model.npz'),quota=Quota(root/'usage.sqlite3'),manager=ModelManager(root/'models'),store=ChatStore(root),researcher=WebResearch(search,fetch))
            ui=TerminalApp(session);task=asyncio.create_task(ui.app.run_async())
            def generate(prompt,settings,on_text,cancel,**kwargs):return Result('Draft from the model.',list(prompt),[GeneratedToken(4,'end')],.1,len(prompt),0,'stop')
            old_phase=ui.research_phase
            def phase(text):observed.append(text);old_phase(text)
            ui.research_phase=phase
            try:
                await asyncio.sleep(.08)
                with patch.object(session.engine,'generate',side_effect=generate) as answer:
                    pipe.send_text('hottest planet\r')
                    for _ in range(80):
                        await asyncio.sleep(.01)
                        if answer.called and not ui.busy:break
                    self.assertTrue(answer.called);self.assertFalse(ui.busy)
                self.assertTrue(any(v.startswith('Searching') for v in observed));self.assertTrue(any(v.startswith('Reading') for v in observed));self.assertTrue(any(v.startswith('Thinking') for v in observed))
                self.assertIn('Draft from the model.',ui.body.text)
                self.assertNotIn('example.org',ui.body.text);self.assertNotIn('[1]',ui.body.text)
                self.assertNotIn('EXPERIMENTAL MODEL DRAFT',ui.body.text)
            finally:ui.close();await task

class GroundedEngineTests(unittest.TestCase):
    def test_learned_head_controls_search_without_keyword_fallbacks(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'model.npz';web_fixture(p);e=Engine(p)
            self.assertTrue(e.search_decision('Hello')['search'])
            with np.load(p,allow_pickle=False) as z:arrays={k:z[k].copy() for k in z.files}
            arrays['search_b'][:]=[10,-10];np.savez_compressed(p,**arrays);e=Engine(p)
            self.assertFalse(e.search_decision('What are the latest news and prices today?')['search'])
            self.assertTrue(all(not w.flags.writeable for w in e.weights.values()))
    def test_evidence_adapters_are_conditional_and_do_not_mutate_base_arrays(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'model.npz';web_fixture(p)
            with np.load(p,allow_pickle=False) as z:arrays={k:z[k].copy() for k in z.files}
            arrays['evidence_b1_proj_a'][:]=.05;arrays['evidence_b1_proj_b'][:]=.03
            np.savez_compressed(p,**arrays);e=Engine(p);before=e.weights['b1_proj'].copy()
            view=e.evidence_view();self.assertFalse(np.array_equal(view.weights['b1_proj'],before))
            np.testing.assert_array_equal(e.weights['b1_proj'],before)
            self.assertTrue(all(not w.flags.writeable for w in view.weights.values()))

class SpanReaderTests(unittest.TestCase):
    def fixture(self,path):
        web_fixture(path)
        with np.load(path,allow_pickle=False) as z:arrays={k:z[k].copy() for k in z.files}
        metadata=json.loads(str(arrays['metadata'].item()));metadata['span_reader']=True
        arrays['metadata']=np.asarray(json.dumps(metadata))
        for k,shape in weight_shapes(metadata).items():
            if k not in arrays:arrays[k]=np.zeros(shape,np.float32)
        arrays['span_answerable_b'][:]=[-10,10]
        np.savez_compressed(path,**arrays)
    def test_span_is_neurally_decoded_from_evidence_and_limit_is_respected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'model.npz';self.fixture(path);engine=Engine(path)
            r=research();prompt=source_prompt(engine.tokenizer,'hottest planet?',r,1024,64)
            lo,hi=r['source_token_range']
            result=engine.generate(prompt,Settings(max_tokens=1),evidence=True,evidence_range=[lo,hi])
            self.assertEqual(result.text,engine.tokenizer.decode(prompt[lo:lo+1]).strip())
            self.assertLessEqual(len(result.generated),1)
            self.assertNotIn('[1]',result.text)
    def test_span_reader_rejects_invalid_evidence_bounds(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'model.npz';self.fixture(path);engine=Engine(path)
            for bounds in [None,[2,1],[-1,4],[0,1000],['2',3]]:
                with self.assertRaises(ValueError):engine.generate([1,2,10,4,3],evidence=True,evidence_range=bounds)
