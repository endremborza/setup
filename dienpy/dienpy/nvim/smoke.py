"""Smoke-test runtime autocmd/completion behavior (non-LSP)."""

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

_LUA_SMOKE = r"""
local files = vim.g.smoke_files and vim.json.decode(vim.g.smoke_files) or {}
local results = {}
local idx = 0

local function next_file()
  idx = idx + 1
  if idx > #files then
    io.write("SMOKE:" .. vim.json.encode(results) .. "\n")
    io.flush()
    vim.cmd("qa!")
    return
  end

  local path = files[idx]
  vim.cmd("edit " .. path)
  vim.defer_fn(function()
    vim.api.nvim_buf_set_lines(0, 0, 0, false, { "/" })
    vim.v.errmsg = ""
    vim.api.nvim_exec_autocmds("TextChangedI", { buffer = 0 })
    vim.defer_fn(function()
      results[path] = vim.v.errmsg ~= "" and vim.v.errmsg or nil
      next_file()
    end, 300)
  end, 300)
end

next_file()
"""


@dataclass
class _SmokeResult:
    errors: dict[str, str] = field(default_factory=dict)
    raw_output: str = ""


def _run_headless_smoke(files: list[Path]) -> _SmokeResult:
    with tempfile.NamedTemporaryFile(suffix=".lua", mode="w", delete=False) as tmp:
        tmp.write(_LUA_SMOKE)
        lua_path = tmp.name

    files_json = json.dumps([str(f) for f in files])
    try:
        result = subprocess.run(
            [
                "nvim",
                "--headless",
                "--cmd",
                f"let g:smoke_files = '{files_json}'",
                "-c",
                f"luafile {lua_path}",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        output = result.stdout + result.stderr
        for line in output.splitlines():
            if line.startswith("SMOKE:"):
                data = json.loads(line.removeprefix("SMOKE:"))
                errors = (
                    {k: v for k, v in data.items() if v}
                    if isinstance(data, dict)
                    else {}
                )
                return _SmokeResult(errors=errors)
        return _SmokeResult(raw_output=output[:500])
    except subprocess.TimeoutExpired:
        return _SmokeResult(raw_output="TIMEOUT")
    finally:
        Path(lua_path).unlink(missing_ok=True)


def main(*paths: str) -> None:
    """Smoke-test runtime autocmd/completion behavior (default: temp .md and .py files)."""
    if paths:
        files = [Path(p) for p in paths]
    else:
        tmp_files = []
        for suffix in (".md", ".py"):
            f = tempfile.NamedTemporaryFile(suffix=suffix, mode="w", delete=False)
            f.write("")
            f.close()
            tmp_files.append(Path(f.name))
        files = tmp_files

    print(f"smoke testing {len(files)} file(s)...")
    result = _run_headless_smoke(files)

    if result.raw_output:
        print(f"FAIL (no SMOKE output)\n{result.raw_output}")
        sys.exit(1)

    if result.errors:
        for path, err in result.errors.items():
            print(f"  FAIL {path}: {err}")
        sys.exit(1)

    print("PASS")
