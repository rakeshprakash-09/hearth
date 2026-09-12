"""WS auth-via-first-message and two-tab takeover, against a real server
subprocess (no TestClient/httpx installed, so this needs a real socket).

Run with: python -m app.test_ws
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

import websockets

from . import auth
from .db import get_connection, init_db

PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"
WS_BASE = f"ws://127.0.0.1:{PORT}"


def seed_device(conn, device_id, token):
    conn.execute(
        "INSERT INTO devices (id, name, token_hash, created_at) VALUES (?, ?, ?, ?)",
        (device_id, device_id, auth.hash_token(token), datetime.now(timezone.utc).isoformat()),
    )


def wait_for_server(timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{BASE}/health", timeout=1)
            return
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.2)
    raise TimeoutError("server did not come up in time")


def post_json(path, body, token):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


async def main():
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test.db")
    files_dir = os.path.join(tmp_dir, "files")
    os.makedirs(files_dir, exist_ok=True)

    env = os.environ.copy()
    env["HEARTH_DB_PATH"] = db_path
    env["HEARTH_FILES_DIR"] = files_dir

    init_db(db_path)
    conn = get_connection(db_path)
    seed_device(conn, "alice", "alice-token")
    seed_device(conn, "bob", "bob-token")
    conn.commit()
    conn.close()

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORT)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_server()

        # Bad token -> connection closes with 4401
        async with websockets.connect(f"{WS_BASE}/ws") as bad_ws:
            await bad_ws.send(json.dumps({"type": "auth", "token": "garbage"}))
            try:
                await asyncio.wait_for(bad_ws.recv(), timeout=5)
                raise AssertionError("expected connection to close on bad token")
            except websockets.exceptions.ConnectionClosed as e:
                assert e.rcvd.code == 4401, e.rcvd
        print("bad token correctly closed with 4401")

        # Good token -> first message is a self-inclusive presence snapshot
        async with websockets.connect(f"{WS_BASE}/ws") as alice_ws:
            await alice_ws.send(json.dumps({"type": "auth", "token": "alice-token"}))
            snapshot = json.loads(await asyncio.wait_for(alice_ws.recv(), timeout=5))
            assert snapshot["type"] == "presence" and "alice" in snapshot["online_device_ids"], snapshot
            print("good token authed, presence ack received:", snapshot)

            # Two-tab takeover: a second socket for alice, both authed
            async with websockets.connect(f"{WS_BASE}/ws") as alice_ws2:
                await alice_ws2.send(json.dumps({"type": "auth", "token": "alice-token"}))
                await asyncio.wait_for(alice_ws2.recv(), timeout=5)  # its own presence snapshot
                await asyncio.wait_for(alice_ws.recv(), timeout=5)  # first tab sees the second tab join

                post_json("/messages", {"recipient_device_id": "alice", "body": "hi from bob"}, "bob-token")

                msg1 = json.loads(await asyncio.wait_for(alice_ws.recv(), timeout=5))
                msg2 = json.loads(await asyncio.wait_for(alice_ws2.recv(), timeout=5))
                assert msg1["type"] == "message" and msg1["body"] == "hi from bob", msg1
                assert msg2["type"] == "message" and msg2["body"] == "hi from bob", msg2
        print("two-tab takeover fixed: both sockets received the message")

        print("ws self-check OK")
    finally:
        proc.terminate()
        proc.wait(timeout=10)


if __name__ == "__main__":
    asyncio.run(main())
