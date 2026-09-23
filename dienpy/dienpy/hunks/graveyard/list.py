"""List graveyard entries, newest first; --json is what nvim reads."""

import json as _json

from dienpy._git import find_root

from . import _entries


def main(*, json: bool = False) -> None:
    rows = _entries.entries(find_root())
    if json:
        print(_json.dumps(rows))
        return
    if not rows:
        print("graveyard is empty")
    for e in rows:
        print(f"{e['hash'][:7]}  {e['ref']:<10} {e['age']:<16} {e['title']}")
