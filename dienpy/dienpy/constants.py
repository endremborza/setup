import os
from pathlib import Path


def _env_path(key: str, fallback: str) -> Path:
    return Path(os.environ.get(key, fallback))


SYNC_ROOT = _env_path("SYNC_ROOT", "/mnt/data/synced")

CODE_DIR = _env_path("CODE_DIR", str(SYNC_ROOT / "code"))
COMPOSITES_DIR = _env_path("COMPOSITES_DIR", str(SYNC_ROOT / "composites"))
FOLIOS_DIR = _env_path("FOLIOS_DIR", str(SYNC_ROOT / "folios"))
DATA_DIR = _env_path("DATA_DIR", str(SYNC_ROOT / "data"))
ASSETS_DIR = _env_path("ASSETS_DIR", str(SYNC_ROOT / "assets"))
MEDIA_DIR = _env_path("MEDIA_DIR", str(SYNC_ROOT / "media"))
SHARE_DIR = _env_path("SHARE_DIR", str(SYNC_ROOT / "share"))

PDF_STORE = FOLIOS_DIR / "pile"
REPO_STORE = ASSETS_DIR / "repos"
STANDALONE_ANALYSIS_BASES = DATA_DIR / "standalone"

LOGS_DIR = _env_path("LOGS_DIR", "/mnt/data/logs")

REMOTE_NAME = "gdrive"
REMOTE_ROOT = "rcloned"
