"""Seeds a throwaway DB with old/new messages and files, then asserts
retention.run() only removes what's past RETENTION_DAYS and correctly
sweeps orphaned files while leaving still-referenced ones alone.

Run with: python -m app.test_retention
"""

import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone

from . import config, retention
from .db import get_connection, init_db


def seed_device(conn, device_id):
    conn.execute(
        "INSERT INTO devices (id, name, token_hash, created_at) VALUES (?, ?, ?, ?)",
        (device_id, device_id, "unused", datetime.now(timezone.utc).isoformat()),
    )


def seed_file(conn, files_dir, file_id, content):
    path = os.path.join(files_dir, file_id)
    with open(path, "wb") as f:
        f.write(content)
    conn.execute(
        "INSERT INTO files (id, filename, stored_path, size_bytes, mime_type, uploaded_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (file_id, "f.bin", path, len(content), "application/octet-stream", "a", datetime.now(timezone.utc).isoformat()),
    )
    return path


def seed_message(conn, kind, created_at, file_id=None, body=None):
    conn.execute(
        """INSERT INTO messages (id, sender_device_id, recipient_device_id, kind, body, file_id, created_at)
           VALUES (?, 'a', 'b', ?, ?, ?, ?)""",
        (str(uuid.uuid4()), kind, body, file_id, created_at.isoformat()),
    )


def main():
    tmp_dir = tempfile.mkdtemp()
    config.DB_PATH = os.path.join(tmp_dir, "test.db")
    config.FILES_DIR = os.path.join(tmp_dir, "files")
    os.makedirs(config.FILES_DIR, exist_ok=True)
    init_db()

    now = datetime.now(timezone.utc)
    old = now - timedelta(days=config.RETENTION_DAYS + 1)
    new = now - timedelta(days=1)

    conn = get_connection()
    seed_device(conn, "a")
    seed_device(conn, "b")

    f1_path = seed_file(conn, config.FILES_DIR, "f1", b"old orphan")
    f2_path = seed_file(conn, config.FILES_DIR, "f2", b"still referenced")

    seed_message(conn, "text", old, body="old text")
    seed_message(conn, "text", new, body="new text")
    seed_message(conn, "file", old, file_id="f1")
    seed_message(conn, "file", old, file_id="f2")
    seed_message(conn, "file", new, file_id="f2")
    conn.commit()
    conn.close()

    summary = retention.run(now=now)
    print("first run:", summary)
    assert summary == {"messages_deleted": 3, "files_deleted": 1, "bytes_freed": len(b"old orphan")}, summary

    assert not os.path.exists(f1_path), "orphaned file should be deleted from disk"
    assert os.path.exists(f2_path), "still-referenced file must survive"

    conn = get_connection()
    remaining = conn.execute("SELECT kind, body FROM messages ORDER BY created_at").fetchall()
    assert [dict(r) for r in remaining] == [
        {"kind": "text", "body": "new text"},
        {"kind": "file", "body": None},
    ], remaining
    remaining_file_ids = [r["id"] for r in conn.execute("SELECT id FROM files").fetchall()]
    assert remaining_file_ids == ["f2"], remaining_file_ids
    conn.close()

    second = retention.run(now=now)
    print("second run (idempotent):", second)
    assert second == {"messages_deleted": 0, "files_deleted": 0, "bytes_freed": 0}, second

    print("retention self-check OK")


if __name__ == "__main__":
    main()
