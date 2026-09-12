# Hearth — Tasks

Tracking checklist for v1, broken down from the build order in `hearth-plan.md` (§9). Check items off as you go; update `hearth-plan.md` only if scope actually changes.

## 1. Scaffold FastAPI + SQLite schema
- [x] `backend/requirements.txt` (fastapi, uvicorn)
- [x] `config.py` — `RETENTION_DAYS`, `MAX_FILE_SIZE_MB`, app name, loaded from `.env`
- [x] `db.py` — SQLite connection + schema creation (`devices`, `messages`, `files`)
- [x] `main.py` — app entrypoint, mounts routers

## 2. Device registration + token auth middleware
- [x] `POST /devices` — create device row, generate token (`secrets.token_urlsafe(32)`), return once
- [x] `auth.py` — bearer token verification (check against `token_hash`)
- [x] Apply auth check to every REST route and the WebSocket handshake (WS token passed as a `?token=` query param — browsers can't set headers on a WS handshake)

## 3. Text messaging (REST + WebSocket push)
- [x] `POST /messages` — persist a text message
- [x] `GET /messages/{device_id}` — fetch thread history
- [x] `ws.py` — push new message to recipient if their socket is connected
- [ ] Frontend: request `Notification` permission and fire a browser notification on incoming WS message (no service worker — tab must be open) — deferred to step 7 when the frontend/WS client actually exists

## 4. File upload/download with limits
- [x] Upload: enforce `MAX_FILE_SIZE_MB`, check free disk space, store as `/data/files/<uuid>`
- [x] Download: verify requester is sender or recipient of that message before serving
- [x] Link uploaded file to a `messages` row (`kind='file'`)

## 5. Presence tracking over WebSocket
- [x] In-memory online-device set, updated on WS connect/disconnect
- [x] Broadcast presence changes to connected clients
- [x] Device list query with last-seen — revised from "only devices ever messaged" to "every other registered device": at household scale there's no clutter concern, and filtering to messaged-only left no way to start a first conversation

## 6. Retention job + systemd timer
- [x] `retention.py` — delete messages older than `RETENTION_DAYS`; for orphaned files, delete the file *then* the `files` row
- [x] Seed script with fake old data to test retention before running against real messages
- [x] `deploy/hearth-retention.service` + `deploy/hearth-retention.timer`

## 7. Frontend: device list, chat thread, attach UI
- [x] `index.html` + `style.css` skeleton
- [x] `app.js` — registration flow (prompt name, store token in `localStorage`)
- [x] Device list: online (live via WS presence) vs offline w/ last-seen, showing every registered device (see step 5 note)
- [x] Chat thread view + send text
- [x] File attach button + download links (fetch + blob, not a plain link, so the bearer token never ends up in a URL/browser history)
- [x] Browser `Notification` nudge on incoming message when the tab is hidden (deferred here from step 3)

## 8. Caddy + mkcert HTTPS
- [ ] Generate local CA + cert for `homebot.local` via `mkcert`
- [ ] `deploy/Caddyfile` — reverse proxy to Uvicorn
- [ ] Trust root cert on each family device (phone + laptop)

## 9. Deploy as systemd service on homebot
- [ ] `deploy/hearth.service`
- [ ] Enable + start, verify running
- [ ] Reboot homebot, confirm auto-start

## 10. Family dogfood week
- [ ] One week of real use
- [ ] Review actual usage vs `RETENTION_DAYS` / `MAX_FILE_SIZE_MB`, tune `.env`

---

## v2 backlog (not started)

See `hearth-plan.md` §"v2" for full detail — not broken into subtasks yet:

- [ ] Multi-device-per-person identity
- [ ] Group chats / rooms
- [ ] PWA install + best-effort notifications
- [ ] Admin view (storage, per-device stats, manual purge)
- [ ] Nightly backup of `hearth.db` + `/data/files`
- [ ] Message search
- [ ] Read receipts / typing indicators
- [ ] Inline image/video preview
- [ ] At-rest encryption of message bodies
- [ ] Per-device rate limiting
