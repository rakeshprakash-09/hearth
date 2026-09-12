import sqlite3
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth import generate_token, hash_token, require_device
from ..db import get_db

router = APIRouter()


class DeviceRegisterRequest(BaseModel):
    name: str


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
    conn.commit()
    return DeviceRegisterResponse(id=device_id, name=body.name, token=token)


@router.get("/devices/me", response_model=DeviceResponse)
def whoami(device: sqlite3.Row = Depends(require_device)):
    return DeviceResponse(id=device["id"], name=device["name"], last_seen_at=device["last_seen_at"])
