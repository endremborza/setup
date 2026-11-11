"""Show the ledger of captured calls: per tool, profile and model the calls, the failed ones,
the median and tail seconds and the tokens; --last N lists the newest calls instead."""

from collections import defaultdict
from typing import Any

from dienraw.out import table

from . import _ledger

# the share of answered calls the tail column covers, by nearest rank
TAIL = 0.95
_HEAD = (
    "tool",
    "profile",
    "model",
    "calls",
    "failed",
    "median s",
    "tail s",
    "in",
    "out",
    "last",
)
_ROW = (
    "at",
    "tool",
    "profile",
    "model",
    "seconds",
    "input_tokens",
    "output_tokens",
    "images",
    "cwd",
    "error",
)


def _rank(sorted_values: list[float], share: float) -> float:
    return sorted_values[min(len(sorted_values) - 1, int(share * len(sorted_values)))]


def main(*, tool: str = "", profile: str = "", last: int = 0) -> None:
    """--tool and --profile keep the calls whose tool key or profile starts with the text."""
    kept = [
        r
        for r in _ledger.rows()
        if str(r.get("tool", "")).startswith(tool)
        and str(r.get("profile", "")).startswith(profile)
    ]
    if last:
        print(
            table([tuple(str(r.get(k, "")) for k in _ROW) for r in kept[-last:]], _ROW)
        )
        return
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in kept:
        groups[(r.get("tool", ""), r.get("profile", ""), r.get("model", ""))].append(r)
    out = []
    for key, calls in sorted(groups.items()):
        answered = sorted(r["seconds"] for r in calls if not r.get("error"))
        out.append(
            (
                *key,
                len(calls),
                len(calls) - len(answered),
                f"{_rank(answered, 0.5):.2f}" if answered else "",
                f"{_rank(answered, TAIL):.2f}" if answered else "",
                sum(r.get("input_tokens", 0) for r in calls),
                sum(r.get("output_tokens", 0) for r in calls),
                calls[-1].get("at", ""),
            )
        )
    print(table(out, _HEAD))
