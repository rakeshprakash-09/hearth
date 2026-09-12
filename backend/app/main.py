from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import APP_NAME
from .db import init_db
from .routes import devices


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title=APP_NAME, lifespan=lifespan)
app.include_router(devices.router)


@app.get("/health")
def health():
    return {"status": "ok", "app": APP_NAME}
