"""Shared prompt material for message-writing leaves: repo context, style anchor, commit rendering."""

import re
from pathlib import Path

from . import _hunks

BATCH_CHAR_LIMIT = 1500


def project_context(root: str) -> tuple[str, str] | None:
    for name in ("AGENTS.md", "CLAUDE.md"):
        p = Path(root) / name
        if p.exists():
            return name, p.read_text()
    return None


def subjects(root: str) -> str:
    return _hunks._git(root, ["log", "--format=%s", "-15"]).strip()


def message_context(root: str) -> str:
    """Project context + recent subjects — the preamble every message-writing prompt shares."""
    parts = []
    ctx = project_context(root)
    if ctx:
        parts += [f"Project context ({ctx[0]}):", ctx[1], ""]
    parts += ["Recent commit subjects for style:", subjects(root)]
    return "\n".join(parts)


def commit_entry(root: str, hash: str, max_diff_chars: int = 0) -> str:
    msg = _hunks._git(root, ["log", "-1", "--format=%B", hash]).strip()
    diff = _hunks._git(root, ["show", hash])
    if max_diff_chars and len(diff) > max_diff_chars:
        diff = diff[:max_diff_chars] + "\n... [truncated]"
    return (
        f'<commit hash="{hash}">\n'
        f"<message>\n{msg}\n</message>\n"
        f"<diff>\n{diff}\n</diff>\n"
        f"</commit>"
    )


def make_batches(entries: list[str], limit: int = BATCH_CHAR_LIMIT) -> list[list[str]]:
    batches: list[list[str]] = []
    current: list[str] = []
    current_len = 0
    for entry in entries:
        if current and current_len + len(entry) > limit:
            batches.append(current)
            current, current_len = [entry], len(entry)
        else:
            current.append(entry)
            current_len += len(entry)
    if current:
        batches.append(current)
    return batches


def parse_since(since: str) -> str:
    m = re.fullmatch(r"(\d+)([Dh])", since, re.IGNORECASE)
    if not m:
        raise SystemExit(f"Invalid --since format '{since}'. Use e.g. 7D or 50h.")
    n, unit = int(m.group(1)), m.group(2).lower()
    return f"{n} days ago" if unit == "d" else f"{n} hours ago"
