"""Minimal TOML value serialization, stdlib-only.

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
