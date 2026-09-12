import os

APP_NAME = "Hearth"

RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "200"))
MAX_TOTAL_STORAGE_MB = int(os.getenv("MAX_TOTAL_STORAGE_MB", "5000"))
STORAGE_WARNING_THRESHOLD = 0.8

DB_PATH = os.getenv("HEARTH_DB_PATH", "hearth.db")
FILES_DIR = os.getenv("HEARTH_FILES_DIR", "data/files")
