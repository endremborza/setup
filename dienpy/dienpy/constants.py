from pathlib import Path

SYNC_ROOT = f"{Path.home()}/synced"

SYNCED_ASSETS_DIR = f"{SYNC_ROOT}/assets"
SYNCED_CODE_DIR = f"{SYNC_ROOT}/code"
SYNCED_COMPOSITES_DIR = f"{SYNC_ROOT}/composites"
SYNCED_DATA_DIR = f"{SYNC_ROOT}/data"
SYNCED_FOLIOS_DIR = f"{SYNC_ROOT}/folios"
SYNCED_MEDIA_DIR = f"{SYNC_ROOT}/media"
SYNCED_SHARE_DIR = f"{SYNC_ROOT}/share"


REMOTE_NAME = "gdrive"
REMOTE_ROOT = "rcloned"


if __name__ == "__main__":
    for k, v in list(locals().items()):
        if isinstance(v, str) and k == k.upper():
            print(f"export {k} = {v}")
