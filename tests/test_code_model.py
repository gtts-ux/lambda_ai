import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import numpy as np
from prompt_toolkit.document import Document
from lambda_cli.engine import Engine,Result
from lambda_cli.transformer import CODE_FORMAT,weight_shapes
from lambda_cli.byte_tokenizer import conversation_prompt
from lambda_cli.session import Session
from lambda_cli.models import ModelManager,atomic_json
from lambda_cli.model_browser import ModelBrowser
from lambda_cli.quota import Quota
from lambda_cli.tui import ConversationLexer
from test_web_search import web_fixture

def code_fixture(path):
    web_fixture(path)
    with np.load(path,allow_pickle=False) as z:arrays={k:z[k].copy() for k in z.files}
    meta=json.loads(str(arrays['metadata'].item()));meta.update(format=CODE_FORMAT,name='lambda code 3',model_id='lambda-code-3',code_adapter=True)
    arrays['metadata']=np.asarray(json.dumps(meta));arrays['search_w']=np.zeros((128,3),np.float32);arrays['search_b']=np.array([10,-10,-10],np.float32)
    np.savez_compressed(path,**arrays)

class CodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.path=self.root/'code.npz';code_fixture(self.path)

    def test_learned_three_way_router_selects_conditional_weights(self):
        for index,expected in enumerate(['chat','python','javascript']):
            with np.load(self.path,allow_pickle=False) as z:arrays={k:z[k].copy() for k in z.files}
            arrays['search_b'][:]=-10;arrays['search_b'][index]=10;np.savez_compressed(self.path,**arrays)
            engine=Engine(self.path);p=conversation_prompt(engine.tokenizer,[('Old request','Old reply')],'Current request',400)
            def generate(view,prompt,*args):
                self.assertEqual(view is engine,index==0)
                return Result('network answer',list(prompt),[],0,len(prompt),0,'stop')
            with patch('lambda_cli.code.PointerEngine.generate',autospec=True,side_effect=generate):
                r=engine.generate(p)
            self.assertEqual(r.intent,expected)
            self.assertFalse(engine.info()['automatic_search'])

    def test_code_model_never_searches_and_intent_view_handles_languages(self):
        engine=Engine(self.path);researcher=Mock();researcher.run.side_effect=AssertionError('Code model must remain offline')
        s=Session(engine,quota=Quota(self.root/'usage.sqlite3'),manager=ModelManager(self.root/'models'),researcher=researcher)
        self.assertFalse(s.supports_auto_search)
        s.add_user('Search for Python examples online')
        with patch.object(engine,'generate',return_value=Result('answer',[],[],0,0,0,'stop')):
            s.generate('Search for Python examples online')
        researcher.run.assert_not_called();s.inspected_text='Write JavaScript code'
        self.assertIn('Coding probability',s.intent_text())
        s.last_result=Result('answer',[],[],0,0,0,'stop',intent='python')
        self.assertIn('Detected intent       python',s.stats_text())
        self.assertNotIn('Math intent score',s.stats_text())

    def test_code_family_and_local_model_size_render(self):
        manager=ModelManager(self.root/'models');dest=manager.directory/'models';dest.mkdir(parents=True)
        (dest/'local.npz').write_bytes(self.path.read_bytes());state=manager.state()
        state['installed']['lambda-code-3']=dict(filename='local.npz',name='lambda code 3',revision=1,sha256='0'*64,local_only=True,min_app_version='0.8.4')
        atomic_json(manager.directory/'models.json',state);browser=ModelBrowser(manager)
        i=next(i for i,r in enumerate(browser.rows()) if r['id']=='code');self.assertEqual(browser.rows()[i]['name'],'lambda code')
        browser.choose(i);self.assertIn('lambda code 3',browser.text('lambda-code-3'));self.assertEqual(browser.choose(0),'use:lambda-code-3')

    def test_fenced_code_color_streaming_and_message_boundaries(self):
        lexer=ConversationLexer();doc=Document('  LAMBDA  ·  response\n\n  Example:\n  ```python\n  print("Hello")\n  ```\n  Explanation\n  ```javascript\n  console.log("Hi");\n\n  YOU  ·  message\n  normal text')
        line=lexer.lex_document(doc)
        self.assertEqual(line(4)[0][0],'class:chat.code')
        self.assertEqual(line(3)[0][0],'class:chat.fence')
        self.assertEqual(line(6)[0][0],'')
        self.assertEqual(line(8)[0][0],'class:chat.code')
        self.assertEqual(line(11)[0][0],'')
        self.assertEqual(line(4)[0][1],doc.lines[4])

if __name__=='__main__':unittest.main()
