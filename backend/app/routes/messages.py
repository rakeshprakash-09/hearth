import sqlite3
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel

from .. import ws
from ..auth import require_device
from ..db import get_db

router = APIRouter()


class SendMessageRequest(BaseModel):
    recipient_device_id: str
    body: str


class MessageResponse(BaseModel):
    id: str
    sender_device_id: str
    recipient_device_id: str
    kind: str
    body: str | None
    file_id: str | None
    filename: str | None
    created_at: str


@router.post("/messages", response_model=MessageResponse)
def send_message(
    body: SendMessageRequest,
    background_tasks: BackgroundTasks,
    device: sqlite3.Row = Depends(require_device),
    conn: sqlite3.Connection = Depends(get_db),
):
    message = {
        "id": str(uuid.uuid4()),
        "sender_device_id": device["id"],
        "recipient_device_id": body.recipient_device_id,
        "kind": "text",
        "body": body.body,
        "file_id": None,
        "filename": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        conn.execute(
            """INSERT INTO messages
               (id, sender_device_id, recipient_device_id, kind, body, file_id, created_at)
               VALUES (:id, :sender_device_id, :recipient_device_id, :kind, :body, :file_id, :created_at)""",
            message,
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(404, "recipient not found")

    background_tasks.add_task(ws.notify_device, body.recipient_device_id, message)
    return MessageResponse(**message)


@router.get("/messages/{device_id}", response_model=list[MessageResponse])
def get_thread(
    device_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    device: sqlite3.Row = Depends(require_device),
    conn: sqlite3.Connection = Depends(get_db),
):
    rows = conn.execute(
        """SELECT m.*, f.filename AS filename
           FROM messages m
           LEFT JOIN files f ON f.id = m.file_id
           WHERE (m.sender_device_id = ? AND m.recipient_device_id = ?)
              OR (m.sender_device_id = ? AND m.recipient_device_id = ?)
           ORDER BY m.created_at DESC LIMIT ?""",
        (device["id"], device_id, device_id, device["id"], limit),
    ).fetchall()
    return [MessageResponse(**dict(row)) for row in reversed(rows)]
