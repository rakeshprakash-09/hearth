import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from .auth import require_device
from .config import APP_NAME, FILES_DIR, MAX_TOTAL_STORAGE_MB, STORAGE_WARNING_THRESHOLD
from .db import get_db, init_db
from .routes import devices, files, messages
from . import ws

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    os.makedirs(FILES_DIR, exist_ok=True)
    yield


app = FastAPI(title=APP_NAME, lifespan=lifespan)
app.include_router(devices.router)
app.include_router(messages.router)
app.include_router(files.router)
app.include_router(ws.router)


@app.get("/health")
def health():
    return {"status": "ok", "app": APP_NAME}


@app.get("/storage")
def storage(device: sqlite3.Row = Depends(require_device), conn: sqlite3.Connection = Depends(get_db)):
    used_bytes = conn.execute("SELECT COALESCE(SUM(size_bytes), 0) AS n FROM files").fetchone()["n"]
    limit_bytes = MAX_TOTAL_STORAGE_MB * 1024 * 1024
    used_ratio = used_bytes / limit_bytes if limit_bytes else 0
    return {
        "used_bytes": used_bytes,
        "limit_bytes": limit_bytes,
        "used_ratio": used_ratio,
        "warn": used_ratio >= STORAGE_WARNING_THRESHOLD,
    }


# Registered last: a catch-all that must not shadow the API routes above.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
