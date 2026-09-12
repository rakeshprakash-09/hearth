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

sudo mkdir -p /etc/hearth/certs /etc/hearth/ca-public
sudo chown "$(whoami)":"$(whoami)" /etc/hearth/certs /etc/hearth/ca-public

mkcert -cert-file /etc/hearth/certs/homebot.local.pem \
       -key-file /etc/hearth/certs/homebot.local-key.pem \
       homebot.local
```

### Getting every family device to trust it, without emailing files around

Each device still needs a one-time "trust this certificate" step -- that's
unavoidable with a private CA -- but instead of AirDropping/emailing the
root CA file around, homebot serves a small setup page over plain HTTP
(has to be plain HTTP: a device can't yet trust an HTTPS page signed by the
very CA it hasn't trusted yet) with a QR code for phones and a download
link + written steps for laptops.

```
cp deploy/ca-public/index.html /etc/hearth/ca-public/
cp "$(mkcert -CAROOT)/rootCA.pem" /etc/hearth/ca-public/rootCA.pem
backend/.venv/bin/python deploy/generate_ca_qr.py \
    "http://homebot.local/" /etc/hearth/ca-public/ca-qr.svg
```

(Re-run only the `generate_ca_qr.py` line if the hostname/port ever changes.)

Once Caddy is running (step 4), send family members to `http://homebot.local/`
-- or just point a phone camera at the QR on that page -- and they self-serve
from there (iPhone, Android, macOS, and Windows steps are all on the page).

## 4. Caddy

Install Caddy, then point it at `deploy/Caddyfile` (adjust the port in that
file first if 8443 collides with anything else already running on homebot).
It now defines two sites: the HTTPS app on `:8443`, and a plain-HTTP site on
`homebot.local` (port 80) that serves only `/etc/hearth/ca-public` -- the
setup page from step 3, never the private key in `/etc/hearth/certs`.

```
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile   # this exact config hasn't been run against a real Caddy binary yet
sudo systemctl reload caddy
```

If port 80 fails to bind (permission denied), Caddy's own package usually
already grants `cap_net_bind_service`; if it's running some other way,
`sudo setcap 'cap_net_bind_service=+ep' $(which caddy)`.

## 5. systemd services

```
sudo cp deploy/hearth.service deploy/hearth-retention.service deploy/hearth-retention.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hearth.service
sudo systemctl enable --now hearth-retention.timer
```

## 6. Verify

- `sudo systemctl status hearth.service` — should be active.
- `http://homebot.local/` from another device should show the setup page,
  with the QR rendering and the download link actually downloading a
  `hearth-ca.pem` file.
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
