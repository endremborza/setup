"""regroup cache (.git/regroup-cache.json) — schema owner; nvim reads it through `hunks list --json`.

`analyses` is keyed by config (`granularity|model|context`); an entry holds the patches,
the hunk ids they cover, its config and time; `last` is the config the shell and nvim
act on. Every hunks command prunes entries that no longer describe any live hunk.
"""

import dataclasses
import json
import time
from pathlib import Path
from typing import Any

from ._config import Config
from ._hunks import Hunk

VERSION = 4


def key(config: dict[str, str]) -> str:
    return f"{config['granularity']}|{config['model']}|{config['context']}"


def _path(root: str) -> Path:
    return Path(root) / ".git" / "regroup-cache.json"


def _write(root: str, data: dict[str, Any]) -> None:
    data["version"] = VERSION
    _path(root).write_text(json.dumps(data))


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


def prune(root: str, hunks: list[Hunk]) -> None:
    """Drop analyses covering none of the live hunks — every hunks command calls this."""
    data = load(root)
    if not data:
        return
    live = {h.id for h in hunks}
    analyses = data.get("analyses", {})
    stale = [k for k, e in analyses.items() if live.isdisjoint(e["ids"])]
    if not stale:
        return
    for k in stale:
        del analyses[k]
    _write(root, data)
    print(f"pruned {len(stale)} stale run{'s' if len(stale) > 1 else ''}")


def touch_last(root: str, config: Config) -> None:
    data = load(root) or {"version": VERSION, "analyses": {}}
    data["last"] = dataclasses.asdict(config)
    _write(root, data)


def set_entry(
    root: str, config: Config, hunks: list[Hunk], patches: list[dict]
) -> None:
    """Write the entry; `time` only advances when its content actually changed.

    `ids` records what the patches cover, a subset of the live diff for a `--path` run.
    """
    data = load(root) or {"version": VERSION, "analyses": {}}
    grouped = {hid for p in patches for hid in p["hunks"]}
    payload = {
        "ids": [h.id for h in hunks if h.id in grouped],
        "patches": patches,
        "config": dataclasses.asdict(config),
    }
    prev = data["analyses"].get(config.key) or {}
    unchanged = prev.get("time") and all(prev.get(k) == v for k, v in payload.items())
    payload["time"] = prev["time"] if unchanged else int(time.time())
    data["analyses"][config.key] = payload
    _write(root, data)
