# Deploying Hearth

Everything through the frontend is built and CI-tested. These steps happen on
the server machine and on each family device. Tested end-to-end on
Debian 13 (Python 3.13) — adjust package names for your distro.

By default Hearth serves **plain HTTP directly from uvicorn** — no reverse
proxy, no certificates, nothing to install on client devices. HTTPS is
optional (see step 5) if you later want TLS or browser-notification support.

Choose ONE user to run the service as before you start, and substitute
`<deploy-user>` below wherever it appears:
- **Dedicated service user** (e.g. `hearth`) — standard hardening, best if the
  box is shared or the app is exposed beyond your LAN.
- **An existing user** — perfectly fine for a single-user household box on a
  trusted LAN; fewer accounts to maintain.

`<install-root>` defaults to `/opt/hearth` — adjust everywhere if you choose
differently (the systemd unit files under `deploy/` assume this path).

## 1. Get the code and set up the environment

```bash
# If using a dedicated user:
sudo useradd -r -m -d <install-root> hearth
# If using an existing user, just make the directory writable by them:
sudo mkdir -p <install-root> && sudo chown <deploy-user>:<deploy-user> <install-root>

git clone <this repo> <install-root>
cd <install-root>/backend
python3 -m venv .venv            # Debian/Ubuntu: needs python3-venv package
.venv/bin/pip install -r requirements.txt
```

## 2. Configure

```bash
cp .env.example <install-root>/.env
mkdir -p <install-root>/data/files
```

Edit `.env`:
- `HEARTH_DB_PATH` / `HEARTH_FILES_DIR` — match your install root
  (e.g. `<install-root>/data/hearth.db`).
- `HEARTH_SERVE` — `http` (default) or `https`.
- `HEARTH_BIND` — `0.0.0.0` so LAN devices can reach the app (default).
- `HEARTH_PORT` — defaults to 8000.
- Retention/limits — 30-day retention, 200MB per-file, 5GB total by default.

## 3. systemd services

The unit files in `deploy/` reference `User=hearth`, `<install-root>/backend`,
and `<install-root>/.env`. Edit them to match your chosen user and install
root, then:

```bash
sudo cp deploy/hearth.service deploy/hearth-retention.service deploy/hearth-retention.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hearth.service hearth-retention.timer
systemctl status hearth.service --no-pager     # expect: active (running)
```

## 4. Verify and connect devices

```bash
curl http://127.0.0.1:8000/health      # → {"status":"ok",...}
systemctl list-timers hearth-retention.timer   # scheduled
```

Reboot the server; `systemctl is-active hearth.service` should be `active`
without manual start.

On each device, open `http://<server-lan-ip>:<port>` (find the server's LAN IP
with `ip addr`; optionally add a DNS/hosts name so it's a memorable URL).
Then:

1. Get a pairing code, either:
   - **Fixed/reusable**: set `HEARTH_PAIRING_CODE` in `.env` and restart the
     service. That code works for any number of devices, indefinitely — no
     per-device generation step.
   - **One-time**: leave `HEARTH_PAIRING_CODE` unset and generate a fresh
     single-use code per device:
     ```bash
     cd <install-root>/backend && .venv/bin/python -m app.pairing
     ```
2. Enter a device name + the code in the web UI.

No certificates or browser settings to touch on devices in HTTP mode.

## 5. HTTPS (optional)

Two things HTTP doesn't give you, and when they matter:

- **Encryption on the wire** — only relevant if untrusted devices join your
  LAN. Home Wi-Fi (WPA2/3) already encrypts the air.
- **Browser "secure context"** — required for web notifications. If you want
  "new message" push-style popups, you need HTTPS.

If you want HTTPS, two routes:

**a. Static cert (e.g. mkcert / internal CA):** uvicorn terminates TLS itself —
no reverse proxy needed. Set in `.env`:

```
HEARTH_SERVE=https
HEARTH_TLS_CERT=/path/to/cert.pem
HEARTH_TLS_KEY=/path/to/key.pem
```

Startup fails loudly if either file is missing. Note mkcert-style local CAs
must be installed and trusted on every client device, and on Android may trip
banking-app attestation checks — this is exactly why HTTP is the default.

**b. Publicly-trusted cert (Let's Encrypt DNS-01):** needed for browser
notifications without touching client devices. Requires a domain and a DNS
provider; certbot or Caddy's DNS plugin handles issuance + auto-renewal, then
either run Caddy in front or feed the renewed certs to uvicorn via the same
`HEARTH_TLS_CERT`/`HEARTH_TLS_KEY` paths.

Restart the service after changing `.env`:
`sudo systemctl restart hearth.service`.

## 6. Dogfood

Real usage, not something a checklist can do. Worth actually watching:
- Do all devices reliably receive messages/files (including ones sent while
  they were offline — history refetches on reconnect)?
- Does at least one large-file transfer beat whatever cloud alternative you'd
  otherwise use?
- Does the retention timer clean up without touching anything recent?
