"""Minimal TOML value/entry serialization, stdlib-only.

Covers the common case of "serialize a flat dict as `key = value` lines"
without pulling in `tomli_w`. Section headers (`[table]`, `[[array]]`) are the
caller's responsibility — render them and concatenate with `fmt_entry(...)`.

For reading, use stdlib `tomllib`. For anything richer than primitives + flat
lists, reach for `tomli_w` or `tomlkit`.
"""

from __future__ import annotations


def fmt_value(v: object) -> str:
    """Render a Python primitive as a TOML scalar/inline value."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        escaped = v.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(v, list):
        return "[" + ", ".join(fmt_value(i) for i in v) + "]"
    return str(v)


def fmt_entry(d: dict, key_order: list[str] | None = None) -> str:
    """Render a flat dict as TOML `key = value` lines (trailing newline).

    `key_order` lists keys to emit first in the given order; remaining keys
    follow in dict-iteration order.
    """
    order = key_order or []
    seen: set[str] = set()
    lines: list[str] = []
    for k in order:
        if k in d:
            lines.append(f"{k} = {fmt_value(d[k])}")
            seen.add(k)
    for k, v in d.items():
        if k not in seen:
            lines.append(f"{k} = {fmt_value(v)}")
    return "\n".join(lines) + "\n"
