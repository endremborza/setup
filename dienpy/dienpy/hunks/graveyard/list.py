"""List graveyard entries, newest first; --json is what nvim reads."""

import json as _json

from dienpy._git import find_root
from dienpy._out import table

from . import _entries


def main(*, json: bool = False) -> None:
    rows = _entries.entries(find_root())
    if json:
        print(_json.dumps(rows))
        return
    if not rows:
        print("graveyard is empty")
        return
    print(table((e["hash"][:7], e["ref"], e["age"], e["title"]) for e in rows))
