from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import APP_NAME
from .db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title=APP_NAME, lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "app": APP_NAME}
