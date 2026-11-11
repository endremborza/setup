"""The ledger: one line per captured call (`send`), whoever made it, so what ran on this
machine, for which tool, on which profile and how long it took is read back by `moac ledger`.
It keeps no prompt and no reply.
"""

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

ENV_VAR = "MOAC_LEDGER"
PATH = Path(
    os.environ.get(ENV_VAR)
    or Path.home() / ".local" / "state" / "moac" / "ledger.jsonl"
)


def record(row: dict[str, Any]) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    with PATH.open("a") as f:
        f.write(json.dumps(row) + "\n")


def rows() -> Iterator[dict[str, Any]]:
    try:
        f = PATH.open()
    except FileNotFoundError:
        return
    with f:
        for line in f:
            yield json.loads(line)
