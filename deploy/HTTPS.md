# HTTPS setup

Hearth runs as plain HTTP by default — see the main [README](../README.md)
and [deploy/README.md](README.md). This file covers the optional HTTPS setup
referenced from both.

## Do you need this?

Two things HTTP doesn't give you:

- **Encryption on the wire** — only matters if you don't trust every device
  on your Wi-Fi. Home Wi-Fi (WPA2/3) already encrypts the air itself.
- **Browser "secure context"** — required for web push notifications. If you
  want "new message" popups, you need HTTPS.

If neither applies, skip this file.

## Two things to decide

1. **Where TLS terminates** — uvicorn directly (simplest), or Caddy in front
   of it (only needed for the self-service device-trust page in Option B).
2. **Where the certificate comes from** — a local CA via `mkcert` (free,
   but every device must trust it once), or a publicly-trusted certificate
   via Let's Encrypt (no per-device trust step, but needs a domain).

## Option A: uvicorn + mkcert, trust devices manually

Simplest route. No reverse proxy. You copy the CA cert onto each device
yourself (AirDrop, USB, etc).

```bash
# On the server, once: install mkcert and create a local CA
sudo apt install libnss3-tools
curl -JLO https://dl.filippo.io/mkcert/latest?for=linux/amd64
chmod +x mkcert-v*-linux-amd64 && sudo mv mkcert-v*-linux-amd64 /usr/local/bin/mkcert
mkcert -install

# Generate a cert for the server's hostname
mkcert homebot.local          # adjust to your server's actual hostname/IP
sudo mkdir -p /etc/hearth/certs
sudo mv homebot.local.pem homebot.local-key.pem /etc/hearth/certs/
```

Edit `.env`:

```
HEARTH_SERVE=https
HEARTH_TLS_CERT=/etc/hearth/certs/homebot.local.pem
HEARTH_TLS_KEY=/etc/hearth/certs/homebot.local-key.pem
```

Restart: `sudo systemctl restart hearth.service`. Startup fails loudly if
either cert file is missing.

Copy `$(mkcert -CAROOT)/rootCA.pem` to each device and install it as a
trusted root certificate (Settings → trust a certificate, varies by OS).
Until a device trusts it, its browser will show a certificate warning.

## Option B: mkcert + Caddy, self-service device trust (recommended for multiple devices)

Adds a QR-code landing page so each family member trusts the CA themselves
in about 30 seconds, without you touching their phone.

1. Generate the CA and a cert as in Option A, but keep `HEARTH_SERVE=http`
   in `.env` — Caddy terminates TLS instead, and proxies to uvicorn over
   plain HTTP on localhost.

2. Install Caddy (`sudo apt install caddy`, or see caddyserver.com), then
   publish the CA root and the trust landing page:

   ```bash
   sudo mkdir -p /etc/hearth/ca-public
   sudo cp "$(mkcert -CAROOT)/rootCA.pem" /etc/hearth/ca-public/rootCA.pem
   sudo cp deploy/ca-public/index.html /etc/hearth/ca-public/
   ```

3. Generate the QR code that links to the landing page (adjust the URL to
   match the plain-HTTP hostname Caddy will serve it on):

   ```bash
   cd <install-root>/backend
   .venv/bin/python ../deploy/generate_ca_qr.py http://homebot.local /etc/hearth/ca-public/ca-qr.svg
   ```

4. Edit `deploy/Caddyfile` — set the hostname and port to your server's,
   and confirm the cert paths match step 1 — then install it:

   ```bash
   sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
   sudo systemctl restart caddy
   ```

   This runs two listeners: `https://homebot.local:8443` (reverse-proxied
   to Hearth) and plain `http://homebot.local` (serves only
   `/etc/hearth/ca-public` — the CA cert, QR code, and instructions; never
   the private key in `/etc/hearth/certs`).

5. On each device: scan the QR code (or open `http://homebot.local`),
   follow the on-page instructions for that platform (iOS, Android, macOS,
   Windows each get their own steps), then open
   `https://homebot.local:8443` — no more certificate warnings.

## Option C: publicly-trusted certificate (Let's Encrypt, DNS-01)

Needed only if you want browser push notifications to work without any
per-device trust step. Requires owning a domain and a DNS provider that
supports the DNS-01 challenge (no public port-forwarding needed).

Use `certbot` or Caddy's DNS-01 plugin to issue and auto-renew the
certificate, then either:

- point `HEARTH_TLS_CERT` / `HEARTH_TLS_KEY` at the renewed cert/key files
  and set `HEARTH_SERVE=https` (uvicorn terminates TLS itself), or
- run Caddy in front with the same DNS-01 plugin handling issuance.

No landing page or QR code needed here — the certificate is already
trusted by every device's browser.

## After changing `.env` or Caddy config

```bash
sudo systemctl restart hearth.service
sudo systemctl restart caddy      # only if using Option B or a Caddy-based Option C
```
