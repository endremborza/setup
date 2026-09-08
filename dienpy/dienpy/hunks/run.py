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

from . import _cache, _config, _engine, _hunks, _patches

_INCR_MIN_COVERAGE = 0.5


def _run_staged(dims: tuple[str, ...], auth: str | None, path: str) -> None:
    root = _hunks.git_root()
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


def describe_stale(
    root: str,
    patches: list[dict],
    hunks: list[_hunks.Hunk],
    config: _config.Config,
    backend,
) -> list[dict]:
    """Fresh title/message for every patch flagged `stale` by a placement."""
    recs = {h.id: h for h in hunks}
    for i, p in enumerate(patches):
        if not p.get("stale"):
            continue
        own = [recs[hid] for hid in p["hunks"] if hid in recs]
        patches[i] = _engine.describe(root, patches, i, own, config, backend)
    return patches


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
    root = _hunks.git_root()
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
    entry = None if force else _cache.entry(root, config)
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

    if entry and not new_ids:
        _cache.set_entry(root, config, all_hunks, existing)
        print("cached partition is current:")
        _patches.print_patches(existing, live)
        return

    incremental = extend or (kept >= _INCR_MIN_COVERAGE * len(scope) and kept > 0)
    if existing and not full and incremental:
        print(
            f"incremental: placing {len(new_ids)} new hunks into "
            f"{len(existing)} existing patches"
        )
        new_hunks = [h for h in hunks if h.id in new_ids]
        patches = _patches.sanitize(
            _engine.place(root, existing, new_hunks, config, backend), live
        )
        _cache.set_entry(root, config, all_hunks, _patches.mint(patches))
        patches = describe_stale(root, patches, all_hunks, config, backend)
    else:
        if extend:
            raise SystemExit(
                f"[{config.key}] no longer covers any of the diff — "
                "drop --extend to re-partition"
            )
        print(f"partitioning {len(hunks)} hunks...")
        # out-of-scope patches keep their hunks: a scoped run rewrites only its own part
        kept_patches = _patches.sanitize(existing, live - scope) if path else []
        patches = _patches.sanitize(
            kept_patches + _engine.partition(root, hunks, config, backend), live
        )

    _cache.set_entry(root, config, all_hunks, _patches.mint(patches))
    _patches.print_patches(patches, live)
