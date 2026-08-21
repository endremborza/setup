"""regroup cache (.git/regroup-cache.json) — schema owner; nvim's regroup/state.lua reads this file."""

import dataclasses
import json
import time
from pathlib import Path
from typing import Any

from . import _rebind
from ._config import Config
from ._hunks import Hunk

VERSION = 3
_READABLE = (2, VERSION)  # v2 entries lack anchors; they gain them on the next write


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
    if not isinstance(data, dict) or data.get("version") not in _READABLE:
        return None
    return data


def last_config(root: str) -> dict[str, str] | None:
    data = load(root)
    return data.get("last") if data else None


def entry(root: str, config: Config) -> dict[str, Any] | None:
    data = load(root)
    return (data or {}).get("analyses", {}).get(config.key)


def prune(root: str, hunks: list[Hunk], head: str) -> None:
    """Drop analyses describing none of the current diff — every hunks command calls this.

    An entry survives on a shared hunk id, or on an anchor a live hunk still overlaps
    (its hunks were edited, not removed — `_rebind` can carry them).
    """
    data = load(root)
    if not data:
        return
    live_ids = {h.id for h in hunks}
    live_anchors = list(_rebind.anchors(hunks).values())

    def covers(e: dict) -> bool:
        if not live_ids.isdisjoint(e["ids"]):
            return True
        if e.get("head") != head:
            return False
        return any(
            _rebind.overlap(a, b)
            for a in (e.get("anchors") or {}).values()
            for b in live_anchors
        )

    analyses = data.get("analyses", {})
    stale = [k for k, e in analyses.items() if not covers(e)]
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
    root: str, config: Config, hunks: list[Hunk], groups: list[dict], head: str
) -> None:
    """Write the entry; `time` only advances when its content actually changed.

    `hunks` is the whole live diff (it supplies the rebind anchors), while `ids` records
    only what the groups actually cover — the two coincide for a full run, and diverge
    for a path-scoped one, whose groups describe a subset of the diff.
    """
    data = load(root) or {"version": VERSION, "analyses": {}}
    grouped = {hid for g in groups for hid in g["hunks"]}
    payload = {
        "ids": [h.id for h in hunks if h.id in grouped],
        "groups": groups,
        "anchors": _rebind.anchors(hunks),
        "head": head,
        "config": dataclasses.asdict(config),
    }
    prev = data["analyses"].get(config.key) or {}
    unchanged = prev.get("time") and all(prev.get(k) == v for k, v in payload.items())
    payload["time"] = prev["time"] if unchanged else int(time.time())
    data["analyses"][config.key] = payload
    _write(root, data)
