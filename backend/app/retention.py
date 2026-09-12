import os
from datetime import datetime, timedelta, timezone

from . import config
from .db import get_connection


def run(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=config.RETENTION_DAYS)).isoformat()

    conn = get_connection()
    try:
        cursor = conn.execute("DELETE FROM messages WHERE created_at < ?", (cutoff,))
        messages_deleted = cursor.rowcount
        conn.commit()

        # Re-check the whole files table, not just what this run touched, so any
        # orphan left behind by a prior crash gets swept up too.
        orphaned = conn.execute(
            "SELECT * FROM files WHERE id NOT IN (SELECT file_id FROM messages WHERE file_id IS NOT NULL)"
        ).fetchall()

        bytes_freed = 0
        for file_row in orphaned:
            if os.path.exists(file_row["stored_path"]):
                bytes_freed += file_row["size_bytes"]
                os.remove(file_row["stored_path"])
            conn.execute("DELETE FROM files WHERE id = ?", (file_row["id"],))
        conn.commit()
    finally:
        conn.close()

    return {
        "messages_deleted": messages_deleted,
        "files_deleted": len(orphaned),
        "bytes_freed": bytes_freed,
    }


if __name__ == "__main__":
    summary = run()
    print(
        f"retention: deleted {summary['messages_deleted']} messages, "
        f"{summary['files_deleted']} files, freed {summary['bytes_freed']} bytes"
    )
