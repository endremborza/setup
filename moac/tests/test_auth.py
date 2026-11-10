"""Credential expiry and refresh."""

import json
import time
from pathlib import Path

from moac import _auth


def test_expiry_is_read_and_written_in_milliseconds(
    tmp_path: Path, monkeypatch
) -> None:
    ms = int(time.time() * 1000)
    assert _auth._expired({"claudeAiOauth": {"expiresAt": ms + 3_600_000}}) is False
    assert _auth._expired({"claudeAiOauth": {"expiresAt": ms + 30_000}}) is True

    class _Reply:
        ok = True

        @staticmethod
        def json() -> dict:
            return {"access_token": "new", "expires_in": 3600}

    import types

    fake_requests = types.SimpleNamespace(post=lambda *a, **k: _Reply())
    monkeypatch.setitem(__import__("sys").modules, "requests", fake_requests)
    monkeypatch.setattr(_auth, "warn_if_changed", lambda *a: None)
    path = tmp_path / "creds.json"
    path.write_text(
        json.dumps({"claudeAiOauth": {"refreshToken": "r", "expiresAt": 1}})
    )
    path.chmod(0o600)
    _auth._refresh(path)
    creds = json.loads(path.read_text())["claudeAiOauth"]
    assert creds["accessToken"] == "new" and creds["expiresAt"] > ms + 3_500_000
    assert path.stat().st_mode & 0o777 == 0o600
