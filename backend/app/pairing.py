import secrets
import sqlite3
from datetime import datetime, timezone

from . import config
from .auth import hash_token

CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # no 0/O/1/I, hard to misread
CODE_LENGTH = 8


def generate_code() -> str:
    if config.PAIRING_CODE:
        return config.PAIRING_CODE.strip().upper()
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def _normalize(code: str) -> str:
    return code.strip().upper()


def create_pairing_code(conn: sqlite3.Connection) -> str:
    code = generate_code()
    conn.execute(
        "INSERT INTO pairing_codes (code_hash, created_at) VALUES (?, ?)",
        (hash_token(_normalize(code)), datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    return code


def redeem_pairing_code(conn: sqlite3.Connection, code: str, device_id: str) -> bool:
    if config.PAIRING_CODE and _normalize(code) == _normalize(config.PAIRING_CODE):
        return True  # reusable default code: not single-use, no DB row needed
    cursor = conn.execute(
        "UPDATE pairing_codes SET used_by_device_id = ? WHERE code_hash = ? AND used_by_device_id IS NULL",
        (device_id, hash_token(_normalize(code))),
    )
    return cursor.rowcount == 1


if __name__ == "__main__":
    from .db import get_connection, init_db

    init_db()
    conn = get_connection()
    code = create_pairing_code(conn)
    conn.close()
    print(f"New pairing code (single use): {code}")
