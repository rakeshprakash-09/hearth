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
- [ ] Upload: enforce `MAX_FILE_SIZE_MB`, check free disk space, store as `/data/files/<uuid>`
- [ ] Download: verify requester is sender or recipient of that message before serving
- [ ] Link uploaded file to a `messages` row (`kind='file'`)

## 5. Presence tracking over WebSocket
- [ ] In-memory online-device set, updated on WS connect/disconnect
- [ ] Broadcast presence changes to connected clients
- [ ] Known-conversations query (devices ever messaged, from DB) with last-seen

## 6. Retention job + systemd timer
- [ ] `retention.py` — delete messages older than `RETENTION_DAYS`; for orphaned files, delete the file *then* the `files` row
- [ ] Seed script with fake old data to test retention before running against real messages
- [ ] `deploy/hearth-retention.service` + `deploy/hearth-retention.timer`

## 7. Frontend: device list, chat thread, attach UI
- [ ] `index.html` + `style.css` skeleton
- [ ] `app.js` — registration flow (prompt name, store token in `localStorage`)
- [ ] Device list: online-now vs known-conversations (greyed out + last-seen)
- [ ] Chat thread view + send text
- [ ] File attach button + download links

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
