from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .auth import get_device_by_token
from .db import get_connection

router = APIRouter()

_connections: dict[str, list[WebSocket]] = {}


def _remove_connection(device_id: str, websocket: WebSocket) -> None:
    sockets = _connections.get(device_id)
    if not sockets:
        return
    if websocket in sockets:
        sockets.remove(websocket)
    if not sockets:
        del _connections[device_id]


async def _send_to_device(device_id: str, payload: dict) -> None:
    dead = []
    for socket in list(_connections.get(device_id, [])):
        try:
            await socket.send_json(payload)
        except Exception:
            dead.append(socket)
    for socket in dead:
        _remove_connection(device_id, socket)


async def notify_device(device_id: str, payload: dict) -> None:
    await _send_to_device(device_id, {"type": "message", **payload})


async def broadcast_presence() -> None:
    payload = {"type": "presence", "online_device_ids": list(_connections.keys())}
    for device_id in list(_connections.keys()):
        await _send_to_device(device_id, payload)


async def disconnect_device(device_id: str) -> None:
    for socket in list(_connections.get(device_id, [])):
        await socket.close(code=4401)
    _connections.pop(device_id, None)


async def _authenticate(websocket: WebSocket) -> str | None:
    try:
        auth_message = await websocket.receive_json()
    except Exception:
        await websocket.close(code=4401)
        return None

    if not isinstance(auth_message, dict) or auth_message.get("type") != "auth":
        await websocket.close(code=4401)
        return None

    conn = get_connection()
    try:
        device = get_device_by_token(conn, auth_message.get("token", ""))
        if device is None:
            await websocket.close(code=4401)
            return None
        conn.execute(
            "UPDATE devices SET last_seen_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), device["id"]),
        )
        conn.commit()
        return device["id"]
    finally:
        conn.close()


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    device_id = await _authenticate(websocket)
    if device_id is None:
        return

    _connections.setdefault(device_id, []).append(websocket)
    await broadcast_presence()
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _remove_connection(device_id, websocket)
        await broadcast_presence()
