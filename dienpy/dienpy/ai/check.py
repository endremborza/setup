"""Smoke-test AI profiles: endpoint reachable, API key present, claude installed and logged in."""

import os
import shutil
import sys
from pathlib import Path
from typing import Any

from . import _profiles
from ._profiles import ProfileName

_CREDENTIALS = Path.home() / ".claude" / ".credentials.json"
_ADC = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"


def _check_openai(spec: dict[str, Any]) -> str | None:
    import requests

    url = str(spec.get("url", "")).replace("/chat/completions", "/models")
    try:
        r = requests.get(url, timeout=5)
    except requests.RequestException as e:
        return f"unreachable: {e}"
    return None if r.ok else f"{url} -> {r.status_code}"


def _check_api(spec: dict[str, Any]) -> str | None:
    model = str(spec.get("model", ""))
    if model.startswith("gemini"):
        if os.environ.get("GEMINI_API_KEY") or _ADC.exists():
            return None
        return "GEMINI_API_KEY not set and no gcloud ADC"
    return None if os.environ.get("ANTHROPIC_API_KEY") else "ANTHROPIC_API_KEY not set"


def _check_cli(spec: dict[str, Any]) -> str | None:
    if not shutil.which("claude"):
        return "claude not on PATH"
    auth = spec.get("auth", "login")
    if auth == "login" and not _CREDENTIALS.exists():
        return f"no claude.ai login ({_CREDENTIALS} missing)"
    if auth == "env" and not (
        os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    ):
        return "auth=env but no ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN"
    return None


_CHECKS = {"openai": _check_openai, "api": _check_api, "cli": _check_cli}


def main(profile: ProfileName | None = None) -> None:
    failed = False
    for name in [profile] if profile else _profiles.names():
        spec = _profiles.get(name)
        check = _CHECKS.get(str(spec.get("kind", "")))
        problem = check(spec) if check else f"unknown kind '{spec.get('kind')}'"
        print(f"{name:<12} {'ok' if problem is None else f'FAIL  {problem}'}")
        failed = failed or problem is not None
    if failed:
        sys.exit(1)
