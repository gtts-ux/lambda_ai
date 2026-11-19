"""Persistent local image history; never modifies chats or their revision scheme."""
import base64
import json
from pathlib import Path
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from .paths import data_dir

class ImageStore:
    def __init__(self,directory=None):
        self.directory=(Path(directory) if directory is not None else data_dir())/'image-playground'
        self.directory.mkdir(parents=True,exist_ok=True)
        self.db=self.directory/'history.sqlite3'
        with self.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS images (id TEXT PRIMARY KEY, created REAL, prompt TEXT, seed INTEGER, metadata TEXT)')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.db,timeout=5)
        try:
            with db:yield db
        finally:db.close()
    def file(self,identifier):
        if not isinstance(identifier,str) or not re.fullmatch('[a-f0-9]{32}',identifier):raise ValueError('Invalid image identifier')
        return self.directory/(identifier+'.png')
    def add(self,prompt,seed,pixels,metadata):
        from PIL import Image
        identifier=uuid.uuid4().hex;path=self.file(identifier)
        try:
            Image.fromarray(pixels).save(path)
            with self.connect() as db:db.execute('INSERT INTO images VALUES (?,?,?,?,?)',(identifier,time.time(),prompt,seed,json.dumps(metadata)))
        except Exception:
            path.unlink(missing_ok=True);raise
        return identifier
    def get(self,identifier,include_image=True):
        self.file(identifier)
        with self.connect() as db:row=db.execute('SELECT id,created,prompt,seed,metadata FROM images WHERE id=?',(identifier,)).fetchone()
        if row is None:raise ValueError('Image not found on this device')
        data=dict(id=row[0],created=row[1],prompt=row[2],seed=row[3],**json.loads(row[4]))
        if include_image:
            raw=self.file(identifier).read_bytes()
            if len(raw)>1_048_576:raise ValueError('Image file is too large')
            data['dataUrl']='data:image/png;base64,'+base64.b64encode(raw).decode()
        return data
    def history(self):
        with self.connect() as db:ids=[r[0] for r in db.execute('SELECT id FROM images ORDER BY created DESC LIMIT 16')]
        result=[]
        for identifier in ids:
            try:result.append(self.get(identifier))
            except (OSError,ValueError):continue
        return result
    def delete(self,identifier):
        path=self.file(identifier)
        with self.connect() as db:db.execute('DELETE FROM images WHERE id=?',(identifier,))
        path.unlink(missing_ok=True)
