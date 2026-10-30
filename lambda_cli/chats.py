"""Local conversation snapshots. Models and the shared token ledger are separate."""
from contextlib import contextmanager
import json
from pathlib import Path
import re
import sqlite3
import time
from uuid import uuid4
from .paths import data_dir


class ChatConflict(ValueError):
    pass


class ChatStore:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else data_dir()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory/'chats.sqlite3'
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS chats (id TEXT PRIMARY KEY, title TEXT NOT NULL, '
                       'created REAL NOT NULL, updated REAL NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL, '
                       'model_name TEXT NOT NULL, turns INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS chat_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            # A separate table keeps older running app windows compatible.
            db.execute('CREATE TABLE IF NOT EXISTS chat_pins (chat_id TEXT PRIMARY KEY, pinned INTEGER NOT NULL)')

    @contextmanager
    def connect(self):
        db = None
        try:
            db = sqlite3.connect(self.path, timeout=10)
            db.row_factory = sqlite3.Row
            with db:
                yield db
        except sqlite3.Error as error:
            raise ValueError(f'Local chat storage failed: {error}') from error
        finally:
            if db is not None:
                db.close()

    def active(self):
        with self.connect() as db:
            row = db.execute("SELECT value FROM chat_state WHERE key='active'").fetchone()
        return row['value'] if row else None

    def set_active(self, identifier):
        with self.connect() as db:
            if not db.execute('SELECT id FROM chats WHERE id=?', (identifier,)).fetchone():
                raise ValueError('That local chat no longer exists.')
            db.execute("INSERT OR REPLACE INTO chat_state VALUES ('active',?)", (identifier,))

    def create(self, payload, title='New chat'):
        identifier, now = uuid4().hex, time.time()
        raw = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        with self.connect() as db:
            db.execute('INSERT INTO chats VALUES (?,?,?,?,?,?,?,?)',
                       (identifier, title, now, now, 1, raw, payload.get('model_name') or 'Local model', len(payload['turns'])))
            db.execute("INSERT OR REPLACE INTO chat_state VALUES ('active',?)", (identifier,))
        return self.get(identifier)

    def get(self, reference):
        if not isinstance(reference, str) or not re.fullmatch(r'[0-9a-f]{8,32}', reference):
            raise ValueError('Use a chat number or the ID shown in /chats.')
        with self.connect() as db:
            rows = db.execute('SELECT * FROM chats WHERE id LIKE ?', (reference+'%',)).fetchall()
        if len(rows) != 1:
            raise ValueError('Chat not found.' if not rows else 'Chat ID is ambiguous; use its full ID.')
        row = dict(rows[0])
        try:
            row['payload'] = json.loads(row['payload'])
        except json.JSONDecodeError as error:
            raise ValueError('This chat contains unreadable data. Other chats are preserved.') from error
        return row

    def list(self, query=''):
        # Read summaries without copying every token array into the UI on each render.
        with self.connect() as db:
            columns = 'c.id,c.title,c.created,c.updated,c.revision,c.model_name,c.turns,COALESCE(p.pinned,0) AS pinned'
            if query:
                columns += ',c.payload'
            cursor = db.execute('SELECT '+columns+' FROM chats c LEFT JOIN chat_pins p ON p.chat_id=c.id '
                                'ORDER BY COALESCE(p.pinned,0) DESC,c.updated DESC,c.id')
            rows=[]
            needle=query.casefold()
            for row in cursor:
                row=dict(row)
                if query:
                    raw=row.pop('payload')
                    try:
                        payload=json.loads(raw)
                        text='\n'.join(str(message[1]) for message in payload.get('messages',[]) if isinstance(message,(list,tuple)) and len(message)==2)
                    except (json.JSONDecodeError,AttributeError):
                        text=''
                    if needle not in (row['title']+'\n'+text).casefold():
                        continue
                rows.append(row)
        return rows

    def toggle_pin(self, identifier):
        with self.connect() as db:
            if not db.execute('SELECT id FROM chats WHERE id=?',(identifier,)).fetchone():
                raise ValueError('Chat not found.')
            row=db.execute('SELECT pinned FROM chat_pins WHERE chat_id=?',(identifier,)).fetchone()
            value=0 if row and row['pinned'] else 1
            db.execute('INSERT OR REPLACE INTO chat_pins VALUES (?,?)',(identifier,value))
        return bool(value)

    def save(self, identifier, revision, title, payload):
        raw = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        with self.connect() as db:
            changed = db.execute('UPDATE chats SET title=?,updated=?,revision=revision+1,payload=?,model_name=?,turns=? '
                                 'WHERE id=? AND revision=?',
                                 (title, time.time(), raw, payload.get('model_name') or 'Local model', len(payload['turns']), identifier, revision)).rowcount
            if changed != 1:
                raise ChatConflict('This chat changed in another window.')
        return revision+1
