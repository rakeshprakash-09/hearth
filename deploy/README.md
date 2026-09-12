# Deploying Hearth on homebot

Everything up through the frontend has been built and tested locally. These
steps have to happen on homebot itself and on each family device — nothing
here has been run yet, since this session has no access to either.

## 1. Get the code onto homebot

```
sudo useradd -r -m -d /opt/hearth hearth
sudo -u hearth git clone <this repo> /opt/hearth
cd /opt/hearth/backend
sudo -u hearth python3 -m venv .venv
sudo -u hearth .venv/bin/pip install -r requirements.txt
```

Adjust `/opt/hearth` everywhere below if you put it somewhere else — that's
just what `hearth.service` / `hearth-retention.service` assume.

## 2. Configure

```
sudo -u hearth cp .env.example /opt/hearth/.env
sudo -u hearth mkdir -p /opt/hearth/data/files
```

Edit `/opt/hearth/.env` if the defaults (30-day retention, 200MB file limit)
aren't what you want.

## 3. TLS cert via mkcert

```
sudo apt install mkcert   # or however it's packaged for homebot's distro
mkcert -install           # trusts the local CA on homebot itself
sudo mkdir -p /etc/hearth/certs
mkcert -cert-file /etc/hearth/certs/homebot.local.pem \
       -key-file /etc/hearth/certs/homebot.local-key.pem \
       homebot.local
```

Then copy `$(mkcert -CAROOT)/rootCA.pem` to each family device and trust it:
- **iOS**: AirDrop/email the file, install as a profile in Settings, then
  also enable it under Settings > General > About > Certificate Trust
  Settings (both steps are required, easy to miss the second one).
- **Android**: Settings > Security > Install a certificate > CA certificate.
- **macOS/Windows laptops**: double-click to import into the system/login
  keychain or certificate store, mark trusted.

## 4. Caddy

Install Caddy, then point it at `deploy/Caddyfile` (adjust the port in that
file first if 8443 collides with anything else already running on homebot):

```
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

## 5. systemd services

```
sudo cp deploy/hearth.service deploy/hearth-retention.service deploy/hearth-retention.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hearth.service
sudo systemctl enable --now hearth-retention.timer
```

## 6. Verify

- `sudo systemctl status hearth.service` — should be active.
- From another device on the same Wi-Fi, after trusting the root CA:
  `https://homebot.local:8443/health` should return `{"status":"ok",...}`.
- Reboot homebot, confirm `hearth.service` comes back up on its own
  (`systemctl is-enabled hearth.service` should say `enabled`).
- `sudo systemctl list-timers hearth-retention.timer` to confirm it's
  scheduled.

## 7. Dogfood week

Real usage, not something this session can do. The two things worth
actually checking afterward (see the earlier assessment): does the kid's
laptop reliably get files/messages from parents, and does at least one
large-file transfer beat whatever cloud alternative you'd otherwise use.
