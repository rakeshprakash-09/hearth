import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import APP_NAME, FILES_DIR
from .db import init_db
from .routes import devices, files, messages
from . import ws


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
