"""Local desktop bridge. The existing engine generates every assistant answer."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import getpass
import json
from pathlib import Path
import re
import sys
import threading
import time

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lambda_cli import __version__
from lambda_cli.chats import ChatStore
from lambda_cli.engine import Engine, Settings, DEFAULT_MODEL
from lambda_cli.families import canonical_id, family_for
from lambda_cli.models import ModelManager, atomic_json
from lambda_cli.paths import data_dir
from lambda_cli.quota import Quota
from lambda_cli.session import Session

WRITE_LOCK = threading.Lock()


class ProfileSession(Session):
    """User-authored context only; the neural engine still generates the reply."""
    def build_prompt(self, question):
        profile = getattr(self, 'profile_preferences', {})
        if not profile.get('shareProfile', True) or not getattr(self.engine, 'supports_memory', False):
            return super().build_prompt(question)
        from lambda_cli.byte_tokenizer import USER, END, conversation_prompt
        facts = []
        for key, template in [('displayName', 'My name is {}.'), ('age', 'I am {} years old.'),
                              ('location', 'I live in {}.'), ('interests', 'My interests are {}.')]:
            if profile.get(key): facts.append(template.format(profile[key]))
        if not facts: return super().build_prompt(question)
        tokenizer, context = self.engine.tokenizer, self.engine.context
        details = tokenizer.encode(' '.join(facts))[:max(0, context//4-2)]
        block = [USER] + details + [END]
        turns = [(t['question'], t['text']) for t in self.turns[self.memory_start:]
                 if t.get('finish_reason') != 'cancelled' and t.get('text')]
        prompt = conversation_prompt(tokenizer, turns, question, context-len(block))
        return prompt[:1] + block + prompt[1:]


def output(value):
    with WRITE_LOCK:
        print(json.dumps(value, ensure_ascii=False, allow_nan=False), flush=True)


class Desktop:
    def __init__(self, emit=lambda event, data: None):
        self.emit = emit
        self.lock = threading.RLock()
        self.manager = ModelManager()
        self.store = ChatStore()
        self.quota = Quota()
        self.cancel = threading.Event()
        self.download_cancel = threading.Event()
        self.generating = False
        self.downloading = None
        self.notice = ''
        self.revision = 0
        self.preferences_path = data_dir()/'desktop.json'
        self.preferences = dict(theme='system', accent='orange', density='comfortable', fontSize=16,
                                displayName=getpass.getuser(), responseTokens=192, shareProfile=True,
                                age='', location='', interests='')
        try:
            self.preferences.update(json.loads(self.preferences_path.read_text()))
        except (FileNotFoundError, ValueError):
            pass
        with self.store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS desktop_chat_archive (chat_id TEXT PRIMARY KEY, archived_at REAL NOT NULL)')
        try:
            engine = Engine(self.manager.resolve())
        except (ValueError, OSError):
            engine = Engine(DEFAULT_MODEL)
        self.session = ProfileSession(engine, Settings(max_tokens=self.preferences['responseTokens']),
                               quota=self.quota, manager=self.manager)
        self.session.profile_preferences = self.preferences
        self.session.store = self.store
        if self.store.active():
            try:
                self.session.open_chat(self.store.active())
            except (ValueError, OSError) as error:
                self.notice = str(error)

    def idle(self):
        if self.generating:
            raise ValueError('Stop the current reply before changing this conversation.')

    def chats(self, query='', archived=False):
        with self.store.connect() as db:
            hidden = {r['chat_id'] for r in db.execute('SELECT chat_id FROM desktop_chat_archive')}
        return [r for r in self.store.list(query) if (r['id'] in hidden) == bool(archived)]

    def models(self):
        values = []
        for row in self.manager.entries():
            values.append({k:row.get(k) for k in ('id','name','bytes','revision','installed_revision','update_available','description','min_app_version','license','local_only')} |
                          dict(family=row.get('family') or family_for(row['id'])))
        return values

    def chat(self):
        s = self.session
        turns = iter(s.turns)
        messages = []
        for role, text in s.messages:
            message = dict(role=role, text=text)
            if role == 'Lambda':
                turn = next(turns, {})
                message.update(model=turn.get('model'), tokens=turn.get('generated_tokens'),
                               seconds=turn.get('seconds'), finish=turn.get('finish_reason'))
            messages.append(message)
        return dict(id=s.chat_id, title=s.chat_title, modelId=s.engine.metadata.get('model_id'),
                    modelName=s.engine.metadata.get('name'), messages=messages, settings=asdict(s.settings),
                    parameters=s.engine.parameter_count, context=s.engine.context,
                    canRegenerate=bool(s.turns), notice=s.persistence_notice or self.notice)

    def state(self):
        with self.lock:
            self.revision += 1
            return dict(revision=self.revision, chat=self.chat(), chats=self.chats(), models=self.models(), quota=self.quota.status(),
                        preferences=dict(self.preferences), generating=self.generating,
                        downloading=self.downloading, engineVersion=__version__)

    def new_chat(self):
        self.idle()
        old = self.session
        if old.chat_id is not None:
            old.persist()
        self.session = ProfileSession(old.engine, Settings(max_tokens=self.preferences['responseTokens']),
                               quota=self.quota, manager=self.manager)
        self.session.profile_preferences = self.preferences
        self.session.store = self.store
        self.notice = ''

    def send(self, question, retry=False):
        with self.lock:
            self.idle()
            if retry:
                if not self.session.turns:
                    raise ValueError('There is no reply to regenerate.')
                question = self.session.prepare_revision(len(self.session.turns), kind='retry')
            if not isinstance(question, str) or not question.strip() or len(question) > 20000:
                raise ValueError('Enter a message of 1–20,000 characters.')
            self.session.add_user(question.strip())
            self.generating = True
            self.cancel.clear()
            session = self.session
        self.emit('generation-start', self.state())
        updated = 0.
        def progress(text, count):
            nonlocal updated
            now = time.monotonic()
            if now-updated >= .04 or count == 1:
                self.emit('generation-text', dict(chatId=session.chat_id, text=text, tokens=count))
                updated = now
        try:
            result = session.generate(question.strip(), progress, self.cancel,
                                      on_phase=lambda phase:self.emit('generation-phase',dict(text=phase)))
            with self.lock:
                if result.text or result.finish_reason != 'cancelled':
                    session.complete(result)
        finally:
            with self.lock:
                self.generating = False
            self.emit('generation-end', self.state())
        return self.state()

    def download(self, identifier):
        identifier = canonical_id(identifier)
        with self.lock:
            if self.downloading:
                raise ValueError('A model is already downloading. Finish or cancel that download first.')
            self.downloading = dict(id=identifier, percent=0, text='Preparing download…')
            self.download_cancel.clear()
        self.emit('download-progress', dict(self.downloading))
        def progress(message):
            match = re.search(r'(\d+)%', message)
            with self.lock:
                self.downloading = dict(id=identifier, percent=int(match[1]) if match else 0, text=message)
            self.emit('download-progress', dict(self.downloading))
        try:
            # Explicit single-model request; NEVER manager.update(), which
            # intentionally updates more than one installed model in the CLI.
            self.manager.install(identifier, progress, self.download_cancel)
        finally:
            with self.lock:
                self.downloading = None
            self.emit('download-end', self.state())
        return self.state()

    def dispatch(self, method, params):
        if method == 'state': return self.state()
        if method == 'send': return self.send(params.get('text'))
        if method == 'regenerate': return self.send('', retry=True)
        if method == 'stop':
            self.cancel.set()
            return dict(stopping=True)
        if method == 'download': return self.download(params.get('id'))
        if method == 'cancel_download':
            self.download_cancel.set()
            return dict(stopping=True)
        if method == 'refresh_catalog':
            self.manager.refresh_catalog()  # metadata only, no weights
            return self.state()
        if method == 'list_chats':
            return self.chats(str(params.get('query',''))[:500], bool(params.get('archived')))
        with self.lock:
            if method == 'new_chat':
                self.new_chat()
            elif method == 'open_chat':
                self.idle()
                self.session.open_chat(params['id'])
                self.notice = ''
            elif method == 'rename_chat':
                self.idle()
                title = params.get('title','').strip()
                if not 1 <= len(title) <= 100 or not all(c.isprintable() for c in title):
                    raise ValueError('Use a title of 1–100 printable characters.')
                row = self.store.get(params['id'])
                if row['id'] == self.session.chat_id:
                    self.session.chat_title = title
                    self.session.persist()
                else:
                    self.store.save(row['id'], row['revision'], title, row['payload'])
            elif method == 'pin_chat':
                self.store.toggle_pin(self.store.get(params['id'])['id'])
            elif method == 'delete_chat':
                self.idle()
                row = self.store.get(params['id'])
                with self.store.connect() as db:
                    db.execute('DELETE FROM chat_pins WHERE chat_id=?', (row['id'],))
                    db.execute('DELETE FROM desktop_chat_archive WHERE chat_id=?', (row['id'],))
                    db.execute("DELETE FROM chat_state WHERE key='active' AND value=?", (row['id'],))
                    db.execute('DELETE FROM chats WHERE id=?', (row['id'],))
                if row['id'] == self.session.chat_id:
                    # Do not persist the deliberately deleted conversation again.
                    self.session.chat_id = None
                    self.new_chat()
            elif method in ('archive_chat','restore_chat'):
                self.idle()
                row = self.store.get(params['id'])
                with self.store.connect() as db:
                    if method == 'archive_chat':
                        db.execute('INSERT OR REPLACE INTO desktop_chat_archive VALUES (?,?)',(row['id'],time.time()))
                    else:
                        db.execute('DELETE FROM desktop_chat_archive WHERE chat_id=?',(row['id'],))
                if method == 'archive_chat' and row['id'] == self.session.chat_id:
                    self.new_chat()
                    with self.store.connect() as db:
                        db.execute("DELETE FROM chat_state WHERE key='active' AND value=?",(row['id'],))
            elif method == 'select_model':
                self.idle()
                identifier = canonical_id(params['id'])
                row = next((r for r in self.manager.entries() if r['id']==identifier),None)
                if row is None or row.get('installed_revision') is None:
                    raise ValueError('Download this model in Settings before selecting it.')
                self.session.engine = self.manager.activate(identifier)
                # History is plain text, re-tokenized by the selected engine.
                # Old token IDs are never decoded by another model's tokenizer.
                self.session.last_result = None
                self.session.inspected_text = ''
                if self.session.chat_id is not None: self.session.persist()
            elif method == 'preferences':
                allowed = dict(theme=['system','light','dark'],accent=['orange','graphite','blue','sage','clay'],density=['comfortable','compact'])
                changed = params.get('values',{})
                for key, value in changed.items():
                    if key in allowed:
                        if value not in allowed[key]: raise ValueError('Unsupported appearance setting.')
                    elif key == 'fontSize':
                        if type(value) is not int or not 13 <= value <= 20: raise ValueError('Choose a text size between 13 and 20.')
                    elif key == 'displayName':
                        if not isinstance(value,str) or not 1 <= len(value.strip()) <= 40 or not value.isprintable(): raise ValueError('Choose a name of 1–40 characters.')
                    elif key == 'shareProfile':
                        if type(value) is not bool: raise ValueError('Choose whether to share profile information.')
                    elif key == 'age':
                        if not isinstance(value,str) or (value and (not value.isascii() or not value.isdigit() or not 1 <= int(value) <= 120)):
                            raise ValueError('Enter an age between 1 and 120, or leave it empty.')
                    elif key in ('location','interests'):
                        limit = 80 if key == 'location' else 160
                        if not isinstance(value,str) or len(value)>limit or (value and not value.isprintable()):
                            raise ValueError(f'Use up to {limit} printable characters for {key}.')
                    elif key == 'responseTokens':
                        if type(value) is not int or not 16 <= value <= 2048: raise ValueError('Choose a response limit between 16 and 2048 tokens.')
                    else: raise ValueError('Unknown preference.')
                if 'responseTokens' in changed: self.idle()
                self.preferences.update(changed)
                atomic_json(self.preferences_path,self.preferences)
                if 'responseTokens' in changed:
                    self.session.settings.max_tokens = changed['responseTokens']
                    if self.session.chat_id is not None: self.session.persist()
            else:
                raise ValueError('Unknown desktop operation.')
        return self.state()


def main():
    service = Desktop(lambda name, data:output(dict(event=name,data=data)))
    executor = ThreadPoolExecutor(max_workers=3)
    def handle(request):
        try:
            value = service.dispatch(request.get('method'),request.get('params') or {})
            output(dict(id=request.get('id'),result=value))
        except Exception as error:
            output(dict(id=request.get('id'),error=str(error)))
    output(dict(event='ready',data=dict(engineVersion=__version__)))
    try:
        for line in sys.stdin:
            try:
                request=json.loads(line)
                if not isinstance(request,dict):continue
                # Cancellation cannot queue behind generation/download requests.
                if request.get('method') in ('stop','cancel_download'):handle(request)
                else:executor.submit(handle,request)
            except (ValueError,TypeError):
                continue
    finally:
        service.cancel.set();service.download_cancel.set()
        executor.shutdown(wait=True,cancel_futures=True)


if __name__=='__main__':main()
