import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import APP_NAME, FILES_DIR
from .db import init_db
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


# Registered last: a catch-all that must not shadow the API routes above.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
