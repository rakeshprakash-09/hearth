# Hearth — Plan

*A persistent chat and file-sharing hub for your home network, hosted on homebot.*

> **Name:** going with **Hearth** as the working name — a home network's gathering point, and it doesn't collide with the Hermes agent already running on homebot. It's a single config constant, so renaming later (e.g. to `Nook` or `LANtern`) costs nothing. Swap it in `backend/app/config.py` and the systemd unit name if you want something else.

---

## 1. What this is

A web app hosted on homebot. Any device on the home Wi-Fi opens `https://homebot.local:PORT`, registers itself once, and from then on appears in everyone else's device list. DMs and files persist in a database on homebot, are visible only to the two devices in that conversation, and are purged automatically after a configurable retention window.

## 2. Architecture at a glance

```
 ┌─────────────┐        HTTPS/WSS         ┌───────────────────────────┐
 │  Any device  │ ───────────────────────▶ │  homebot                  │
 │  (browser)   │ ◀─────────────────────── │  Caddy (TLS) → FastAPI    │
 └─────────────┘                           │   ├─ REST API              │
                                            │   ├─ WebSocket (presence + │
                                            │   │   live messages)       │
                                            │   ├─ SQLite (messages,     │
                                            │   │   devices, files meta) │
                                            │   └─ /data/files (blobs)   │
                                            │  systemd timer → nightly   │
                                            │   retention job            │
                                            └───────────────────────────┘
```

**Stack:**
- **Backend:** Python 3.12 + FastAPI + Uvicorn — native WebSocket support, tiny footprint, fits homebot's 5GB RAM comfortably.
- **DB:** SQLite — zero admin, plenty for household scale.
- **Frontend:** plain HTML/CSS/JS, no build step — keeps deployment on homebot dead simple (no Node toolchain needed on the box itself).
- **TLS:** Caddy as reverse proxy with a locally-trusted cert (via `mkcert`) — unlocks secure-context browser features and stops tokens going over Wi-Fi in plaintext.
- **Retention job:** a standalone script run by a systemd timer, not inside the web process — easier to test and debug in isolation.

## 3. Data model

```sql
devices (
  id            TEXT PRIMARY KEY,   -- uuid
  name          TEXT NOT NULL,      -- "Rakesh's laptop"
  token_hash    TEXT NOT NULL,      -- sha256 of the bearer token; raw token shown once at registration
  created_at    TIMESTAMP,
  last_seen_at  TIMESTAMP
)

messages (
  id                  TEXT PRIMARY KEY,
  sender_device_id    TEXT REFERENCES devices(id),
  recipient_device_id TEXT REFERENCES devices(id),
  kind                TEXT,          -- 'text' | 'file'
  body                TEXT,          -- text content, null for file messages
  file_id             TEXT REFERENCES files(id),  -- null for text messages
  created_at          TIMESTAMP
)

files (
  id            TEXT PRIMARY KEY,
  filename      TEXT NOT NULL,
  stored_path   TEXT NOT NULL,       -- path under /data/files
  size_bytes    INTEGER NOT NULL,
  mime_type     TEXT,
  uploaded_by   TEXT REFERENCES devices(id),
  created_at    TIMESTAMP
)
```

Retention window and max file size live in a `.env` on homebot (`RETENTION_DAYS`, `MAX_FILE_SIZE_MB`) — not hardcoded, so you can tune them without a redeploy.

## 4. Auth & identity (the part v0 of the idea was missing)

- First visit → prompt for a device name → server creates a `devices` row, generates a random token (`secrets.token_urlsafe(32)`), returns it once, client stores it in `localStorage`.
- Every REST call and the WebSocket connection send that token as a bearer credential. The server checks it against `token_hash` before trusting *any* claim about who's messaging whom.
- File downloads are only served to the sender or recipient device of that specific message — checked server-side, not just hidden in the UI.
- This is what makes "only that device can view messages sent to it" actually true, rather than just a name shown in a list.

## 5. Presence model

Two separate things, not one list pretending to be both:
- **Online now** — devices with a live WebSocket connection, tracked in an in-memory set on the server, broadcast to connected clients as it changes.
- **Known conversations** — every device you've ever exchanged messages with, read from the `devices`/`messages` tables, shown regardless of whether they're online, with a greyed-out state and last-seen time when they're not.

## 6. Retention job

A systemd timer runs a standalone script nightly:
1. Find all `messages` older than `RETENTION_DAYS`.
2. For each, delete the message row.
3. For any `files` row no longer referenced by a remaining message, delete the physical file under `/data/files` **and then** the `files` row — in that order, so a crash mid-job never leaves an orphaned DB row pointing at a deleted file, worse than the reverse.
4. Log a one-line summary (rows deleted, bytes freed) so you can see it's actually running.

This is deliberately its own script, tested against seeded old data before it ever runs against real messages — this exact feature (delete the message, forget the file) is where even mature chat platforms have shipped bugs.

## 7. File handling

- Enforce `MAX_FILE_SIZE_MB` per upload at the API layer, not just in the frontend.
- Also check total free disk space on homebot before accepting an upload; refuse cleanly with a clear error rather than filling the disk.
- Store blobs under `/data/files/<uuid>` (not the original filename) to avoid collisions and path traversal, keep the original name only in the `files` row for display/download.

---

## v1 — Minimum working version

Goal: text + file DMs that persist, are private per device, respect a global retention window, and are reachable securely from any device on the network.

- [ ] FastAPI scaffold + SQLite schema (section 3)
- [ ] Device registration + token auth on every route and the WebSocket (section 4)
- [ ] 1:1 text messaging — REST send + WebSocket push to the recipient if online
- [ ] File upload/download with per-file size limit + free-disk check
- [ ] Presence: online-now (WebSocket) + known-conversations (DB), shown as two distinct states in the UI
- [ ] Retention job as a systemd timer, tested against seeded old data before going live
- [ ] Minimal frontend: device list, chat thread, file attach button, download links
- [ ] Caddy + mkcert HTTPS, root cert trusted once on each family device
- [ ] Deployed as a systemd service on homebot (`hearth.service`), survives reboot
- [ ] One week of real dogfood use with the family, then re-check default retention days and size limit against actual usage

**Explicitly out of v1:** group chats, push notifications when the tab is closed, an admin UI, multi-device-per-person identity, message search.

## v2 — Once v1 has been used for a while

- [ ] **Multi-device-per-person identity** — right now "device" is the unit; this groups multiple tokens (e.g. your wife's phone *and* laptop) under one person, so "chat with [[wife|Akshaya]]" works regardless of which device she has open. This is the biggest architectural change on the list — worth doing once you know the household actually wants it.
- [ ] Group chats / rooms, not just 1:1
- [ ] PWA install + best-effort background notifications (works reasonably on Android; iOS Safari is much more restrictive — set expectations accordingly)
- [ ] Admin view: storage used, per-device stats, manual purge, edit retention/size limit without SSH-ing in
- [ ] Nightly backup of `hearth.db` + `/data/files` to another device/NAS on the network
- [ ] Message search
- [ ] Read receipts / typing indicators (nice-to-have, not core)
- [ ] Inline image/video preview instead of plain download links
- [ ] Optional at-rest encryption of message bodies (defense in depth, even LAN-only)
- [ ] Basic rate limiting per device (guests on the Wi-Fi, kids mashing the upload button)

---

## 8. Suggested repo layout

```
hearth/
├── README.md
├── PLAN.md                    ← this document
├── .gitignore                 ← excludes hearth.db, /data/files, .env, certs
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── config.py          ← RETENTION_DAYS, MAX_FILE_SIZE_MB, app name
│       ├── db.py
│       ├── auth.py
│       ├── retention.py       ← standalone, run by the timer, not the web process
│       └── routes/
│           ├── devices.py
│           ├── messages.py
│           ├── files.py
│           └── ws.py
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
└── deploy/
    ├── hearth.service
    ├── hearth-retention.service
    ├── hearth-retention.timer
    └── Caddyfile
```

## 9. Build order for v1

1. Scaffold FastAPI + SQLite schema
2. Device registration + token auth middleware
3. Text messaging (REST + WebSocket push)
4. File upload/download with limits
5. Presence tracking over WebSocket
6. Retention job + systemd timer, tested against seeded data
7. Frontend: device list, chat thread, attach UI
8. Caddy + mkcert HTTPS, verified cross-device (phone + laptop)
9. Deploy as a systemd service on homebot, confirm it survives a reboot
10. Family dogfood week, then tune defaults
