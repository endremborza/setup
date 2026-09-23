"""Prompt assembly, backend invocation, validation, and incremental placement: the partition of a diff into patches."""

import copy
import dataclasses

from .. import ai
from ._config import GRANULARITIES, Config
from ._hunks import Hunk
from ._prompt import context_lines

MAX_PROMPT_CHARS = 300000

_TOOLS = ("Read", "Grep", "Glob")

_PATCH_PROPS = {
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
Partition these git hunks into patches (future commits).

Rules:
- Every hunk id below appears in exactly one patch's "hunks" array; never dropped, never duplicated.
- Partition by semantic concern, not by file: hunks from one file can belong to different patches.
- If a single hunk mixes two distinct concerns, assign it to the dominant one and record it in that patch's "mixed" array with a note naming the foreign part.
- "title": a commit subject line (<= 72 chars) in the style of the recent subjects below.
- "message": the commit body, what changed and why; do not restate the title.
- Order patches so foundational changes come before things built on them."""

_INCR_RULES = """\
These hunks are NEW since a previous partition of this diff. Place each new hunk.

Rules:
- Every new hunk id below appears in exactly one returned patch's "hunks" array; never dropped, never duplicated.
- To add new hunks to an existing patch, return a patch with "extends": <existing patch number> containing only those new hunk ids.
- For new hunks belonging to no existing patch, return a new patch (no "extends") with title/message in the established style.
- Do not restate hunks that are already placed."""


def _schema(incremental: bool) -> dict:
    props = dict(_PATCH_PROPS)
    if incremental:
        props["extends"] = {"type": "integer"}
    return {
        "type": "object",
        "properties": {
            "patches": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": props,
                    "required": ["title", "message", "hunks"],
                },
            }
        },
        "required": ["patches"],
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
            "changes before partitioning.",
        ]
    return parts + ["", *context_lines(root, project=config.context != "bare")]


def _hunk_block(hunks: list[Hunk]) -> list[str]:
    parts = []
    for h in hunks:
        parts += ["", f"[{h.id}] {h.path}", h.display]
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
    parts = _prompt_head(root, config, _INCR_RULES) + ["", "Existing patches:"]
    for i, g in enumerate(groups, 1):
        parts.append(f"{i}. {g['title']}")
        for line in (g.get("message") or "").split("\n"):
            parts.append(f"   {line}")
    parts += ["", "New hunks:"]
    parts += _hunk_block(new_hunks)
    if feedback:
        parts += ["", feedback]
    return "\n".join(parts)


_DESCRIBE_RULES = """\
Rewrite the commit title and message of ONE patch whose hunks changed since it was \
described. The other patches are listed by title for context only.

Rules:
- "title": a commit subject line (<= 72 chars) in the style of the recent subjects below; keep the current title when it still describes the patch.
- "message": the commit body, what changed and why; do not restate the title.
- Describe the patch as it is now, from all of its hunks, not the delta since the old message."""

_DESCRIBE_SCHEMA = {
    "type": "object",
    "properties": {"title": {"type": "string"}, "message": {"type": "string"}},
    "required": ["title", "message"],
}


def build_describe_prompt(
    root: str, groups: list[dict], index: int, hunks: list[Hunk], config: Config
) -> str:
    parts = _prompt_head(root, config, _DESCRIBE_RULES) + ["", "All patches:"]
    for i, g in enumerate(groups):
        parts.append(f"{'>' if i == index else ' '} {i + 1}. {g['title']}")
    g = groups[index]
    parts += ["", "Current message of the marked patch:", g.get("message") or "(none)"]
    parts += ["", "Its hunks:"] + _hunk_block(hunks)
    return "\n".join(parts)


def describe(
    root: str,
    groups: list[dict],
    index: int,
    hunks: list[Hunk],
    config: Config,
    backend: ai.Backend,
) -> dict:
    """Fresh title/message for one patch; the returned dict is a copy with `stale` cleared."""
    prompt = build_describe_prompt(root, groups, index, hunks, config)
    if len(prompt) > MAX_PROMPT_CHARS:
        raise SystemExit(
            f"patch {index + 1} too large to describe: {len(prompt)} chars "
            f"(limit {MAX_PROMPT_CHARS})"
        )
    payload = ai.send(
        backend, "", prompt, schema=_DESCRIBE_SCHEMA, max_tokens=2048, cwd=root
    )
    if not isinstance(payload, dict) or not payload.get("title"):
        raise SystemExit("no title in model output")
    out = {k: v for k, v in groups[index].items() if k != "stale"}
    out["title"] = str(payload["title"]).strip()
    out["message"] = str(payload.get("message") or "").strip()
    return out


def describe_stale(
    root: str,
    patches: list[dict],
    hunks: list[Hunk],
    config: Config,
    backend: ai.Backend,
) -> list[dict]:
    """Fresh title/message for every patch flagged `stale` by a placement."""
    recs = {h.id: h for h in hunks}
    for i, p in enumerate(patches):
        if not p.get("stale"):
            continue
        own = [recs[hid] for hid in p["hunks"] if hid in recs]
        patches[i] = describe(root, patches, i, own, config, backend)
    return patches


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
    patches = payload.get("patches") if isinstance(payload, dict) else None
    if not isinstance(patches, list):
        raise SystemExit("no patches in model output")
    return patches


def _validate_full(hunks: list[Hunk], groups: list[dict]) -> str | None:
    known = {h.id: h for h in hunks}
    assigned: set[str] = set()
    problems = []
    for gi, g in enumerate(groups, 1):
        for hid in g["hunks"]:
            if hid not in known:
                problems.append(f"patch {gi} references unknown id {hid}")
            elif hid in assigned:
                problems.append(f"id {hid} appears in more than one patch")
            assigned.add(hid)
    for h in hunks:
        if h.id not in assigned:
            problems.append(f"id {h.id} ({h.path}) is not in any patch")
    return "\n".join(problems) or None


def _validate_incremental(
    new_ids: set[str], n_existing: int, groups: list[dict]
) -> str | None:
    assigned: set[str] = set()
    problems = []
    for gi, g in enumerate(groups, 1):
        ext = g.get("extends")
        if ext is not None and not 1 <= ext <= n_existing:
            problems.append(f"patch {gi} extends invalid patch number {ext}")
        for hid in g["hunks"]:
            if hid not in new_ids:
                problems.append(f"patch {gi} references non-new id {hid}")
            elif hid in assigned:
                problems.append(f"id {hid} appears in more than one patch")
            assigned.add(hid)
    for hid in new_ids - assigned:
        problems.append(f"new id {hid} is not in any patch")
    return "\n".join(problems) or None


_RETRY = (
    "Your previous partition was invalid:\n{}\nProduce a corrected, complete partition."
)


def partition(
    root: str, hunks: list[Hunk], config: Config, backend: ai.Backend
) -> list[dict]:
    feedback = problems = None
    for _ in range(2):
        prompt = build_full_prompt(root, hunks, config, feedback)
        groups = _call(root, prompt, backend, False)
        problems = _validate_full(hunks, groups)
        if not problems:
            return groups
        feedback = _RETRY.format(problems)
    raise SystemExit(f"invalid partition after retry:\n{problems}")


def place(
    root: str,
    existing: list[dict],
    new_hunks: list[Hunk],
    config: Config,
    backend: ai.Backend,
) -> list[dict]:
    """Validated placements: groups whose `extends` names a position in `existing`."""
    new_ids = {h.id for h in new_hunks}
    feedback = problems = None
    for _ in range(2):
        prompt = build_incremental_prompt(root, existing, new_hunks, config, feedback)
        groups = _call(root, prompt, backend, True)
        problems = _validate_incremental(new_ids, len(existing), groups)
        if not problems:
            return groups
        feedback = _RETRY.format(problems)
    raise SystemExit(f"invalid placement after retry:\n{problems}")


def merge_placement(
    patches: list[dict], groups: list[dict], snapshot: list[dict]
) -> list[dict]:
    """Placements made against `snapshot` applied to `patches`, the entry as it is now:
    an extended patch is found by id, one gone meanwhile takes the placement whole."""
    merged = copy.deepcopy(patches)
    by_id = {p["id"]: p for p in merged}
    for g in groups:
        ext = g.pop("extends", None)
        target = by_id.get(snapshot[ext - 1]["id"]) if ext is not None else None
        if target is None:
            merged.append(g)
            continue
        target["hunks"] = list(target["hunks"]) + list(g["hunks"])
        target["stale"] = True
        if g.get("mixed"):
            target["mixed"] = list(target.get("mixed") or []) + list(g["mixed"])
    return merged
