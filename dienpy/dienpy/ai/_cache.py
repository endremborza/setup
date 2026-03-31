"""Disk-cached model list for all AI providers. Used for autocomplete and display."""
import json
import time
from pathlib import Path

_CACHE_PATH = Path.home() / ".config" / "dienpy" / "ai-models.json"
_TTL = 86400  # 24 hours


def _load_raw() -> dict:
    if not _CACHE_PATH.exists():
        return {}
    try:
        return json.loads(_CACHE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_raw(data: dict) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(json.dumps(data, indent=2))


def needs_refresh(provider: str) -> bool:
    fetched_at = _load_raw().get(provider, {}).get("fetched_at", 0)
    return time.time() - fetched_at > _TTL


def save(provider: str, models: list[str]) -> None:
    data = _load_raw()
    data[provider] = {"models": models, "fetched_at": int(time.time())}
    _save_raw(data)


def load(provider: str | None = None) -> dict[str, list[str]]:
    """Return {provider: [model_ids]}, optionally filtered to one provider."""
    raw = _load_raw()
    result = {p: d["models"] for p, d in raw.items() if "models" in d}
    return {provider: result.get(provider, [])} if provider else result


def all_models() -> list[str]:
    """Flat list of all cached model IDs. Fast, no network."""
    return [m for models in load().values() for m in models]
