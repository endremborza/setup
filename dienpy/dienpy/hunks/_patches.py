"""Patch-list helpers shared by the hunks commands: ids, sanitizing, selection, printing.

A patch is `{id, title, message, hunks, mixed?}`; its id is a number minted once, when the
patch enters a run, never reused within that run, and is what nvim and the CLI address it by.
"""

import re
from typing import Annotated

from protocli import Complete

from dienpy._out import table

_HUNK_ID = re.compile(r"^[0-9a-f]{12}(~\d+)?$")


def mint(patches: list[dict], next_id: int) -> int:
    """Number the patches that have no id yet, from `next_id`; returns the next free number."""
    for p in patches:
        if "id" not in p:
            p["id"] = str(next_id)
            next_id += 1
    return next_id


def sanitize(patches: list[dict], live: set[str]) -> list[dict]:
    """Drop hunk ids gone from the diff, drop emptied patches, merge same-titled ones."""
    out: list[dict] = []
    by_title: dict[str, dict] = {}
    for p in patches:
        hunks = [i for i in p["hunks"] if i in live]
        if not hunks:
            continue
        mixed = [m for m in p.get("mixed") or [] if m["hunk"] in live]
        tgt = by_title.get(p["title"])
        if tgt is None:
            tgt = {k: v for k, v in p.items() if k != "mixed"}
            tgt["hunks"] = hunks
            by_title[p["title"]] = tgt
            out.append(tgt)
        else:
            tgt["hunks"] = tgt["hunks"] + hunks
        if mixed:
            tgt["mixed"] = (tgt.get("mixed") or []) + mixed
    return out


def select(patches: list[dict], tokens: tuple[str, ...]) -> list[dict]:
    """Patches named by id, in the order given."""
    by_id = {p["id"]: p for p in patches}
    missing = [t for t in tokens if t not in by_id]
    if missing:
        raise SystemExit(f"no patch '{missing[0]}' in the current run")
    return [by_id[t] for t in tokens]


def hunk_ids(
    patches: list[dict], tokens: tuple[str, ...], live: set[str], known: set[str]
) -> list[str]:
    """Expand patch and hunk tokens into hunk ids, deduplicated, in token order: a
    patch contributes its live hunks, a bare id must be one of `known`."""
    out: list[str] = []
    for tok in tokens:
        if _HUNK_ID.match(tok):
            if tok not in known:
                raise SystemExit(f"hunk {tok} is not in the current diff")
            ids = [tok]
        else:
            ids = [i for i in select(patches, (tok,))[0]["hunks"] if i in live]
        out += [i for i in ids if i not in out]
    return out


def message(p: dict) -> str:
    body = (p.get("message") or "").strip()
    return p["title"] + ("\n\n" + body if body else "") + "\n"


def print_patches(patches: list[dict], live: set[str]) -> None:
    """One row per patch, its mixed hunks as indented rows under the title."""
    rows = []
    for p in patches:
        n = sum(1 for h in p["hunks"] if h in live)
        rows.append((p["id"], f"{n} hunks", p["title"]))
        rows += [
            ("", "", f"  mixed {m['hunk']}: {m['note']}") for m in p.get("mixed") or []
        ]
    if rows:
        print(table(rows, align=">>"))


def completions() -> list[str]:
    from dienpy._git import find_root

    from . import _cache, _config

    try:
        data = _cache.load(find_root())
    except SystemExit:
        return []
    last = data and data.get("last")
    entry = data and last and data["analyses"].get(_config.Config(**last).key)
    return [p["id"] for p in entry["patches"]] if entry else []


Target = Annotated[str, Complete(completions)]
