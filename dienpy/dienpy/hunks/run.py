"""Analyze uncommitted changes into AI change groups (writes the cache nvim's :Regroup reads).

`--path <dir|file>` scopes the analysis to one subtree: only those hunks reach the model,
groups covering the rest of the diff are left untouched, and the entry records the partial
coverage — so the remaining hunks land incrementally on the next unscoped run.
"""

from typing import Literal

from protocli import FILE_COMPLETION

from . import _cache, _config, _engine, _groups, _hunks, _rebind

_INCR_MIN_COVERAGE = 0.5


def get_completions(args: list[str]) -> list[str]:
    if args and args[-1] == "--path":
        return [FILE_COMPLETION]
    return [
        *_config.GRANULARITIES,
        *_config.CONTEXTS,
        *_config.MODELS,
        "--force",
        "--full",
        "--auth",
        "--path",
    ]


def main(
    *dims: str,
    force: bool = False,
    full: bool = False,
    auth: Literal["login", "env"] = "login",
    path: str = "",
) -> None:
    root = _hunks.git_root()
    all_hunks = _hunks.parse(root)
    head = _hunks.head_sha(root)
    _cache.prune(root, all_hunks, head)
    if not all_hunks:
        print("no uncommitted changes")
        return
    hunks = _hunks.under(all_hunks, path)
    if not hunks:
        print(f"no uncommitted changes under {path}")
        return
    config = _config.resolve(dims, _cache.last_config(root))
    # groups are sanitized against the whole diff so a scoped run never evicts
    # out-of-scope groups; only in-scope hunks are handed to the model
    live = {h.id for h in all_hunks}
    scope = {h.id for h in hunks}
    extent = f" of {len(all_hunks)} under {path}" if path else ""
    print(f"regroup: {len(hunks)} hunks{extent} [{config.key}]")
    _cache.touch_last(root, config)

    entry = None if force else _cache.entry(root, config)
    existing: list[dict] = []
    new_ids: set[str] = scope
    if entry:
        res = _rebind.rebind(all_hunks, entry, head)
        if res.rebound:
            print(f"carried {len(res.rebound)} edited hunk(s) into their groups")
        existing = _groups.sanitize(res.groups, live)
        new_ids = set(res.new) & scope
    kept = len(scope) - len(new_ids)

    if entry and not new_ids:
        _cache.set_entry(root, config, all_hunks, existing, head)
        print("cached analysis is current:")
        _groups.print_groups(existing, live)
        return

    if existing and not full and kept >= _INCR_MIN_COVERAGE * len(scope) and kept > 0:
        print(
            f"incremental: placing {len(new_ids)} new hunks into "
            f"{len(existing)} existing groups"
        )
        new_hunks = [h for h in hunks if h.id in new_ids]
        groups = _groups.sanitize(
            _engine.analyze_incremental(root, existing, new_hunks, config, auth), live
        )
    else:
        print(f"analyzing {len(hunks)} hunks...")
        # out-of-scope groups keep their hunks: a scoped run rewrites only its own part
        kept_groups = _groups.sanitize(existing, live - scope) if path else []
        groups = _groups.sanitize(
            kept_groups + _engine.analyze_full(root, hunks, config, auth), live
        )

    _cache.set_entry(root, config, all_hunks, groups, head)
    _groups.print_groups(groups, live)
