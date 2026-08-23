"""Prompt assembly, backend invocation, validation, and incremental merge."""

import copy
import dataclasses

from .. import ai
from ._config import GRANULARITIES, Config
from ._hunks import Hunk
from ._prompt import context_lines

MAX_PROMPT_CHARS = 300000

_TOOLS = ("Read", "Grep", "Glob")

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


def _schema(incremental: bool) -> dict:
    props = dict(_GROUP_PROPS)
    if incremental:
        props["extends"] = {"type": "integer"}
    return {
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
    return parts + ["", *context_lines(root, project=config.context != "bare")]


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


def _need(config: Config) -> ai.Need:
    return ai.Need(
        schema=True,
        tools=_TOOLS if config.context == "explore" else (),
        timeout=1200 if config.context == "explore" else 900,
    )


def backend_for(config: Config, auth: str | None) -> ai.Backend:
    """Resolve before any cache mutation, so a capability mismatch changes nothing."""
    backend = ai.resolve("hunks", _need(config), profile=config.model)
    if auth:
        if not isinstance(backend, ai.Cli):
            raise SystemExit(
                f"--auth applies to cli profiles only, not '{config.model}'"
            )
        backend = dataclasses.replace(backend, auth=auth)
    return backend


def _call(root: str, prompt: str, backend: ai.Backend, incremental: bool) -> list[dict]:
    if len(prompt) > MAX_PROMPT_CHARS:
        raise SystemExit(
            f"diff too large for one analysis: {len(prompt)} chars "
            f"(limit {MAX_PROMPT_CHARS})"
        )
    payload = ai.send(
        backend, "", prompt, schema=_schema(incremental), max_tokens=8192, cwd=root
    )
    groups = payload.get("groups") if isinstance(payload, dict) else None
    if not isinstance(groups, list):
        raise SystemExit("no groups in model output")
    return groups


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


_RETRY = (
    "Your previous grouping was invalid:\n{}\nProduce a corrected, complete grouping."
)


def analyze_full(
    root: str, hunks: list[Hunk], config: Config, backend: ai.Backend
) -> list[dict]:
    feedback = None
    for _ in range(2):
        prompt = build_full_prompt(root, hunks, config, feedback)
        groups = _call(root, prompt, backend, False)
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
    backend: ai.Backend,
) -> list[dict]:
    new_ids = {h.id for h in new_hunks}
    feedback = None
    for _ in range(2):
        prompt = build_incremental_prompt(root, existing, new_hunks, config, feedback)
        groups = _call(root, prompt, backend, True)
        problems = _validate_incremental(new_ids, len(existing), groups)
        if not problems:
            merged = copy.deepcopy(existing)
            for g in groups:
                ext = g.pop("extends", None)
                if ext is not None:
                    target = merged[ext - 1]
                    target["hunks"] = list(target["hunks"]) + list(g["hunks"])
                    if g.get("mixed"):
                        target["mixed"] = list(target.get("mixed") or []) + list(
                            g["mixed"]
                        )
                else:
                    merged.append(g)
            return merged
        feedback = _RETRY.format(problems)
    raise SystemExit(f"invalid incremental grouping after retry:\n{problems}")
