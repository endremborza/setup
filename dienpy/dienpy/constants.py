import os
from pathlib import Path


def env_path(key: str, fallback: str) -> Path:
    return Path(os.environ.get(key, fallback))


SYNC_ROOT = env_path("SYNC_ROOT", str(Path.home() / "synced"))

CODE_DIR = env_path("CODE_DIR", str(SYNC_ROOT / "code"))
COMPOSITES_DIR = env_path("COMPOSITES_DIR", str(SYNC_ROOT / "composites"))
FOLIOS_DIR = env_path("FOLIOS_DIR", str(SYNC_ROOT / "folios"))
DATA_DIR = env_path("DATA_DIR", str(SYNC_ROOT / "data"))
ASSETS_DIR = env_path("ASSETS_DIR", str(SYNC_ROOT / "assets"))
MEDIA_DIR = env_path("MEDIA_DIR", str(SYNC_ROOT / "media"))
SHARE_DIR = env_path("SHARE_DIR", str(SYNC_ROOT / "share"))
ARCHIVE_DIR = env_path("ARCHIVE_DIR", str(SYNC_ROOT / "archive"))

# The three PKM centers. Names and env keys match .vars, which exports the same
# three so a shell override reaches Python. PKM_REL is the layout under SYNC_ROOT,
# also the shape bootstrap.sh lays down on a leaf.
PKM_REL = "composites/pkm"
_CENTER_ENV = {
    "diencephalon": "DIEN_ROOT",
    "hypothalamus": "HYPO_ROOT",
    "logos": "LOGOS_ROOT",
}
CENTERS: dict[str, Path] = {
    name: env_path(key, str(SYNC_ROOT / PKM_REL / name))
    for name, key in _CENTER_ENV.items()
}
DIENCEPHALON_ROOT = CENTERS["diencephalon"]
HYPOTHALAMUS_ROOT = CENTERS["hypothalamus"]
LOGOS_ROOT = CENTERS["logos"]

PDF_STORE = FOLIOS_DIR / "pile"
PAPERS_FOLIO_DIR = FOLIOS_DIR / "papers"
REPO_STORE = ASSETS_DIR / "repos"
STANDALONE_ANALYSIS_BASES = DATA_DIR / "standalone"

LOGS_DIR = env_path("LOGS_DIR", str(SYNC_ROOT / "logs"))

REMOTE_NAME = "gdrive"
REMOTE_ROOT = "rcloned"
