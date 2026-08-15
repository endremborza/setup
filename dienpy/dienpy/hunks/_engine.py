"""Prompt assembly, claude CLI invocation, validation, and incremental merge."""

import copy
import json
import os
import subprocess
from pathlib import Path

from ._config import GRANULARITIES, Config
from ._hunks import Hunk

MAX_PROMPT_CHARS = 300000

_GROUP_PROPS = {
    "title": {"type": "string"},
    "message": {"type": "string"},
    "hunks": {"type": "array", "items": {"type": "string"}},
    "mixed": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {"hunk": {"type": "string"}, "note": {"type": "string"}},
            "required": ["hunk", "note"],
        },
    },
}

_FULL_RULES = """\
Group these git hunks into change groups (future commits).

Rules:
- Every hunk id below appears in exactly one group's "hunks" array; never dropped, never duplicated.
- Group by semantic concern, not by file: hunks from one file can belong to different groups.
- If a single hunk mixes two distinct concerns, assign it to the dominant one and record it in that group's "mixed" array with a note naming the foreign part.
- "title": a commit subject line (<= 72 chars) in the style of the recent subjects below.
- "message": the commit body, what changed and why; do not restate the title.
- Order groups so foundational changes come before things built on them."""

_INCR_RULES = """\
These hunks are NEW since a previous grouping of this diff. Place each new hunk.

Rules:
- Every new hunk id below appears in exactly one returned group's "hunks" array; never dropped, never duplicated.
- To add new hunks to an existing group, return a group with "extends": <existing group number> containing only those new hunk ids.
- For new hunks belonging to no existing group, return a new group (no "extends") with title/message in the established style.
- Do not restate hunks that are already grouped."""


def _schema(incremental: bool) -> str:
    props = dict(_GROUP_PROPS)
    if incremental:
        props["extends"] = {"type": "integer"}
    return json.dumps(
        {
            "type": "object",
            "properties": {
                "groups": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": props,
                        "required": ["title", "message", "hunks"],
                    },
                }
            },
            "required": ["groups"],
        }
    )


def _project_context(root: str) -> tuple[str, str] | None:
    for name in ("AGENTS.md", "CLAUDE.md"):
        p = Path(root) / name
        if p.exists():
            return name, p.read_text()
    return None


def _subjects(root: str) -> str:
    res = subprocess.run(
        ["git", "log", "--format=%s", "-15"], capture_output=True, text=True, cwd=root
    )
    return res.stdout.strip()


def _prompt_head(root: str, config: Config, rules: str) -> list[str]:
    parts = [
        rules,
        "",
        f'Granularity "{config.granularity}": {GRANULARITIES[config.granularity]}.',
    ]
    if config.context == "explore":
        parts += [
            "",
            "You may read files in this repository (read-only) to understand the "
            "changes before grouping.",
        ]
    if config.context != "bare":
        ctx = _project_context(root)
        if ctx:
            parts += ["", f"Project context ({ctx[0]}):", ctx[1]]
    parts += ["", "Recent commit subjects for style:", _subjects(root)]
    return parts


def _hunk_block(hunks: list[Hunk]) -> list[str]:
    parts = []
    for h in hunks:
        parts += ["", f"[{h.id}] {h.path}", h.text]
    return parts


def build_full_prompt(
    root: str, hunks: list[Hunk], config: Config, feedback: str | None
) -> str:
    parts = _prompt_head(root, config, _FULL_RULES) + ["", "Hunks:"]
    parts += _hunk_block(hunks)
    if feedback:
        parts += ["", feedback]
    return "\n".join(parts)


def build_incremental_prompt(
    root: str,
    groups: list[dict],
    new_hunks: list[Hunk],
    config: Config,
    feedback: str | None,
) -> str:
    parts = _prompt_head(root, config, _INCR_RULES) + ["", "Existing groups:"]
    for i, g in enumerate(groups, 1):
        parts.append(f"{i}. {g['title']}")
        for line in (g.get("message") or "").split("\n"):
            parts.append(f"   {line}")
    parts += ["", "New hunks:"]
    parts += _hunk_block(new_hunks)
    if feedback:
        parts += ["", feedback]
    return "\n".join(parts)


def _failure_report(res: subprocess.CompletedProcess) -> str:
    parts = []
    try:
        outer = json.loads(res.stdout or "")
        if isinstance(outer.get("result"), str):
            parts.append(outer["result"])
    except json.JSONDecodeError:
        if res.stdout and res.stdout.strip():
            parts.append(res.stdout.strip()[-400:])
    if res.stderr and res.stderr.strip():
        parts.append(res.stderr.strip()[-400:])
    return "\n".join(parts) or f"exit code {res.returncode}"


def _call(
    root: str,
    prompt: str,
    config: Config,
    auth: str,
    incremental: bool,
    timeout: int,
) -> list[dict]:
    if len(prompt) > MAX_PROMPT_CHARS:
        raise SystemExit(
            f"diff too large for one analysis: {len(prompt)} chars "
            f"(limit {MAX_PROMPT_CHARS})"
        )
    cmd = [
        "claude",
        "-p",
        "--output-format",
        "json",
        "--json-schema",
        _schema(incremental),
        "--model",
        config.model,
        "--tools",
        "Read,Grep,Glob" if config.context == "explore" else "",
    ]
    env = os.environ.copy()
    if auth == "login":
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
    try:
        res = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            cwd=root,
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise SystemExit(f"claude timed out after {timeout}s")
    if res.returncode != 0:
        raise SystemExit("claude failed: " + _failure_report(res))
    outer = json.loads(res.stdout)
    if outer.get("is_error"):
        raise SystemExit(f"claude error: {outer.get('result')}")
    payload = outer.get("structured_output")
    if payload is None and isinstance(outer.get("result"), str):
        try:
            payload = json.loads(outer["result"])
        except json.JSONDecodeError:
            payload = None
    if not isinstance(payload, dict) or not isinstance(payload.get("groups"), list):
        raise SystemExit("no structured groups in claude output")
    return payload["groups"]


def _timeout(config: Config) -> int:
    return 1200 if config.context == "explore" else 900


def _validate_full(hunks: list[Hunk], groups: list[dict]) -> str | None:
    known = {h.id: h for h in hunks}
    assigned: set[str] = set()
    problems = []
    for gi, g in enumerate(groups, 1):
        for hid in g["hunks"]:
            if hid not in known:
                problems.append(f"group {gi} references unknown id {hid}")
            elif hid in assigned:
                problems.append(f"id {hid} appears in more than one group")
            assigned.add(hid)
    for h in hunks:
        if h.id not in assigned:
            problems.append(f"id {h.id} ({h.path}) is not in any group")
    return "\n".join(problems) or None


def _validate_incremental(
    new_ids: set[str], n_existing: int, groups: list[dict]
) -> str | None:
    assigned: set[str] = set()
    problems = []
    for gi, g in enumerate(groups, 1):
        ext = g.get("extends")
        if ext is not None and not 1 <= ext <= n_existing:
            problems.append(f"group {gi} extends invalid group number {ext}")
        for hid in g["hunks"]:
            if hid not in new_ids:
                problems.append(f"group {gi} references non-new id {hid}")
            elif hid in assigned:
                problems.append(f"id {hid} appears in more than one group")
            assigned.add(hid)
    for hid in new_ids - assigned:
        problems.append(f"new id {hid} is not in any group")
    return "\n".join(problems) or None


_RETRY = "Your previous grouping was invalid:\n{}\nProduce a corrected, complete grouping."


def analyze_full(
    root: str, hunks: list[Hunk], config: Config, auth: str
) -> list[dict]:
    feedback = None
    for _ in range(2):
        prompt = build_full_prompt(root, hunks, config, feedback)
        groups = _call(root, prompt, config, auth, False, _timeout(config))
        problems = _validate_full(hunks, groups)
        if not problems:
            return groups
        feedback = _RETRY.format(problems)
    raise SystemExit(f"invalid grouping after retry:\n{problems}")


def analyze_incremental(
    root: str,
    existing: list[dict],
    new_hunks: list[Hunk],
    config: Config,
    auth: str,
) -> list[dict]:
    new_ids = {h.id for h in new_hunks}
    feedback = None
    for _ in range(2):
        prompt = build_incremental_prompt(root, existing, new_hunks, config, feedback)
        groups = _call(root, prompt, config, auth, True, _timeout(config))
        problems = _validate_incremental(new_ids, len(existing), groups)
        if not problems:
            merged = copy.deepcopy(existing)
            for g in groups:
                ext = g.pop("extends", None)
                if ext is not None:
                    target = merged[ext - 1]
                    target["hunks"] = list(target["hunks"]) + list(g["hunks"])
                    if g.get("mixed"):
                        target["mixed"] = list(target.get("mixed") or []) + list(g["mixed"])
                else:
                    merged.append(g)
            return merged
        feedback = _RETRY.format(problems)
    raise SystemExit(f"invalid incremental grouping after retry:\n{problems}")
