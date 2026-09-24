"""Shared helpers used by multiple nvim subcommands."""

import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

LAZY_LOCK = Path.home() / ".config/nvim/lazy-lock.json"
LAZY_PLUGIN_DIR = Path.home() / ".local/share/nvim/lazy"
GITHUB_API = "https://api.github.com"

# Lua scripts read their arguments with `vim.json.decode(vim.env.NVIM_HEADLESS_ARGS)`
ARGS_ENV = "NVIM_HEADLESS_ARGS"


@dataclass
class Headless:
    data: dict | None
    timed_out: bool = False
    output: str = ""
    wall_ms: int = 0


def nvim_version() -> str:
    try:
        out = subprocess.check_output(["nvim", "--version"], text=True)
        return out.splitlines()[0].removeprefix("NVIM ")
    except Exception:
        return "unknown"


def run_headless(
    lua: str,
    args: dict,
    prefix: str,
    timeout: float,
    env: dict[str, str] | None = None,
) -> Headless:
    """Run `lua` in a headless nvim; `data` is the JSON the script prints after `prefix`."""
    with tempfile.NamedTemporaryFile(suffix=".lua", mode="w", delete=False) as tmp:
        tmp.write(lua)
        lua_path = tmp.name
    full_env = {**os.environ, **(env or {}), ARGS_ENV: json.dumps(args)}
    start = time.monotonic()
    try:
        res = subprocess.run(
            ["nvim", "--headless", "-c", f"luafile {lua_path}"],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=full_env,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        output = (e.stdout or b"").decode(errors="replace")
        return Headless(None, True, output, _ms(start))
    finally:
        Path(lua_path).unlink(missing_ok=True)
    output = res.stdout + res.stderr
    for line in output.splitlines():
        if line.startswith(prefix):
            return Headless(json.loads(line.removeprefix(prefix)), wall_ms=_ms(start))
    return Headless(None, output=output, wall_ms=_ms(start))


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
