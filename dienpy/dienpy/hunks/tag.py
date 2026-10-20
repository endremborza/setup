"""Suggest the `branb tag` command for the commits since the last tag: release notes and a major/minor/bug bump."""

import re
import shlex

from dienpy._git import find_root

from .. import ai
from . import _prompt
from ._engine import MAX_PROMPT_CHARS
from ._hunks import repo

BUMPS = ("major", "minor", "bug")

_RULES = """\
Write the release notes for the commits below, everything since the last release, and choose the version bump.

Rules:
- "bump": "major" when a change breaks the public API, CLI or documented behavior for existing users; "minor" when it adds backward-compatible functionality; "bug" when it only fixes bugs or touches internals, docs, tests or CI.
- "reason": one sentence naming the change that decides the bump.
- "notes": a markdown bullet list, one line per user-facing change, breaking changes first and marked **Breaking:**; commits serving one change are one bullet; internal churn (formatting, CI, tests) is left out unless it is the whole release.
- No commit hashes, headings or preamble in the notes."""

_SCHEMA = {
    "type": "object",
    "properties": {
        "bump": {"type": "string", "enum": list(BUMPS)},
        "reason": {"type": "string"},
        "notes": {"type": "string"},
    },
    "required": ["bump", "reason", "notes"],
}


def bumped(tag: str, bump: str) -> str | None:
    m = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", tag)
    if not m:
        return None
    major, minor, bug = map(int, m.groups())
    parts = {
        "major": (major + 1, 0, 0),
        "minor": (major, minor + 1, 0),
        "bug": (major, minor, bug + 1),
    }[bump]
    return "v" + ".".join(map(str, parts))


def _entries(root: str, hashes: list[str]) -> list[str]:
    """Full diffs while the series fits a prompt, else each diff cut to an equal share."""
    entries = [_prompt.commit_entry(root, h) for h in hashes]
    if sum(map(len, entries)) <= MAX_PROMPT_CHARS:
        return entries
    share = MAX_PROMPT_CHARS // len(hashes)
    return [_prompt.commit_entry(root, h, share) for h in hashes]


def build_prompt(root: str, tag: str | None, hashes: list[str]) -> str:
    parts = [_RULES, ""]
    ctx = _prompt.project_context(root)
    if ctx:
        parts += [f"Project context ({ctx[0]}):", ctx[1], ""]
    parts += [f"Last release: {tag or 'none'}", "", "Commits since, oldest first:"]
    return "\n".join(parts + _entries(root, hashes))


def main(*, profile: ai.ProfileName = "", effort: ai.Effort = "") -> None:
    root = find_root()
    r = repo(root)
    tag = r.maybe("describe", "--tags", "--abbrev=0", "--match", "v[0-9]*")
    hashes = r.out(
        "log",
        "--reverse",
        "--no-merges",
        "--format=%H",
        f"{tag}..HEAD" if tag else "HEAD",
    ).split()
    if not hashes:
        raise SystemExit(f"no commits since {tag}")

    backend = ai.resolve(
        "commit", ai.Need(schema=True, effort=effort, timeout=900), profile=profile
    )
    print(f"tag: {len(hashes)} commits since {tag or 'the first commit'}")
    payload = ai.send(
        backend,
        "",
        build_prompt(root, tag, hashes),
        schema=_SCHEMA,
        max_tokens=4096,
        cwd=root,
    )
    if not isinstance(payload, dict) or payload.get("bump") not in BUMPS:
        raise SystemExit(f"no valid bump in model output: {payload!r}")

    bump = payload["bump"]
    target = bumped(tag, bump) if tag else None
    transition = f" {tag} → {target}" if target else ""
    print(f"\n{bump}{transition}: {str(payload['reason']).strip()}\n")
    print(f"branb tag {shlex.quote(str(payload['notes']).strip())} {bump}")
