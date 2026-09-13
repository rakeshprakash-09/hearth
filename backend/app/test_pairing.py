"""Pairing-code gate: happy path, reused code rejected, bogus code rejected,
and a concurrent-redemption race where exactly one of two racers should win.

Run with: python -m app.test_pairing
"""

import os
import tempfile
import threading
from datetime import datetime, timezone

from fastapi import HTTPException

from . import config, pairing
from .db import get_connection, init_db
from .routes.devices import DeviceRegisterRequest, register_device


def device_count(conn) -> int:
    return conn.execute("SELECT COUNT(*) AS n FROM devices").fetchone()["n"]


def main():
    tmp_dir = tempfile.mkdtemp()
    config.DB_PATH = os.path.join(tmp_dir, "test.db")
    config.FILES_DIR = os.path.join(tmp_dir, "files")
    os.makedirs(config.FILES_DIR, exist_ok=True)
    init_db()

    conn = get_connection()

    # Happy path
    code = pairing.create_pairing_code(conn)
    resp = register_device(DeviceRegisterRequest(name="phone", pairing_code=code), conn)
    assert resp.token, resp
    assert device_count(conn) == 1, device_count(conn)
    print("happy path OK:", resp.id)

    # Reused code -> 403, and the orphaned device insert must be rolled back
    try:
        register_device(DeviceRegisterRequest(name="laptop", pairing_code=code), conn)
        raise AssertionError("expected 403 for reused pairing code")
    except HTTPException as e:
        assert e.status_code == 403, e.status_code
    assert device_count(conn) == 1, device_count(conn)
    print("reused code correctly rejected, no orphan device row")

    # Bogus/never-issued code -> 403
    try:
        register_device(DeviceRegisterRequest(name="tablet", pairing_code="NOTREAL1"), conn)
        raise AssertionError("expected 403 for bogus pairing code")
    except HTTPException as e:
        assert e.status_code == 403, e.status_code
    assert device_count(conn) == 1, device_count(conn)
    print("bogus code correctly rejected")
    conn.close()

    # Concurrent redemption: two threads race to redeem the same fresh code;
    # exactly one should win. used_by_device_id is an FK, so both racing
    # devices must already exist.
    conn2 = get_connection()
    race_code = pairing.create_pairing_code(conn2)
    now = datetime.now(timezone.utc).isoformat()
    for device_id in ("race-device-1", "race-device-2"):
        conn2.execute(
            "INSERT INTO devices (id, name, token_hash, created_at) VALUES (?, ?, 'unused', ?)",
            (device_id, device_id, now),
        )
    conn2.commit()
    conn2.close()

    results = []

    def racer(device_id):
        conn = get_connection()
        results.append(pairing.redeem_pairing_code(conn, race_code, device_id))
        conn.commit()
        conn.close()

    t1 = threading.Thread(target=racer, args=("race-device-1",))
    t2 = threading.Thread(target=racer, args=("race-device-2",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert sorted(results) == [False, True], results
    print("concurrent redemption: exactly one winner, as expected")

    # HEARTH_PAIRING_CODE override
    config.PAIRING_CODE = "fixed123"
    assert pairing.generate_code() == "FIXED123"
    config.PAIRING_CODE = ""
    assert pairing.generate_code() != "FIXED123"
    print("pairing code override OK")

    print("pairing self-check OK")


if __name__ == "__main__":
    main()
