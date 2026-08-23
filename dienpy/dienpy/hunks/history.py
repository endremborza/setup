"""Describe past commits with AI: explicit hashes, or --since 7D / 50h."""

from datetime import datetime
from pathlib import Path
from typing import Annotated

from protocli import FILES

from .. import ai
from . import _hunks, _prompt

_SYSTEM = """\
Describe a series of git commits as a cohesive summary.

Rules:
- Output ONLY the summary — no preamble, explanation, or quotes
- 1-3 sentences or bullet points covering the key changes across the series
- Focus on what changed and why, not on individual commit hashes
"""


def main(
    *hashes: str,
    since: str = "",
    profile: ai.ProfileName = "",
    effort: ai.Effort = "",
    max_diff_chars: int = 0,
    out: Annotated[str, FILES] = "",
) -> None:
    root = _hunks.git_root()
    if since and hashes:
        raise SystemExit("pass commit hashes or --since, not both")
    if since:
        found = _hunks._git(
            root, ["log", f"--since={_prompt.parse_since(since)}", "--format=%H"]
        ).split()
        if not found:
            raise SystemExit(f"no commits since {since}")
        hashes = tuple(reversed(found))  # oldest first
    if not hashes:
        raise SystemExit("pass commit hashes or --since")

    backend = ai.resolve("commit", ai.Need(effort=effort), profile=profile)
    ctx = _prompt.message_context(root)
    entries = [_prompt.commit_entry(root, h, max_diff_chars) for h in hashes]
    descriptions: list[str] = []
    for batch in _prompt.make_batches(entries):
        user = ctx + "\n\n" + "\n\n".join(batch)
        desc = ai.send(backend, _SYSTEM, user, temperature=0.3, cwd=root)
        print(desc)
        descriptions.append(str(desc))

    if out:
        span = since or f"{len(hashes)} commits"
        header = f"## {span} history — {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        block = header + "\n\n" + "\n\n---\n\n".join(descriptions) + "\n"
        target = Path(out)
        existing = target.read_text() + "\n" if target.exists() else ""
        target.write_text(existing + block)
