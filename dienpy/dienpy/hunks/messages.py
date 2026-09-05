"""Rewrite title/message of groups whose hunks changed since they were described (--all: every group).

`run --extend` and rebinding mark the groups they touch `stale`; this is the step that
turns an appended-to group back into an accurate commit message, one model call per group.
"""

from typing import Literal

from . import _cache, _config, _engine, _groups, _hunks, _rebind


def main(
    *dims: _config.Dim,
    all: bool = False,
    auth: Literal["login", "env"] | None = None,
) -> None:
    root = _hunks.git_root()
    hunks = _hunks.parse(root)
    head = _hunks.head_sha(root)
    _cache.prune(root, hunks, head)
    config = _config.resolve(dims, _cache.last_config(root))
    entry = _cache.entry(root, config)
    if not entry:
        raise SystemExit(f"no cached run for [{config.key}]")
    live = {h.id for h in hunks}
    groups = _groups.sanitize(_rebind.rebind(hunks, entry, head).groups, live)
    targets = [i for i, g in enumerate(groups) if all or g.get("stale")]
    if not targets:
        print(f"[{config.key}] no stale groups")
        return
    backend = _engine.backend_for(config, auth)
    by_id = {h.id: h for h in hunks}
    print(f"[{config.key}] describing {len(targets)} of {len(groups)} groups")
    for i in targets:
        own = [by_id[hid] for hid in groups[i]["hunks"] if hid in by_id]
        before = groups[i]["title"]
        groups[i] = _engine.describe(root, groups, i, own, config, backend)
        # persist after each call so a failure later keeps the descriptions already paid for
        _cache.set_entry(root, config, hunks, groups, head)
        arrow = "" if groups[i]["title"] == before else f"  (was: {before})"
        print(f"{len(own):2d} hunks  {groups[i]['title']}{arrow}")
