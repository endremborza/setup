"""regroup cache (.git/regroup-cache.json) — schema owner; nvim's regroup/state.lua reads this file."""

import dataclasses
import json
import time
from pathlib import Path
from typing import Any

from ._config import Config

VERSION = 2


def _path(root: str) -> Path:
    return Path(root) / ".git" / "regroup-cache.json"


def load(root: str) -> dict[str, Any] | None:
    p = _path(root)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get("version") != VERSION:
        return None
    return data


def last_config(root: str) -> dict[str, str] | None:
    data = load(root)
    return data.get("last") if data else None


def entry(root: str, config: Config) -> dict[str, Any] | None:
    data = load(root)
    return (data or {}).get("analyses", {}).get(config.key)


def prune(root: str, live: set[str]) -> None:
    """Drop analyses sharing no hunk with the current diff — every hunks command calls this."""
    data = load(root)
    if not data:
        return
    analyses = data.get("analyses", {})
    stale = [k for k, e in analyses.items() if live.isdisjoint(e["ids"])]
    if not stale:
        return
    for k in stale:
        del analyses[k]
    _path(root).write_text(json.dumps(data))
    print(f"pruned {len(stale)} stale run{'s' if len(stale) > 1 else ''}")


def set_entry(root: str, config: Config, ids: list[str], groups: list[dict]) -> None:
    data = load(root) or {"version": VERSION, "analyses": {}}
    data["analyses"][config.key] = {
        "ids": ids,
        "groups": groups,
        "config": dataclasses.asdict(config),
        "time": int(time.time()),
    }
    data["last"] = dataclasses.asdict(config)
    _path(root).write_text(json.dumps(data))
