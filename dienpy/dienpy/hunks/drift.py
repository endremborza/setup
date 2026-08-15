"""Drift between the current diff and a cached run: kept/gone/new (exit 1 = drifted, 2 = no run)."""

import sys

from . import _cache, _config, _hunks


def get_completions(args: list[str]) -> list[str]:
    return [*_config.GRANULARITIES, *_config.CONTEXTS, *_config.MODELS]


def main(*dims: str) -> None:
    root = _hunks.git_root()
    current = [h.id for h in _hunks.parse(root)]
    _cache.prune(root, set(current))
    config = _config.resolve(dims, _cache.last_config(root))
    e = _cache.entry(root, config)
    if not e:
        print(f"no cached run for [{config.key}]")
        sys.exit(2)
    known = set(e["ids"])
    cur_set = set(current)
    kept = sum(1 for i in current if i in known)
    new = len(current) - kept
    gone = sum(1 for i in e["ids"] if i not in cur_set)
    print(
        f"[{config.key}] kept {kept} / gone {gone} / new {new} — "
        f"coverage {kept}/{len(current)}"
    )
    sys.exit(0 if new == 0 else 1)
