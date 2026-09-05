"""Prompt files: an optional flat `key: value` frontmatter block above the prompt text.

The block is `---` fenced at the top of the file; values are plain strings (lists are
comma-separated, ` #` starts a comment). The model only ever sees the body.
"""

import re

FENCE = "---"
_COMMENT = re.compile(r"\s#.*$")


def split(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != FENCE:
        return {}, text
    meta: dict[str, str] = {}
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == FENCE:
            return meta, "".join(lines[i + 1 :]).lstrip("\n")
        bare = _COMMENT.sub("", line).strip()
        if not bare:
            continue
        key, sep, value = bare.partition(":")
        if not sep:
            raise ValueError(f"frontmatter line without a colon: {line.rstrip()!r}")
        meta[key.strip()] = value.strip()
    return {}, text


def as_list(value: str) -> tuple[str, ...]:
    return tuple(v.strip() for v in value.split(",") if v.strip())


def as_bool(value: str) -> bool:
    return value.strip().lower() in ("true", "yes", "1")
