"""Carry group membership across worktree edits, by HEAD-side anchor. No model call.

A hunk id hashes its body, so any edit inside a hunk mints a new id and retires the
old one. The `@@ -start,count` range is HEAD-side: it cannot move while the worktree
is edited, so it survives the edit that the id does not. Anchors are only comparable
under the same HEAD — after a commit they are re-derived and ids carry membership by
hash, as they always did.
"""

import copy
from dataclasses import dataclass, field

from ._hunks import Hunk

Anchor = list  # [path, head_start, head_count]


@dataclass
class Result:
    groups: list[dict]
    # new id -> the id it inherited membership from
    rebound: dict[str, str] = field(default_factory=dict)
    # rebound ids whose anchor spanned more than one group
    ambiguous: list[str] = field(default_factory=list)
    gone: list[str] = field(default_factory=list)  # grouped ids with no successor
    new: list[str] = field(default_factory=list)  # live ids belonging to no group


def anchors(hunks: list[Hunk]) -> dict[str, Anchor]:
    return {h.id: [h.path, h.head_start, h.head_count] for h in hunks}


def overlap(a: Anchor, b: Anchor) -> int:
    if a[0] != b[0]:
        return 0
    if a[2] == 0 or b[2] == 0:  # new/binary file: the path is the anchor
        return 1
    return max(0, min(a[1] + a[2], b[1] + b[2]) - max(a[1], b[1]))


def _remap_mixed(
    mixed: list[dict], live: set[str], succ: dict[str, list[str]]
) -> list[dict]:
    out = []
    for m in mixed:
        if m["hunk"] in live:
            out.append(m)
        elif succ.get(m["hunk"]):
            out.append({**m, "hunk": succ[m["hunk"]][0]})
    return out


def rebind(hunks: list[Hunk], entry: dict, head: str) -> Result:
    groups = copy.deepcopy(entry["groups"])
    live = {h.id for h in hunks}
    owner: dict[str, int] = {}
    for gi, g in enumerate(groups):
        for hid in g["hunks"]:
            owner.setdefault(hid, gi)

    res = Result(groups)
    res.gone = [hid for hid in owner if hid not in live]
    fresh = [h for h in hunks if h.id not in owner]
    cur, old = anchors(hunks), entry.get("anchors") or {}
    succ: dict[str, list[str]] = {}

    if head and entry.get("head") == head:
        for h in fresh:
            best, best_w, groups_hit = None, 0, set()
            for hid in res.gone:
                w = overlap(cur[h.id], old[hid]) if hid in old else 0
                if w:
                    groups_hit.add(owner[hid])
                    if w > best_w:
                        best, best_w = hid, w
            if best is None:
                continue
            res.rebound[h.id] = best
            succ.setdefault(best, []).append(h.id)
            if len(groups_hit) > 1:
                res.ambiguous.append(h.id)

    res.new = [h.id for h in fresh if h.id not in res.rebound]
    res.gone = [hid for hid in res.gone if hid not in succ]

    for gi, g in enumerate(groups):
        rewritten, seen = [], set()
        for hid in g["hunks"]:
            for out in [hid] if hid in live else succ.get(hid, []):
                if out not in seen:
                    seen.add(out)
                    rewritten.append(out)
        if any(hid not in live for hid in g["hunks"]) and rewritten != g["hunks"]:
            g["stale"] = True
        g["hunks"] = rewritten
        if g.get("mixed"):
            g["mixed"] = _remap_mixed(g["mixed"], live, succ)
        flagged = [i for i in g.get("ambiguous") or [] if i in live]
        flagged += [i for i in res.ambiguous if owner[res.rebound[i]] == gi]
        if flagged:
            g["ambiguous"] = sorted(set(flagged))
        else:
            g.pop("ambiguous", None)
    return res
