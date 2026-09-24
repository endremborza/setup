"""Smoke-test runtime autocmd/completion behavior (non-LSP)."""

import sys
import tempfile
from pathlib import Path

from ._shared import ARGS_ENV, run_headless

_LUA_SMOKE = rf"""
local files = vim.json.decode(vim.env.{ARGS_ENV}).files
local results = {{}}
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
  vim.cmd.edit(path)
  vim.defer_fn(function()
    vim.api.nvim_buf_set_lines(0, 0, 0, false, {{ "/" }})
    vim.v.errmsg = ""
    vim.api.nvim_exec_autocmds("TextChangedI", {{ buffer = 0 }})
    vim.defer_fn(function()
      results[path] = vim.v.errmsg ~= "" and vim.v.errmsg or nil
      next_file()
    end, 300)
  end, 300)
end

next_file()
"""


def main(*paths: str) -> None:
    """Smoke-test runtime autocmd/completion behavior (default: temp .md and .py files)."""
    if paths:
        files = [Path(p) for p in paths]
    else:
        files = []
        for suffix in (".md", ".py"):
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                files.append(Path(f.name))

    print(f"smoke testing {len(files)} file(s)...")
    h = run_headless(_LUA_SMOKE, {"files": [str(f) for f in files]}, "SMOKE:", 15)
    if h.data is None:
        print(
            "FAIL (no SMOKE output)\n" + ("TIMEOUT" if h.timed_out else h.output[:500])
        )
        sys.exit(1)
    errors = {k: v for k, v in h.data.items() if v} if isinstance(h.data, dict) else {}
    for path, err in errors.items():
        print(f"  FAIL {path}: {err}")
    if errors:
        sys.exit(1)
    print("PASS")
