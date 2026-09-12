import hashlib
import secrets
import sqlite3
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, status

from .db import get_db


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def get_device_by_token(conn: sqlite3.Connection, token: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM devices WHERE token_hash = ?", (hash_token(token),)
    ).fetchone()


def require_device(
    authorization: str | None = Header(default=None),
    conn: sqlite3.Connection = Depends(get_db),
) -> sqlite3.Row:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    device = get_device_by_token(conn, authorization.removeprefix("Bearer "))
    if device is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    conn.execute(
        "UPDATE devices SET last_seen_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), device["id"]),
    )
    conn.commit()
    return device


if __name__ == "__main__":
    t1, t2 = generate_token(), generate_token()
    assert t1 != t2
    assert hash_token(t1) == hash_token(t1)
    assert hash_token(t1) != hash_token(t2)
    assert len(hash_token(t1)) == 64
    print("auth self-check OK")
