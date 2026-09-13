import os

APP_NAME = "Hearth"

RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "200"))
MAX_TOTAL_STORAGE_MB = int(os.getenv("MAX_TOTAL_STORAGE_MB", "5000"))
STORAGE_WARNING_THRESHOLD = 0.8

PAIRING_CODE = os.getenv("HEARTH_PAIRING_CODE", "")

DB_PATH = os.getenv("HEARTH_DB_PATH", "hearth.db")
FILES_DIR = os.getenv("HEARTH_FILES_DIR", "data/files")

# Serving: "http" (uvicorn directly, no TLS) or "https" (uvicorn terminates TLS
# itself with the cert below; Caddy not required). Bind 0.0.0.0 in http mode so
# LAN devices can reach the app.
SERVE_MODE = os.getenv("HEARTH_SERVE", "http").lower()
BIND_HOST = os.getenv("HEARTH_BIND", "0.0.0.0")
PORT = int(os.getenv("HEARTH_PORT", "8000"))
TLS_CERT = os.getenv("HEARTH_TLS_CERT", "")
TLS_KEY = os.getenv("HEARTH_TLS_KEY", "")
