"""List cached regroup runs with coverage against the current diff."""

import datetime

from . import _cache, _hunks


def main() -> None:
    root = _hunks.git_root()
    current = {h.id for h in _hunks.parse(root)}
    _cache.prune(root, current)
    data = _cache.load(root)
    if not data or not data.get("analyses"):
        print("no cached regroup runs")
        return
    rows = sorted(
        data["analyses"].items(), key=lambda kv: kv[1].get("time") or 0, reverse=True
    )
    for key, e in rows:
        covered = sum(1 for i in current if i in set(e["ids"]))
        when = e.get("time")
        stamp = (
            datetime.datetime.fromtimestamp(when).strftime("%m-%d %H:%M")
            if when
            else "?"
        )
        print(
            f"{key:<30} {len(e['groups'])} groups  "
            f"covers {covered}/{len(current)} hunks  {stamp}"
        )
