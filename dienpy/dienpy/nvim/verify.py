"""Headless LSP verification against test projects."""

import json
import os
import sys
from dataclasses import dataclass, field, fields
from pathlib import Path

from ._shared import ARGS_ENV, run_headless

_VERIFY_CONFIG_FILE = Path.home() / ".config" / "nvim-verify.json"
_EXT = {"rust": "rs", "svelte": "svelte", "python": "py"}

_LUA_VERIFY = rf"""
local args = vim.json.decode(vim.env.{ARGS_ENV})
local timeout_ms = 12000
local check_interval = 400
local wall_start = vim.loop.now()

vim.cmd.edit(args.file)

local function elapsed() return vim.loop.now() - wall_start end

local function report(result)
  io.write("RESULT:" .. vim.json.encode(result) .. "\n")
  io.flush()
  vim.cmd("qa!")
end

local function check_lsp()
  if elapsed() > timeout_ms then
    report({{ timed_out = true }})
    return
  end
  local clients = vim.lsp.get_clients({{ bufnr = 0 }})
  if #clients == 0 then
    vim.defer_fn(check_lsp, check_interval)
    return
  end
  local attach_ms = elapsed()
  local names = vim.tbl_map(function(c) return c.name end, clients)
  vim.defer_fn(function()
    local errors = vim.diagnostic.get(0, {{ severity = vim.diagnostic.severity.ERROR }})
    local warns  = vim.diagnostic.get(0, {{ severity = vim.diagnostic.severity.WARN }})
    local result = {{
      clients   = names,
      errors    = #errors,
      warns     = #warns,
      attach_ms = attach_ms,
      total_ms  = elapsed(),
    }}
    for i, d in ipairs(errors) do
      result["error_" .. i] = string.format("L%d: %s", d.lnum + 1, d.message)
    end
    report(result)
  end, 3000)
end

vim.defer_fn(check_lsp, 800)
"""

_LUA_PERF = rf"""
local args = vim.json.decode(vim.env.{ARGS_ENV})
local function ms() return vim.loop.now() end
local results = {{}}

local function finish()
  io.write("PERF:" .. vim.json.encode(results) .. "\n")
  io.flush()
  vim.cmd("qa!")
end

local function wait_lsp(key, t, attempts, interval, on_done)
  local function poll(attempt)
    if attempt > attempts then results[key] = -1; on_done(); return end
    if #vim.lsp.get_clients({{ bufnr = 0 }}) > 0 then
      results[key] = ms() - t
      on_done()
    else
      vim.defer_fn(function() poll(attempt + 1) end, interval)
    end
  end
  vim.defer_fn(function() poll(1) end, interval)
end

local step2, step3

local function step1()
  local t = ms()
  vim.cmd.edit(args.file1)
  results.file1_edit = ms() - t
  wait_lsp("file1_lsp", t, 40, 300, function() vim.defer_fn(step2, 3000) end)
end

step2 = function()
  local t = ms()
  vim.cmd.edit(args.file2)
  results.file2_edit = ms() - t
  wait_lsp("file2_lsp", t, 20, 100, step3)
end

step3 = function()
  if not args.has_git then
    results.diff1 = -1
    results.diff2 = -1
    results.diff_fugitive_lsp = -1
    finish()
    return
  end
  require("lazy").load({{ plugins = {{ "vim-fugitive" }} }})
  vim.cmd.edit(args.file1)
  vim.defer_fn(function()
    local t = ms()
    pcall(vim.cmd, "Gvdiffsplit HEAD")
    results.diff1 = ms() - t

    local fug_lsp = 0
    for _, b in ipairs(vim.api.nvim_list_bufs()) do
      if vim.api.nvim_buf_get_name(b):match("^fugitive://") then
        fug_lsp = fug_lsp + #vim.lsp.get_clients({{ bufnr = b }})
      end
    end
    results.diff_fugitive_lsp = fug_lsp

    vim.cmd("only")
    vim.defer_fn(function()
      local t2 = ms()
      pcall(vim.cmd, "Gvdiffsplit HEAD")
      results.diff2 = ms() - t2
      vim.cmd("only")
      vim.defer_fn(finish, 200)
    end, 500)
  end, 500)
end

vim.defer_fn(step1, 500)
"""


@dataclass
class _VerifyResult:
    file: str
    clients: list[str] = field(default_factory=list)
    errors: int = 0
    warns: int = 0
    raw: dict = field(default_factory=dict)
    timed_out: bool = False
    attach_ms: int = 0
    total_ms: int = 0
    wall_ms: int = 0


@dataclass
class _PerfResult:
    file1_edit: int = 0
    file1_lsp: int = 0
    file2_edit: int = 0
    file2_lsp: int = 0
    diff1: int = 0
    diff2: int = 0
    diff_fugitive_lsp: int = 0
    wall_ms: int = 0


def _known(cls: type, data: dict) -> dict:
    names = {f.name for f in fields(cls)}
    return {k: v for k, v in data.items() if k in names}


def _load_verify_config() -> dict[str, str]:
    if not _VERIFY_CONFIG_FILE.exists():
        return {}
    data = json.loads(_VERIFY_CONFIG_FILE.read_text())
    return {k: v for k, v in data.items() if k in _EXT}


def _pick_test_files(root: Path, ext: str, count: int = 2) -> list[Path]:
    if not root.exists():
        return []
    skip = {".venv", "node_modules", "target", ".svelte-kit", "__pycache__"}
    found: list[Path] = []
    for f in sorted(root.rglob(f"*.{ext}")):
        if not any(part in skip for part in f.parts):
            found.append(f)
            if len(found) >= count:
                break
    return found


def _run_verify(target: Path, env: dict[str, str] | None) -> _VerifyResult:
    h = run_headless(_LUA_VERIFY, {"file": str(target)}, "RESULT:", 25, env)
    if h.timed_out or h.data is None:
        raw = {} if h.timed_out else {"stderr": h.output[:500]}
        return _VerifyResult(
            str(target),
            errors=0 if h.timed_out else 1,
            raw=raw,
            timed_out=h.timed_out,
            wall_ms=h.wall_ms,
        )
    return _VerifyResult(
        str(target), raw=h.data, wall_ms=h.wall_ms, **_known(_VerifyResult, h.data)
    )


def _run_perf(file1: Path, file2: Path, has_git: bool) -> _PerfResult | None:
    args = {"file1": str(file1), "file2": str(file2), "has_git": has_git}
    h = run_headless(_LUA_PERF, args, "PERF:", 30)
    if h.data is None:
        return None
    return _PerfResult(wall_ms=h.wall_ms, **_known(_PerfResult, h.data))


_PERF_THRESHOLDS: dict[str, int] = {"rust": 8000, "svelte": 6000, "python": 6000}
_PERF_FILE2_THRESHOLD = 100
_PERF_DIFF_THRESHOLD = 200


def _print_verify_result(label: str, result: _VerifyResult, perf: bool) -> bool:
    ok = True
    if result.timed_out:
        status, ok = "✗ TIMEOUT", False
    elif result.errors > 0:
        status, ok = f"✗ {result.errors} ERROR(S)", False
    else:
        status = "✓ OK"
    clients_str = ", ".join(result.clients) if result.clients else "none attached"
    print(f"  [{label}] {status}")
    print(f"    file:    {result.file}")
    print(f"    clients: {clients_str}")
    print(
        f"    attach:  {result.attach_ms}ms  total: {result.total_ms}ms  wall: {result.wall_ms}ms"
    )
    if result.warns:
        print(f"    warns:   {result.warns}")
    if result.raw.get("stderr"):
        print(f"    stderr:  {result.raw['stderr'][:200]}")
    for k, v in result.raw.items():
        if k.startswith("error_"):
            print(f"    {v}")
    if perf:
        threshold = _PERF_THRESHOLDS.get(label, 8000)
        if result.wall_ms > threshold:
            print(
                f"    ⚠ SLOW: wall time {result.wall_ms}ms exceeds {threshold}ms threshold"
            )
            ok = False
    return ok


def _print_perf_result(label: str, perf: _PerfResult | None) -> bool:
    print(f"  [{label}] performance")
    if perf is None:
        print("    ✗ no PERF result (timeout or crash)")
        return False
    ok = True
    print(f"    file1 edit:   {perf.file1_edit}ms  lsp attach: {perf.file1_lsp}ms")
    print(f"    file2 edit:   {perf.file2_edit}ms  lsp attach: {perf.file2_lsp}ms")
    if perf.file1_lsp < 0 or perf.file2_lsp < 0:
        print("    ✗ LSP never attached")
        ok = False
    if perf.diff1 >= 0:
        print(f"    diff open:    {perf.diff1}ms  (repeat: {perf.diff2}ms)")
        print(f"    fugitive lsp: {perf.diff_fugitive_lsp} clients (want 0)")
        if perf.diff_fugitive_lsp > 0:
            print("    ⚠ LSP attached to fugitive buffer!")
            ok = False
        if perf.diff1 > _PERF_DIFF_THRESHOLD:
            print(f"    ⚠ diff open {perf.diff1}ms exceeds {_PERF_DIFF_THRESHOLD}ms")
            ok = False
    if perf.file2_edit > _PERF_FILE2_THRESHOLD:
        print(f"    ⚠ file2 edit {perf.file2_edit}ms exceeds {_PERF_FILE2_THRESHOLD}ms")
        ok = False
    return ok


def main(
    *,
    rust: str | None = None,
    svelte: str | None = None,
    python: str | None = None,
    save: bool = False,
    show_config: bool = False,
    perf: bool = False,
) -> None:
    """Headless LSP verification against test projects."""
    cfg = _load_verify_config()
    cfg.update(
        {k: v for k, v in (("rust", rust), ("svelte", svelte), ("python", python)) if v}
    )

    if show_config:
        print(json.dumps(cfg, indent=2))
        return

    if save:
        _VERIFY_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        _VERIFY_CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
        print(f"Saved config to {_VERIFY_CONFIG_FILE}")

    all_ok = True
    ran = 0
    print("nvim LSP verification")
    print("=" * 50)

    for label, ext in _EXT.items():
        if not cfg.get(label):
            print(f"  [{label}] SKIP (no project configured — use --{label} <path>)")
            continue
        root = Path(cfg[label]).expanduser()
        test_files = _pick_test_files(root, ext)
        if not test_files:
            print(f"  [{label}] SKIP (no .{ext} file found under {root})")
            continue

        env: dict[str, str] = {}
        venv = root / ".venv"
        if venv.is_dir():
            env["VIRTUAL_ENV"] = str(venv)
            env["PATH"] = str(venv / "bin") + ":" + os.environ.get("PATH", "")

        print(f"  [{label}] testing {test_files[0]}...")
        all_ok &= _print_verify_result(
            label, _run_verify(test_files[0], env or None), perf
        )
        ran += 1

        if perf and len(test_files) >= 2:
            has_git = (root / ".git").is_dir()
            print(
                f"  [{label}] perf test ({test_files[0].name} → {test_files[1].name})..."
            )
            all_ok &= _print_perf_result(
                label, _run_perf(test_files[0], test_files[1], has_git)
            )

    print("=" * 50)
    if ran == 0:
        print(
            "No projects configured. Run with --rust/--svelte/--python <path> --save to set up."
        )
        sys.exit(1)

    print("PASS" if all_ok else "FAIL")
    sys.exit(0 if all_ok else 1)
