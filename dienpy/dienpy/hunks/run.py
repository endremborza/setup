"""Analyze uncommitted changes into AI change groups (writes the cache nvim's :Regroup reads)."""

from typing import Literal

from . import _cache, _config, _engine, _hunks

_INCR_MIN_COVERAGE = 0.5


def get_completions(args: list[str]) -> list[str]:
    return [*_config.GRANULARITIES, *_config.CONTEXTS, *_config.MODELS, "--force", "--full", "--auth"]


def _print_groups(groups: list[dict], live: set[str]) -> None:
    for g in groups:
        n = sum(1 for i in g["hunks"] if i in live)
        print(f"{n:2d} hunks  {g['title']}")
        for m in g.get("mixed") or []:
            print(f"          mixed {m['hunk']}: {m['note']}")


def _sanitize(groups: list[dict], live: set[str]) -> list[dict]:
    """Drop hunk ids gone from the diff, drop emptied groups, merge same-titled groups."""
    out: list[dict] = []
    by_title: dict[str, dict] = {}
    for g in groups:
        hunks = [i for i in g["hunks"] if i in live]
        if not hunks:
            continue
        mixed = [m for m in g.get("mixed") or [] if m["hunk"] in live]
        tgt = by_title.get(g["title"])
        if tgt is None:
            tgt = {k: v for k, v in g.items() if k != "mixed"}
            tgt["hunks"] = hunks
            by_title[g["title"]] = tgt
            out.append(tgt)
        else:
            tgt["hunks"] = tgt["hunks"] + hunks
        if mixed:
            tgt["mixed"] = (tgt.get("mixed") or []) + mixed
    return out


def main(
    *dims: str,
    force: bool = False,
    full: bool = False,
    auth: Literal["login", "env"] = "login",
) -> None:
    root = _hunks.git_root()
    hunks = _hunks.parse(root)
    _cache.prune(root, {h.id for h in hunks})
    if not hunks:
        print("no uncommitted changes")
        return
    config = _config.resolve(dims, _cache.last_config(root))
    current = [h.id for h in hunks]
    print(f"regroup: {len(hunks)} hunks [{config.key}]")

    entry = None if force else _cache.entry(root, config)
    known = set(entry["ids"]) if entry else set()
    new_ids = {i for i in current if i not in known}
    kept = len(current) - len(new_ids)
    live = set(current)

    if entry and not new_ids:
        groups = _sanitize(entry["groups"], live)
        if groups == entry["groups"]:
            print("cached analysis is current:")
        else:
            _cache.set_entry(root, config, current, groups)
            print("cached analysis is current (pruned hunks no longer in the diff):")
        _print_groups(groups, live)
        return

    if entry and not full and kept >= _INCR_MIN_COVERAGE * len(current) and kept > 0:
        existing = _sanitize(entry["groups"], live)
        print(
            f"incremental: placing {len(new_ids)} new hunks into "
            f"{len(existing)} existing groups"
        )
        new_hunks = [h for h in hunks if h.id in new_ids]
        groups = _sanitize(
            _engine.analyze_incremental(root, existing, new_hunks, config, auth), live
        )
    else:
        print(f"analyzing {len(hunks)} hunks...")
        groups = _engine.analyze_full(root, hunks, config, auth)

    _cache.set_entry(root, config, current, groups)
    _print_groups(groups, live)
