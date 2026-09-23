"""List cached runs with coverage against the current diff; --json is what nvim reads."""

import datetime
import json as _json

from dienpy._git import find_root

from . import _cache, _hunks


def main(*, json: bool = False) -> None:
    root = find_root()
    hunks = _hunks.parse(root)
    current = {h.id for h in hunks}
    _cache.prune(root, hunks)
    data = _cache.load(root) or {"analyses": {}, "last": None}
    if json:
        print(
            _json.dumps(
                {
                    "root": root,
                    "branch": _hunks.repo(root).out("branch", "--show-current"),
                    "hunks": [h.as_json() for h in hunks],
                    "staged": [h.id for h in _hunks.parse(root, staged=True)],
                    "runs": data["analyses"],
                    "last": data.get("last"),
                }
            )
        )
        return
    if not data["analyses"]:
        print("no cached regroup runs")
        return
    rows = sorted(
        data["analyses"].items(), key=lambda kv: kv[1].get("time") or 0, reverse=True
    )
    for key, e in rows:
        covered = len(current.intersection(e["ids"]))
        when = e.get("time")
        stamp = (
            datetime.datetime.fromtimestamp(when).strftime("%m-%d %H:%M")
            if when
            else "?"
        )
        print(
            f"{key:<30} {len(e['patches'])} patches  "
            f"covers {covered}/{len(current)} hunks  {stamp}"
        )
