import os
import sqlite3
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from .. import pairing, ws
from ..auth import generate_token, hash_token, require_device
from ..db import get_db

router = APIRouter()


class DeviceRegisterRequest(BaseModel):
    name: str
    pairing_code: str


class DeviceRegisterResponse(BaseModel):
    id: str
    name: str
    token: str


class DeviceResponse(BaseModel):
    id: str
    name: str
    last_seen_at: str | None


@router.post("/devices", response_model=DeviceRegisterResponse)
def register_device(body: DeviceRegisterRequest, conn: sqlite3.Connection = Depends(get_db)):
    device_id = str(uuid.uuid4())
    token = generate_token()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO devices (id, name, token_hash, created_at, last_seen_at) VALUES (?, ?, ?, ?, ?)",
        (device_id, body.name, hash_token(token), now, now),
    )
    if not pairing.redeem_pairing_code(conn, body.pairing_code, device_id):
        conn.rollback()
        raise HTTPException(403, "invalid or already-used pairing code")
    conn.commit()
    return DeviceRegisterResponse(id=device_id, name=body.name, token=token)


@router.get("/devices/me", response_model=DeviceResponse)
def whoami(device: sqlite3.Row = Depends(require_device)):
    return DeviceResponse(id=device["id"], name=device["name"], last_seen_at=device["last_seen_at"])


@router.get("/devices", response_model=list[DeviceResponse])
def list_devices(device: sqlite3.Row = Depends(require_device), conn: sqlite3.Connection = Depends(get_db)):
    # At household scale, every registered device is worth showing (not just
    # ones already messaged) -- otherwise there's no way to start a first
    # conversation with a device, which is the app's core use case.
    rows = conn.execute(
        "SELECT id, name, last_seen_at FROM devices WHERE id != ? ORDER BY name", (device["id"],)
    ).fetchall()
    return [DeviceResponse(**dict(row)) for row in rows]


@router.delete("/devices/{device_id}", status_code=204)
def delete_device(
    device_id: str,
    background_tasks: BackgroundTasks,
    device: sqlite3.Row = Depends(require_device),
    conn: sqlite3.Connection = Depends(get_db),
) -> None:
    if device_id != device["id"]:
        raise HTTPException(403, "can only delete your own device")

    files = conn.execute("SELECT stored_path FROM files WHERE uploaded_by = ?", (device["id"],)).fetchall()
    for file_row in files:
        if os.path.exists(file_row["stored_path"]):
            os.remove(file_row["stored_path"])

    conn.execute(
        "DELETE FROM messages WHERE sender_device_id = ? OR recipient_device_id = ?",
        (device["id"], device["id"]),
    )
    conn.execute("DELETE FROM files WHERE uploaded_by = ?", (device["id"],))
    conn.execute("DELETE FROM pairing_codes WHERE used_by_device_id = ?", (device["id"],))
    conn.execute("DELETE FROM devices WHERE id = ?", (device["id"],))
    conn.commit()

    background_tasks.add_task(ws.disconnect_device, device["id"])
