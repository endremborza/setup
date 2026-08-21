"""Drift between the current diff and a cached run: kept/rebound/gone/new (exit 1 = drifted, 2 = no run)."""

import sys

from . import _cache, _config, _hunks, _rebind


def get_completions(args: list[str]) -> list[str]:
    return [*_config.GRANULARITIES, *_config.CONTEXTS, *_config.MODELS]


def main(*dims: str) -> None:
    root = _hunks.git_root()
    hunks = _hunks.parse(root)
    head = _hunks.head_sha(root)
    _cache.prune(root, hunks, head)
    config = _config.resolve(dims, _cache.last_config(root))
    e = _cache.entry(root, config)
    if not e:
        print(f"no cached run for [{config.key}]")
        sys.exit(2)
    res = _rebind.rebind(hunks, e, head)
    kept = len(hunks) - len(res.new) - len(res.rebound)
    print(
        f"[{config.key}] kept {kept} / rebound {len(res.rebound)} / gone "
        f"{len(res.gone)} / new {len(res.new)} — coverage "
        f"{kept + len(res.rebound)}/{len(hunks)}"
    )
    sys.exit(1 if res.new else 0)
