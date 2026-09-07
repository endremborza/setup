"""Show patch branches: every branch but the default one with its commits ahead, or one branch's log; --archived lists refs/landed and refs/dropped."""

import json as _json

from .. import _hunks
from . import _ops


def _branches(root: str, onto: str) -> list[dict]:
    out = []
    cur = _ops.current(root)
    for name in _ops.git(
        root, "for-each-ref", "--format=%(refname:short)", "refs/heads"
    ).split("\n"):
        if not name or name == onto:
            continue
        wt = _ops.worktree_of(root, name)
        out.append(
            {
                "name": name,
                "commits": int(
                    _ops.git(root, "rev-list", "--count", f"{onto}..{name}")
                ),
                "stat": _ops.git(root, "diff", "--shortstat", f"{onto}...{name}"),
                "current": name == cur,
                "worktree": str(wt) if wt else "",
            }
        )
    return out


def _archived(root: str) -> list[dict]:
    rows = _ops.git(
        root,
        "for-each-ref",
        "--format=%(refname)%09%(objectname:short)%09%(committerdate:short)",
        "refs/landed",
        "refs/dropped",
    )
    return [
        {"ref": ref, "tip": tip, "date": date}
        for ref, tip, date in (r.split("\t") for r in rows.split("\n") if r)
    ]


def main(name: str = "", *, archived: bool = False, json: bool = False) -> None:
    root = _hunks.git_root()
    onto = _ops.default(root)
    if name:
        ref = name if _ops.exists(root, name) else f"refs/landed/{name}"
        print(_ops.summary(root, onto, ref))
        return
    rows = _archived(root) if archived else _branches(root, onto)
    if json:
        print(_json.dumps(rows))
    elif not rows:
        print(
            "no archived patch branches"
            if archived
            else f"no patch branches beyond {onto}"
        )
    elif archived:
        for r in rows:
            print(f"{r['ref']:<40} {r['tip']}  {r['date']}")
    else:
        for r in rows:
            mark = "*" if r["current"] else " "
            wt = f"  [{r['worktree']}]" if r["worktree"] else ""
            print(f"{mark} {r['name']:<30} {r['commits']:3d} commits  {r['stat']}{wt}")
