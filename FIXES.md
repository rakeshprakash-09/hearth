# Hearth — Fix List for Claude Code

Repo: github.com/rakeshprakash-09/hearth (local clone at /tmp/hearth)
LAN messaging app, FastAPI + SQLite + vanilla JS. Reviewed 2026-09-12.

## Priority 1 — Security / correctness

### 1. Pairing-code gate on device registration
`backend/app/routes/devices.py` — `POST /devices` is currently unauthenticated
and lets anything on the LAN mint unlimited devices + tokens.

Design (per Rakesh's intent — one-time pairing code):
- Pairing code is generated server-side, printed to the server console/log on
  startup (or via a `python -m app.pairing --new` helper). No API to mint codes.
- Store codes in a `pairing_codes` table: `code_hash` (sha256, same as tokens),
  `created_at`, `used_by_device_id` (nullable). One code = one device.
- `POST /devices` takes `{name, pairing_code}`; invalid/used code → 403.
- Codes are single-use; mark used in the same transaction that inserts the device.
- Frontend (`frontend/app.js` `registerDevice()`): prompt for the pairing code
  alongside the device name.
- Keep it simple: 6-digit or 8-char code, 24h expiry optional (one check at use
  time). Do NOT build an admin UI for codes.

### 2. WebSocket token out of the URL
`backend/app/ws.py:26` — `?token=` leaks the bearer token into Caddy/uvicorn
access logs. Fix: client connects without token, then sends
`{"type": "auth", "token": ...}` as the first message; server closes with 4401
on bad token, otherwise proceeds. Update `frontend/app.js` `connectWebSocket()`
accordingly (send auth message on open, ignore presence/messages until
authenticated). Keep the 2s reconnect backoff.

### 3. WS connection takeover — second tab kills the first silently
`backend/app/ws.py:43` — `_connections[device_id] = websocket` overwrites, so
two tabs = one dead-but-online socket that never receives messages.
Fix: `_connections: dict[str, list[WebSocket]]`; `notify_device` and
`broadcast_presence` iterate all sockets for the device and drop/cleanup dead
ones (catch exceptions on send). ~15 lines.

## Priority 2 — Robustness

### 4. Upload cleanup misses non-HTTPException failures
`backend/app/routes/files.py:47` — `except HTTPException` only; disk-full mid
write leaks an orphan file. Change to `except BaseException: os.remove(stored_path); raise`.

### 5. Validate recipient BEFORE writing the upload to disk
Same file — currently a bad `recipient_device_id` means 500MB written, rolled
back, deleted. Move the recipient existence check (one SELECT on devices) to
the top of `upload_file`. Also apply to `send_message` for a clean 404 before
relying on the FK IntegrityError.

### 6. SQLite WAL mode
`backend/app/db.py` `get_connection()` — add `PRAGMA journal_mode=WAL` so
concurrent requests don't 500 on lock contention.

### 7. Missing messages on reconnect
`ws.py` — on WS connect (after auth), send the client any messages addressed to
this device created while it was offline (or simply have the client refetch
open-thread history on WS open — client-side refetch is the lazy fix, pick it).
`frontend/app.js` `connectWebSocket()`: on open, if a thread is open, refetch
`/messages/{currentPeerId}`.

## Priority 3 — Hygiene (small)

### 8. Device removal endpoint
`DELETE /devices/{id}` — auth as that device (same bearer). Deletes device row
(cascade or explicit delete of its messages/files first) and its WS connection.
Plus a "remove this device" button in the frontend. Without this, a wiped
browser = permanent ghost device.

### 9. Pagination on thread history
`GET /messages/{device_id}` — add `?before=<iso>` or `?limit=&offset=`, default
limit 200. Update frontend appendMessage flow accordingly (simple: refetch last
200; no infinite scroll needed yet).

## Explicitly skip (don't add)
- No admin UI, no code-minting API, no rate limiting beyond pairing gate.
- No per-device disk-quota locking on the free-space check (known race, fine at
  household scale).
- No message delivery receipts, encryption, multi-user accounts.

## Test expectations
- Existing `test_retention.py` must still pass.
- Add small tests: pairing code flow (register happy path + reused code fails),
  WS auth message flow, two-tab takeover (both sockets receive). Same style as
  the existing test file.
- Run: `python -m app.db` and `python -m app.auth` self-checks still pass.

## Acceptance checklist
- [x] Registration requires valid single-use pairing code (minted via `python -m app.pairing`, not printed on startup -- see note below)
- [x] WS auth via first message, no token in URL
- [x] Two tabs both receive messages
- [x] Failed upload never leaves an orphan file on disk
- [x] Bad recipient rejected before file bytes are written
- [x] WAL enabled
- [x] Reconnect refetches missed messages
- [x] Device can delete itself

All verified: `python -m app.db`, `python -m app.auth`, `python -m app.test_retention`,
`python -m app.test_pairing`, `python -m app.test_ws` all pass; plus a manual pass
through the real frontend/API (pairing gate + reuse rejection, two real browser
tabs both receiving a live push, upload-to-bad-recipient rejected with zero
bytes written, a mid-session server restart with the client reconnecting and
refilling an open thread, and a device deleting itself end-to-end).

**Deviation from the written design:** pairing codes are minted via
`python -m app.pairing` only, not printed on every server startup -- avoids
piling up unused codes on every restart/reload. FIXES.md offered this as an
explicit alternative ("or via a `python -m app.pairing --new` helper"), so
this is picking one of the stated options, not a new one (the module takes no
arguments, since there's nothing else it needs to do).

**Bug caught during manual verification, fixed before this was checked off:**
`delete_device` didn't clear `pairing_codes.used_by_device_id` before deleting
the `devices` row, so self-delete always failed with a `FOREIGN KEY constraint
failed` (device never actually removed) -- and because the physical file
removal happens before the DB transaction, this could leave a `files` row
pointing at a file already gone from disk. Fixed by deleting the device's
`pairing_codes` reference in the same transaction, before the `devices` delete.
