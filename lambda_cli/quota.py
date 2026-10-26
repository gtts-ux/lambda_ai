"""Per-OS-user allowance. SQLite transactions reserve tokens across processes."""

from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import time
from uuid import uuid4

from .paths import data_dir

ALLOWANCE = 1_000_000
WINDOW_SECONDS = 10 * 60 * 60


def duration(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds//3600:02d}:{seconds%3600//60:02d}:{seconds%60:02d}"


class QuotaExceeded(ValueError):
    pass


@dataclass(frozen=True)
class Reservation:
    id: str
    input_tokens: int
    max_output: int


class Quota:
    def __init__(self, path=None, clock=None):
        self.path = Path(path) if path is not None else data_dir()/"usage.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock or time.time
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS allowance (id INTEGER PRIMARY KEY CHECK(id=1), started REAL, used INTEGER NOT NULL)")
            db.execute("INSERT OR IGNORE INTO allowance VALUES (1, NULL, 0)")
            db.execute("CREATE TABLE IF NOT EXISTS reservations (id TEXT PRIMARY KEY, amount INTEGER NOT NULL)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def refresh(self, db, now):
        started, used = db.execute("SELECT started, used FROM allowance WHERE id=1").fetchone()
        if started is not None and now >= started + WINDOW_SECONDS:
            db.execute("UPDATE allowance SET started=NULL, used=0 WHERE id=1")
            db.execute("DELETE FROM reservations")
            return None, 0
        return started, used

    def status(self):
        now = self.clock()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            started, used = self.refresh(db, now)
        reset = started + WINDOW_SECONDS if started is not None else None
        return {"allowance": ALLOWANCE, "used": used, "remaining": max(0, ALLOWANCE-used),
                "window_hours": 10, "resets_in_seconds": max(0, reset-now) if reset else None,
                "resets_at": datetime.fromtimestamp(reset, timezone.utc).isoformat() if reset else None,
                "approximate_messages": 5000, "assumed_tokens_per_message": 200,
                "enforcement": "local_per_os_user"}

    def reserve(self, input_tokens, max_output):
        if input_tokens < 0 or max_output < 1:
            raise ValueError("Invalid token reservation.")
        now = self.clock()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            started, used = self.refresh(db, now)
            available = ALLOWANCE-used-input_tokens
            if available < 1:
                reset = (started if started is not None else now) + WINDOW_SECONDS
                raise QuotaExceeded("Token allowance exhausted. Resets in " + duration(reset-now) + ".")
            output = min(max_output, available)
            identifier = uuid4().hex
            if started is None:
                db.execute("UPDATE allowance SET started=? WHERE id=1", (now,))
            amount = input_tokens + output
            db.execute("UPDATE allowance SET used=used+? WHERE id=1", (amount,))
            db.execute("INSERT INTO reservations VALUES (?, ?)", (identifier, amount))
        return Reservation(identifier, input_tokens, output)

    def complete(self, reservation, actual):
        if not 0 <= actual <= reservation.input_tokens + reservation.max_output:
            raise ValueError("Invalid token settlement.")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self.refresh(db, self.clock())
            row = db.execute("SELECT amount FROM reservations WHERE id=?", (reservation.id,)).fetchone()
            if row is not None:
                db.execute("UPDATE allowance SET used=MAX(0, used-?) WHERE id=1", (row[0]-actual,))
                db.execute("DELETE FROM reservations WHERE id=?", (reservation.id,))
