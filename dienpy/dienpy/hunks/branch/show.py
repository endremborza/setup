"""Show patch branches: every branch but the default one with its commits ahead, or one branch's log; --archived lists refs/landed and refs/dropped."""

import json as _json
from pathlib import Path

from dienpy._git import find_root

from .._hunks import repo
from . import _ops


def _branches(root: str, onto: str) -> list[dict]:
    r = repo(root)
    here = Path(root).resolve()
    rows = r.out(
        "for-each-ref",
        f"--format=%(if)%(HEAD)%(then)*%(else)-%(end)%09%(refname:short)%09%(worktreepath)%09%(ahead-behind:{onto})",
        "refs/heads",
    )
    out = []
    for row in rows.split("\n"):
        if not row:
            continue
        head, name, wt, ahead_behind = row.split("\t")
        if name == onto:
            continue
        out.append(
            {
                "name": name,
                "commits": int(ahead_behind.split()[0]),
                "stat": r.out("diff", "--shortstat", f"{onto}...{name}"),
                "current": head == "*",
                "worktree": wt if wt and Path(wt).resolve() != here else "",
            }
        )
    return out


def _archived(root: str) -> list[dict]:
    rows = repo(root).out(
        "for-each-ref",
        "--format=%(refname)%09%(objectname:short)%09%(committerdate:short)",
        "refs/landed",
        "refs/dropped",
    )
    return [
        {"ref": ref, "tip": tip, "date": date}
        for ref, tip, date in (r.split("\t") for r in rows.split("\n") if r)
    ]


def main(
    name: _ops.BranchName = "", *, archived: bool = False, json: bool = False
) -> None:
    root = find_root()
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
