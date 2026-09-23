"""Partition uncommitted changes into patches (writes the cache nvim's :Regroup reads).

`--path <dir|file>` scopes the partition to one subtree: only those hunks reach the model,
patches covering the rest of the diff are left untouched, and the entry records the partial
coverage — so the remaining hunks land incrementally on the next unscoped run.
`--extend` brings one cached run up to date and nothing else: it places only the new hunks
into the existing patches and re-describes the patches it appended to, refusing rather
than re-partitioning — the cheap, predictable update nvim binds to a key.
`--staged` partitions the index instead and prints full messages without touching the
cache — the "message for what I'm about to commit" path.
"""

from typing import Annotated, Literal

from protocli import FILES

from dienpy._git import find_root

from . import _cache, _config, _engine, _hunks, _patches

_INCR_MIN_COVERAGE = 0.5


def _run_staged(dims: tuple[str, ...], auth: str | None, path: str) -> None:
    root = find_root()
    hunks = _hunks.under(_hunks.parse(root, staged=True), path)
    if not hunks:
        raise SystemExit(f"no staged changes{f' under {path}' if path else ''}")
    config = _config.resolve(dims, _cache.last_config(root))
    backend = _engine.backend_for(config, auth)
    print(f"regroup: {len(hunks)} staged hunks [{config.key}]")
    for p in _engine.partition(root, hunks, config, backend):
        print(f"\n{len(p['hunks']):2d} hunks  {p['title']}")
        if p.get("message"):
            print(p["message"])


def _fresh(root: str, config: _config.Config, live: set[str]) -> list[dict]:
    """The entry as it is after a model call: a `patch move` made meanwhile is kept."""
    entry = _cache.entry(root, config)
    return _patches.sanitize(entry["patches"], live) if entry else []


def main(
    *dims: _config.Dim,
    force: bool = False,
    full: bool = False,
    extend: bool = False,
    auth: Literal["login", "env"] | None = None,
    path: Annotated[str, FILES] = "",
    staged: bool = False,
) -> None:
    if staged:
        _run_staged(dims, auth, path)
        return
    root = find_root()
    all_hunks = _hunks.parse(root)
    _cache.prune(root, all_hunks)
    if not all_hunks:
        print("no uncommitted changes")
        return
    hunks = _hunks.under(all_hunks, path)
    if not hunks:
        print(f"no uncommitted changes under {path}")
        return
    config = _config.resolve(dims, _cache.last_config(root))
    entry = _cache.entry(root, config)
    if extend:
        if force or full:
            raise SystemExit("--extend never re-partitions: drop --force/--full")
        if not entry:
            raise _cache.missing(root, config)
    backend = _engine.backend_for(config, auth)
    # patches are sanitized against the whole diff so a scoped run never evicts
    # out-of-scope patches; only in-scope hunks are handed to the model
    live = {h.id for h in all_hunks}
    scope = {h.id for h in hunks}
    extent = f" of {len(all_hunks)} under {path}" if path else ""
    print(f"regroup: {len(hunks)} hunks{extent} [{config.key}]")

    existing = _patches.sanitize(entry["patches"], live) if entry else []
    placed = {hid for p in existing for hid in p["hunks"]}
    new_ids = scope - placed
    kept = len(scope) - len(new_ids)

    if entry and not new_ids and not force:
        # a placement interrupted before its re-describe leaves patches flagged stale
        existing = _engine.describe_stale(root, existing, all_hunks, config, backend)
        _cache.set_entry(root, config, all_hunks, existing)
        print("cached partition is current:")
        _patches.print_patches(existing, live)
        return

    incremental = extend or (kept >= _INCR_MIN_COVERAGE * len(scope) and kept > 0)
    if existing and incremental and not (force or full):
        print(
            f"incremental: placing {len(new_ids)} new hunks into "
            f"{len(existing)} existing patches"
        )
        new_hunks = [h for h in hunks if h.id in new_ids]
        groups = _engine.place(root, existing, new_hunks, config, backend)
        patches = _patches.sanitize(
            _engine.merge_placement(_fresh(root, config, live), groups, existing), live
        )
        _cache.set_entry(root, config, all_hunks, _patches.mint(patches))
        patches = _engine.describe_stale(root, patches, all_hunks, config, backend)
    else:
        if extend:
            raise SystemExit(
                f"[{config.key}] no longer covers any of the diff — "
                "drop --extend to re-partition"
            )
        print(f"partitioning {len(hunks)} hunks...")
        groups = _engine.partition(root, hunks, config, backend)
        # out-of-scope patches keep their hunks: a scoped run rewrites only its own part
        kept_patches = (
            _patches.sanitize(_fresh(root, config, live), live - scope) if path else []
        )
        patches = _patches.sanitize(kept_patches + groups, live)

    _cache.set_entry(root, config, all_hunks, _patches.mint(patches))
    _patches.print_patches(patches, live)
