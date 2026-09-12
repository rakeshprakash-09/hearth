from datetime import datetime, timezone

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from .auth import get_device_by_token
from .db import get_connection

router = APIRouter()

_connections: dict[str, WebSocket] = {}


async def notify_device(device_id: str, payload: dict) -> None:
    websocket = _connections.get(device_id)
    if websocket is not None:
        await websocket.send_json(payload)


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, token: str = Query(...)):
    conn = get_connection()
    device = get_device_by_token(conn, token)
    if device is not None:
        conn.execute(
            "UPDATE devices SET last_seen_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), device["id"]),
        )
        conn.commit()
    conn.close()

    if device is None:
        await websocket.close(code=4401)
        return

    device_id = device["id"]
    await websocket.accept()
    _connections[device_id] = websocket
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if _connections.get(device_id) is websocket:
            del _connections[device_id]
