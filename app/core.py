"""SQLite-backed task service with validation and metrics counters."""
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = os.environ.get('DB_PATH', '/data/tasks.db')
_lock = threading.RLock()


@contextmanager
def connect(db_path=None):
    path = db_path or DB_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db(db_path=None):
    with _lock, connect(db_path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)')


def validate_title(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('title'), str):
        raise ValueError('title must be a string')
    title = payload['title'].strip()
    if not (1 <= len(title) <= 120):
        raise ValueError('title must contain 1 to 120 characters')
    return title


def list_tasks(db_path=None):
    with _lock, connect(db_path) as db:
        return [dict(r) | {'done': bool(r['done'])} for r in db.execute('SELECT * FROM tasks ORDER BY id')]


def add_task(payload, db_path=None):
    title = validate_title(payload)
    stamp = datetime.now(timezone.utc).isoformat()
    with _lock, connect(db_path) as db:
        cur = db.execute('INSERT INTO tasks (title, created_at) VALUES (?, ?)', (title, stamp))
        return {'id': cur.lastrowid, 'title': title, 'done': False, 'created_at': stamp}


def update_task(task_id, payload, db_path=None):
    if not isinstance(payload, dict) or type(payload.get('done')) is not bool:
        raise ValueError('done must be a boolean')
    with _lock, connect(db_path) as db:
        cur = db.execute('UPDATE tasks SET done=? WHERE id=?', (int(payload['done']), task_id))
        if not cur.rowcount:
            return None
        row = db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
        return dict(row) | {'done': bool(row['done'])}


def delete_task(task_id, db_path=None):
    with _lock, connect(db_path) as db:
        return bool(db.execute('DELETE FROM tasks WHERE id=?', (task_id,)).rowcount)
