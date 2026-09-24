"""Disk-cached model ids per API provider: the completion source, refreshed at most daily."""

import json
import time
from pathlib import Path

PATH = Path.home() / ".config" / "dienpy" / "ai-models.json"
TTL = 86400


def _raw() -> dict:
    if not PATH.exists():
        return {}
    try:
        return json.loads(PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def needs_refresh(provider: str) -> bool:
    return time.time() - _raw().get(provider, {}).get("fetched_at", 0) > TTL


def save(provider: str, models: list[str]) -> None:
    data = _raw()
    data[provider] = {"models": models, "fetched_at": int(time.time())}
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(data, indent=2))


def load() -> dict[str, list[str]]:
    """{provider: [model_ids]} for every cached provider."""
    return {p: d["models"] for p, d in _raw().items() if "models" in d}


def ids(provider: str) -> list[str]:
    """One provider's cached ids; [] until `ai models` has fetched them. No network."""
    return load().get(provider, [])
