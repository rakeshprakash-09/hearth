import os
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from .. import ws
from ..auth import require_device
from ..config import FILES_DIR, MAX_FILE_SIZE_MB
from ..db import get_db
from .messages import MessageResponse, insert_message

router = APIRouter()

MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
CHUNK_SIZE = 1024 * 1024


@router.post("/files", response_model=MessageResponse)
def upload_file(
    background_tasks: BackgroundTasks,
    recipient_device_id: str = Form(...),
    file: UploadFile = File(...),
    device: sqlite3.Row = Depends(require_device),
    conn: sqlite3.Connection = Depends(get_db),
):
    if conn.execute("SELECT id FROM devices WHERE id = ?", (recipient_device_id,)).fetchone() is None:
        raise HTTPException(404, "recipient not found")

    os.makedirs(FILES_DIR, exist_ok=True)
    if shutil.disk_usage(FILES_DIR).free < MAX_FILE_SIZE_BYTES:
        raise HTTPException(status.HTTP_507_INSUFFICIENT_STORAGE, "not enough free disk space on homebot")

    file_id = str(uuid.uuid4())
    stored_path = os.path.join(FILES_DIR, file_id)
    size = 0
    try:
        with open(stored_path, "wb") as out:
            while chunk := file.file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > MAX_FILE_SIZE_BYTES:
                    raise HTTPException(
                        status.HTTP_413_CONTENT_TOO_LARGE,
                        f"file exceeds {MAX_FILE_SIZE_MB}MB limit",
                    )
                out.write(chunk)
    except BaseException:
        os.remove(stored_path)
        raise

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO files (id, filename, stored_path, size_bytes, mime_type, uploaded_by, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (file_id, file.filename, stored_path, size, file.content_type, device["id"], now),
    )

    message = {
        "id": str(uuid.uuid4()),
        "sender_device_id": device["id"],
        "recipient_device_id": recipient_device_id,
        "kind": "file",
        "body": None,
        "file_id": file_id,
        "filename": file.filename,
        "created_at": now,
    }
    try:
        insert_message(conn, message)
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        os.remove(stored_path)
        raise HTTPException(404, "recipient not found")

    background_tasks.add_task(ws.notify_device, recipient_device_id, message)
    return MessageResponse(**message)


@router.get("/files/{file_id}")
def download_file(
    file_id: str,
    device: sqlite3.Row = Depends(require_device),
    conn: sqlite3.Connection = Depends(get_db),
):
    file_row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    if file_row is None:
        raise HTTPException(404, "file not found")

    message_row = conn.execute("SELECT * FROM messages WHERE file_id = ?", (file_id,)).fetchone()
    if message_row is None or device["id"] not in (
        message_row["sender_device_id"],
        message_row["recipient_device_id"],
    ):
        raise HTTPException(403, "not authorized to download this file")

    return FileResponse(file_row["stored_path"], filename=file_row["filename"], media_type=file_row["mime_type"])
