"""Machine-written config files: TOML values out, TOML in with a loud error, atomic writes.

For anything richer than primitives + flat lists, reach for `tomli_w` or `tomlkit`.
"""

from __future__ import annotations

import os
from pathlib import Path

import tomllib


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


def load(path: Path) -> dict:
    """The file's tables; a missing file is an empty config, a broken one a user error."""
    if not path.exists():
        return {}
    try:
        return tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as e:
        raise SystemExit(f"{path}: {e}")


def write_atomic(path: Path, text: str) -> None:
    """Replace `path` in one step, keeping its mode; a reader never sees a partial file."""
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    tmp = path.with_name(f".{path.name}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.replace(tmp, path)
