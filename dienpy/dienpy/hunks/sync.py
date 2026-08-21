"""Rebind edited hunks to their change groups without re-analyzing (no model call).

Rebinding is config-independent, so bare `sync` reconciles every cached run; pass
dims to reconcile one and print its groups. This is what nvim calls when the diff
moves under a session.
"""

from . import _cache, _config, _groups, _hunks, _rebind


def get_completions(args: list[str]) -> list[str]:
    return [*_config.GRANULARITIES, *_config.CONTEXTS, *_config.MODELS]


def main(*dims: str) -> None:
    root = _hunks.git_root()
    hunks = _hunks.parse(root)
    head = _hunks.head_sha(root)
    _cache.prune(root, hunks, head)
    data = _cache.load(root)
    if not data or not data.get("analyses"):
        raise SystemExit("no cached regroup runs")

    keys = list(data["analyses"])
    if dims:
        key = _config.resolve(dims, _cache.last_config(root)).key
        if key not in keys:
            raise SystemExit(f"no cached run for [{key}]")
        keys = [key]

    live = {h.id for h in hunks}
    for key in keys:
        entry = data["analyses"][key]
        res = _rebind.rebind(hunks, entry, head)
        _cache.set_entry(
            root, _config.Config(**entry["config"]), hunks, res.groups, head
        )
        print(
            f"[{key}] carried {len(res.rebound)} / dropped {len(res.gone)} / "
            f"unassigned {len(res.new)}"
            + (f" / ambiguous {len(res.ambiguous)}" if res.ambiguous else "")
        )
        if dims:
            _groups.print_groups(res.groups, live)
