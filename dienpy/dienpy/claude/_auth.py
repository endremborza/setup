"""The claude command's own oauth credentials, refreshed the way the command does it."""

from __future__ import annotations

import json
import mmap
import shutil
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from .._toml import write_atomic

if TYPE_CHECKING:
    import requests

_CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"

# constants the claude binary carries; `warn_if_changed` notices when a release moves them
# (extract anew with: strings $(which claude) | grep -E 'CLIENT_ID|TOKEN_URL')
_TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
_BETA_HEADER = "oauth-2025-04-20"

# every call here is short; a stalled connection must not hang a long-running loop
TIMEOUT = 30

# the credentials file keeps `expiresAt` in milliseconds
_MS = 1000
_EARLY_MS = 60 * _MS


def _in_binary(value: str) -> bool | None:
    """Whether the installed claude binary carries `value`; None when there is no binary."""
    claude_path = shutil.which("claude")
    if not claude_path:
        return None
    try:
        with (
            open(claude_path, "rb") as f,
            mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m,
        ):
            return m.find(value.encode()) != -1
    except (OSError, ValueError):
        return None


def warn_if_changed(label: str, value: str) -> None:
    """Warn if a hardcoded constant is no longer present in the claude binary."""
    if _in_binary(value) is False:
        print(
            f"Warning: {label} '{value}' not found in the claude binary — it may have changed. "
            f"See claude/_auth.py.",
            file=sys.stderr,
        )


def _read(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def _write(path: Path, creds: dict) -> None:
    write_atomic(path, json.dumps(creds, indent=2))


def _expired(creds: dict) -> bool:
    return time.time() * _MS >= creds["claudeAiOauth"].get("expiresAt", 0) - _EARLY_MS


def _refresh(path: Path) -> None:
    import requests

    warn_if_changed("client_id", _CLIENT_ID)
    warn_if_changed("anthropic-beta", _BETA_HEADER)
    creds = _read(path)
    r = requests.post(
        _TOKEN_URL,
        json={
            "grant_type": "refresh_token",
            "refresh_token": creds["claudeAiOauth"]["refreshToken"],
            "client_id": _CLIENT_ID,
        },
        timeout=TIMEOUT,
    )
    if not r.ok:
        raise SystemExit(
            f"Token refresh failed ({r.status_code}). Run 'claude' once to re-authenticate."
        )
    data = r.json()
    oauth = creds["claudeAiOauth"]
    oauth["accessToken"] = data["access_token"]
    oauth["expiresAt"] = int(time.time() * _MS) + data.get("expires_in", 3600) * _MS
    if "refresh_token" in data:
        oauth["refreshToken"] = data["refresh_token"]
    _write(path, creds)


def _make_headers(path: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    creds = _read(path)
    if _expired(creds):
        _refresh(path)
        creds = _read(path)
    headers = {
        "Authorization": f"Bearer {creds['claudeAiOauth']['accessToken']}",
        "anthropic-beta": _BETA_HEADER,
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def request(
    method: str,
    url: str,
    extra_headers: dict[str, str] | None = None,
    creds_path: Path | None = None,
    **kwargs,
) -> requests.Response:
    """Authenticated request with automatic token refresh on 401.

    creds_path overrides the default ~/.claude/.credentials.json; refreshed
    tokens are written back to whichever file was used.
    """
    import requests

    path = creds_path or _CREDENTIALS_PATH
    kwargs.setdefault("timeout", TIMEOUT)
    r = getattr(requests, method)(
        url, headers=_make_headers(path, extra_headers), **kwargs
    )
    if r.status_code == 401:
        _refresh(path)
        r = getattr(requests, method)(
            url, headers=_make_headers(path, extra_headers), **kwargs
        )
    return r
