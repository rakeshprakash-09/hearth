import sqlite3

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    last_seen_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    mime_type TEXT,
    uploaded_by TEXT REFERENCES devices(id),
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    sender_device_id TEXT NOT NULL REFERENCES devices(id),
    recipient_device_id TEXT NOT NULL REFERENCES devices(id),
    kind TEXT NOT NULL CHECK (kind IN ('text', 'file')),
    body TEXT,
    file_id TEXT REFERENCES files(id),
    created_at TIMESTAMP NOT NULL
);
"""


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: str | None = None) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    import os
    import tempfile

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        init_db(path)
        conn = get_connection(path)
        tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert {"devices", "files", "messages"} <= tables, tables
        print("db self-check OK:", tables)
    finally:
        os.remove(path)
