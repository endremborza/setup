import functools
import json
import shutil
import sys
import time
from pathlib import Path

import requests

_CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"

# Found in Claude CLI binary. If warn_if_changed fires, extract updated value with:
#   python3 -c "
#   import re, shutil
#   b = open(shutil.which('claude'), 'rb').read().decode('latin-1')
#   print(re.findall(r'CLIENT_ID:\"([^\"]+)\"', b))
#   print(re.findall(r'TOKEN_URL:\"([^\"]+)\"', b))
#   "
_TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
_BETA_HEADER = "oauth-2025-04-20"

# Anthropic Messages API version header. Required for /v1/messages and related endpoints.
# Stable since Claude 3 launch; Anthropic rarely increments this.
# To check for updates: https://docs.anthropic.com/en/api/versioning
# To find current value in the Claude binary:
#   strings $(which claude) | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
ANTHROPIC_VERSION = "2023-06-01"


@functools.cache
def _binary_content() -> bytes:
    claude_path = shutil.which("claude")
    if not claude_path:
        return b""
    try:
        return Path(claude_path).read_bytes()
    except OSError:
        return b""


def warn_if_changed(label: str, value: str) -> None:
    """Warn once if a hardcoded constant is no longer present in the Claude CLI binary."""
    binary = _binary_content()
    if binary and value.encode() not in binary:
        print(
            f"Warning: {label} '{value}' not found in Claude CLI binary — it may have changed. "
            f"See update instructions in claude/auth.py.",
            file=sys.stderr,
        )


def _read() -> dict:
    with _CREDENTIALS_PATH.open() as f:
        return json.load(f)


def _write(creds: dict) -> None:
    with _CREDENTIALS_PATH.open("w") as f:
        json.dump(creds, f, indent=2)


def _expired(creds: dict) -> bool:
    return time.time() >= creds["claudeAiOauth"].get("expiresAt", 0) - 60


def _refresh() -> None:
    warn_if_changed("client_id", _CLIENT_ID)
    warn_if_changed("anthropic-beta", _BETA_HEADER)
    creds = _read()
    r = requests.post(
        _TOKEN_URL,
        json={
            "grant_type": "refresh_token",
            "refresh_token": creds["claudeAiOauth"]["refreshToken"],
            "client_id": _CLIENT_ID,
        },
    )
    if not r.ok:
        raise SystemExit(
            f"Token refresh failed ({r.status_code}). Run 'claude' once to re-authenticate."
        )
    data = r.json()
    oauth = creds["claudeAiOauth"]
    oauth["accessToken"] = data["access_token"]
    oauth["expiresAt"] = int(time.time()) + data.get("expires_in", 3600)
    if "refresh_token" in data:
        oauth["refreshToken"] = data["refresh_token"]
    _write(creds)


def _make_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    creds = _read()
    if _expired(creds):
        _refresh()
        creds = _read()
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
    **kwargs,
) -> requests.Response:
    """Authenticated request with automatic token refresh on 401."""
    r = getattr(requests, method)(url, headers=_make_headers(extra_headers), **kwargs)
    if r.status_code == 401:
        _refresh()
        r = getattr(requests, method)(
            url, headers=_make_headers(extra_headers), **kwargs
        )
    return r
