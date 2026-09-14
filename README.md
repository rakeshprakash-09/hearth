# Hearth

A private, self-hosted chat and file-sharing hub for your home network.

Run it on any always-on machine on your LAN — a Raspberry Pi, an old laptop, a home server — and every device on your Wi-Fi (phones, laptops, tablets) can register, message each other 1:1, and share files, without any of it touching the internet or a third-party server. No accounts, no cloud, no ads, no telemetry. Just your household's own private Signal-lite, running on hardware you already own.

# 

## Features

- **1:1 messaging** — real-time text chat between any two registered devices, pushed instantly over WebSocket when both are online, and fetched as history on reconnect when they weren't.
- **File sharing** — attach and send files of any type directly in a conversation, with a per-file size limit and a household-wide storage cap, both enforced server-side.
- **Presence** — see who's online right now (live) versus every device you can message, with a last-seen timestamp for anyone offline.
- **Device pairing, not accounts** — no usernames or passwords. An admin generates a single-use pairing code on the server; each device redeems one code, once, to register and receive its own private access token.
- **Automatic retention** — messages older than a configurable window are deleted nightly by a systemd timer, and any file no longer referenced by a message is cleaned up right after — so storage doesn't grow forever.
- **Storage budget warning** — the UI shows a warning banner once total file storage crosses 80% of the configured cap.
- **Browser notifications** — an optional nudge when a message arrives while the tab is hidden.
- **HTTP by default, HTTPS if you want it** — runs as plain HTTP out of the box (nothing to install on client devices); switch to HTTPS with a cert path in `.env` if you want encryption-in-transit or browser push notifications, which require a secure context.
- **No build step** — the frontend is plain HTML/CSS/JS served directly by the backend. No Node toolchain needed on the server.

## How it works

Every device that wants to use Hearth first registers with a one-time pairing code generated on the server. Registration returns a private bearer token, stored in the browser's `localStorage`, which authenticates every API call and the WebSocket connection from then on. There are no passwords to remember and no central account system — possession of the token *is* the device's identity.

Once registered, a device sees every other registered device in a sidebar, shows who's currently online, and can open a 1:1 conversation with any of them. Messages sent while the recipient is online arrive instantly over WebSocket; messages sent while they're offline are simply waiting in the database the next time they connect. File downloads are authorized per-message, server-side — a device can only fetch a file if it was the sender or the recipient of that specific message, not just because it guessed the URL.

A nightly job — a small standalone script run by a systemd timer, not the web server itself — deletes messages older than the configured retention window, and once a file is no longer referenced by any message, deletes the file on disk too.

## Architecture

```
 ┌─────────────┐        HTTP(S)/WS         ┌───────────────────────────┐
 │  Any device  │ ───────────────────────▶ │  Your home server          │
 │  (browser)   │ ◀─────────────────────── │  FastAPI + Uvicorn         │
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

**Stack**

| Layer     | Choice                                                          | Why                                                                                                |
| --------- | --------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Backend   | Python 3.12+, FastAPI, Uvicorn                                  | Native WebSocket support, tiny footprint, no framework bloat                                       |
| Database  | SQLite                                                          | Zero administration, plenty for household scale                                                    |
| Frontend  | Plain HTML/CSS/JS, no build step                                | Deploys as static files, no Node toolchain on the server                                           |
| Serving   | Uvicorn (HTTP by default, terminates its own TLS in HTTPS mode) | Nothing extra to install for the common case; a reverse proxy like Caddy is optional, not required |
| Retention | Standalone script + systemd timer                               | Runs outside the web process, easy to test in isolation                                            |

## Project layout

```
hearth/
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py          # FastAPI app, mounts routers + frontend
│       ├── config.py        # env-driven settings (retention, limits, ports, TLS)
│       ├── db.py            # SQLite schema + connection helpers
│       ├── auth.py          # bearer token issuance/verification
│       ├── pairing.py       # single-use pairing code generation/redemption
│       ├── retention.py     # nightly cleanup job
│       ├── ws.py            # WebSocket: live messages + presence
│       └── routes/          # devices, messages, files REST endpoints
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
└── deploy/
    ├── hearth.service              # systemd unit for the app
    ├── hearth-retention.service    # systemd unit for the retention job
    ├── hearth-retention.timer      # nightly schedule for the job above
    ├── Caddyfile                   # optional reverse proxy config (HTTPS)
    ├── generate_ca_qr.py           # QR code for the HTTPS device-trust page
    ├── ca-public/                  # landing page devices use to trust the CA (HTTPS)
    ├── README.md                   # full deployment walkthrough
    └── HTTPS.md                    # optional HTTPS setup
```

## Getting started (local / development)

Requirements: Python 3.12+.

```bash
git clone <this repo>
cd hearth/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip install -r requirements.txt

cp ../.env.example .env
# edit .env if you want to change defaults — see "Configuration" below

.venv/bin/python -m app.run                    # Windows: .venv\Scripts\python -m app.run
```

The app starts on `http://0.0.0.0:8000` by default and serves the frontend directly — open `http://localhost:8000` in a browser.

To let a device in, generate a single-use pairing code from the backend:

```bash
.venv/bin/python -m app.pairing
```

Enter a device name and that code on the registration screen. Repeat once per device you want to add.

## Configuration

All configuration lives in `.env` (copy from `.env.example`), read by `backend/app/config.py`:

| Variable                             | Default             | Purpose                                                                            |
| ------------------------------------ | ------------------- | ---------------------------------------------------------------------------------- |
| `RETENTION_DAYS`                     | `30`                | How long messages (and their orphaned files) are kept before nightly cleanup       |
| `MAX_FILE_SIZE_MB`                   | `200`               | Per-file upload limit                                                              |
| `MAX_TOTAL_STORAGE_MB`               | `5000`              | Household-wide cap on stored files; the UI warns at 80%                            |
| `HEARTH_PAIRING_CODE`                | *(random per call)* | Pin the pairing code to a fixed value instead of generating a random one each time |
| `HEARTH_DB_PATH`                     | `hearth.db`         | SQLite database file location                                                      |
| `HEARTH_FILES_DIR`                   | `data/files`        | Where uploaded file blobs are stored                                               |
| `HEARTH_SERVE`                       | `http`              | `http` (default, no certs needed) or `https` (uvicorn terminates TLS itself)       |
| `HEARTH_BIND`                        | `0.0.0.0`           | Interface to bind — `0.0.0.0` so other devices on the LAN can reach it             |
| `HEARTH_PORT`                        | `8000`              | Listening port                                                                     |
| `HEARTH_TLS_CERT` / `HEARTH_TLS_KEY` | *(unset)*           | Certificate paths, required only when `HEARTH_SERVE=https`                         |

## Deploying to a home server

The short version: clone the repo onto the server, set up a virtualenv, copy `.env.example` to `.env` and configure it, then install the two systemd units in `deploy/` (the app itself, and the nightly retention timer) so it survives reboots. Plain HTTP works out of the box with nothing to install on client devices; HTTPS is an opt-in step for encryption-in-transit or browser push notifications.

Full step-by-step instructions — systemd unit setup, generating pairing codes for each family device, and verifying the service — are in **[`deploy/README.md`](deploy/README.md)**. HTTPS is optional and covered separately in **[`deploy/HTTPS.md`](deploy/HTTPS.md)**.

## Security model

- **No passwords, no shared secrets in transit** — a device registers once with a single-use pairing code and receives a random 32-byte bearer token; only its SHA-256 hash is ever stored.
- **Every route is authenticated** — every REST call and the WebSocket handshake require that bearer token; there's no anonymous read path.
- **Per-message file authorization** — a file download is only served to the sender or recipient of the specific message it belongs to, checked server-side on every request.
- **Server-side limits** — file size and total storage are enforced in the API layer, not just hinted at in the UI, and an upload is rejected before it can fill the disk.
- **LAN-only by design** — Hearth is built to be reachable only on your home network, not exposed to the public internet. If you do expose it beyond your LAN, use HTTPS.

# 

## License

[MIT](LICENSE)
