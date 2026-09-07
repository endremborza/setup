"""Patch-list helpers shared by the hunks commands: ids, sanitizing, selection, printing.

A patch is `{id, title, message, hunks, mixed?}`; its id is minted here once, when the
model's output is accepted, and is what nvim and the CLI address it by.
"""

import re
import secrets
from typing import Annotated

from protocli import Complete

_HUNK_ID = re.compile(r"^[0-9a-f]{12}(~\d+)?$")


def mint(patches: list[dict]) -> list[dict]:
    for p in patches:
        p.setdefault("id", secrets.token_hex(3))
    return patches


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
    """Patches named by id or 1-based position, in the order given."""
    out = []
    for tok in tokens:
        if tok.isdigit() and 1 <= int(tok) <= len(patches):
            out.append(patches[int(tok) - 1])
            continue
        found = [p for p in patches if p["id"] == tok]
        if not found:
            raise SystemExit(f"no patch '{tok}' in the current run")
        out.append(found[0])
    return out


def hunk_ids(patches: list[dict], tokens: tuple[str, ...], live: set[str]) -> list[str]:
    """Expand patch and hunk tokens into live hunk ids, deduplicated, in token order."""
    out: list[str] = []
    for tok in tokens:
        if _HUNK_ID.match(tok):
            if tok not in live:
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
    for i, p in enumerate(patches, 1):
        n = sum(1 for h in p["hunks"] if h in live)
        print(f"{i:2d} {p['id']}  {n:2d} hunks  {p['title']}")
        for m in p.get("mixed") or []:
            print(f"                 mixed {m['hunk']}: {m['note']}")


def completions() -> list[str]:
    from . import _cache, _hunks

    try:
        data = _cache.load(_hunks.git_root())
    except SystemExit:
        return []
    last = data and data.get("last")
    entry = data and last and data["analyses"].get(_cache.key(last))
    return [p["id"] for p in entry["patches"]] if entry else []


Target = Annotated[str, Complete(completions)]
