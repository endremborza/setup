"""Headless LSP verification against test projects."""

import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

_VERIFY_CONFIG_FILE = Path.home() / ".config" / "nvim-verify.json"

_LUA_VERIFY = r"""
local target = vim.g.verify_target_file
local timeout_ms = 12000
local check_interval = 400

local wall_start = vim.loop.now()

vim.cmd("edit " .. target)

local function elapsed() return vim.loop.now() - wall_start end

local function report_and_exit(ok, msg)
  io.write(msg .. "\n")
  io.flush()
  vim.cmd("qa!")
end

local function check_lsp()
  if elapsed() > timeout_ms then
    report_and_exit(false, "TIMEOUT: LSP did not attach after " .. timeout_ms .. "ms")
    return
  end

  local clients = vim.lsp.get_clients({ bufnr = 0 })
  if #clients == 0 then
    vim.defer_fn(check_lsp, check_interval)
    return
  end

  local attach_ms = elapsed()
  local names = vim.tbl_map(function(c) return c.name end, clients)

  vim.defer_fn(function()
    local errors = vim.diagnostic.get(0, { severity = vim.diagnostic.severity.ERROR })
    local warns  = vim.diagnostic.get(0, { severity = vim.diagnostic.severity.WARN })
    local total_ms = elapsed()
    local result = {
      file       = target,
      clients    = names,
      errors     = #errors,
      warns      = #warns,
      attach_ms  = attach_ms,
      total_ms   = total_ms,
    }
    for _, d in ipairs(errors) do
      result["error_" .. _] = string.format("L%d: %s", d.lnum + 1, d.message)
    end
    report_and_exit(#errors == 0, "RESULT:" .. vim.json.encode(result))
  end, 3000)
end

vim.defer_fn(check_lsp, 800)
"""

_LUA_PERF = r"""
local file1 = vim.g.perf_file1
local file2 = vim.g.perf_file2
local has_fugitive = vim.g.perf_has_fugitive == 1

local function ms() return vim.loop.now() end
local results = {}

local function finish()
  io.write("PERF:" .. vim.json.encode(results) .. "\n")
  io.flush()
  vim.cmd("qa!")
end

local step2, step3, step4

local function step1()
  local t = ms()
  vim.cmd("edit " .. file1)
  results.file1_edit = ms() - t

  local function wait(attempt)
    if attempt > 40 then results.file1_lsp = -1; step2(); return end
    if #vim.lsp.get_clients({ bufnr = 0 }) > 0 then
      results.file1_lsp = ms() - t
      vim.defer_fn(step2, 3000)
    else
      vim.defer_fn(function() wait(attempt + 1) end, 300)
    end
  end
  vim.defer_fn(function() wait(1) end, 200)
end

step2 = function()
  local t = ms()
  vim.cmd("edit " .. file2)
  results.file2_edit = ms() - t

  local function wait(attempt)
    if attempt > 20 then results.file2_lsp = -1; step3(); return end
    if #vim.lsp.get_clients({ bufnr = 0 }) > 0 then
      results.file2_lsp = ms() - t
      step3()
    else
      vim.defer_fn(function() wait(attempt + 1) end, 100)
    end
  end
  vim.defer_fn(function() wait(1) end, 50)
end

step3 = function()
  if not has_fugitive then
    results.diff1 = -1
    results.diff2 = -1
    results.diff_fugitive_lsp = -1
    finish()
    return
  end
  require("lazy").load({ plugins = { "vim-fugitive" } })
  vim.cmd("edit " .. file1)
  vim.defer_fn(function()
    local t = ms()
    pcall(vim.cmd, "Gvdiffsplit HEAD")
    results.diff1 = ms() - t

    local fug_lsp = 0
    for _, b in ipairs(vim.api.nvim_list_bufs()) do
      local name = vim.api.nvim_buf_get_name(b)
      if name:match("^fugitive://") then
        fug_lsp = fug_lsp + #vim.lsp.get_clients({ bufnr = b })
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
class _ProjectConfig:
    rust: str = ""
    svelte: str = ""
    python: str = ""


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


def _load_verify_config() -> _ProjectConfig:
    if _VERIFY_CONFIG_FILE.exists():
        data = json.loads(_VERIFY_CONFIG_FILE.read_text())
        return _ProjectConfig(
            **{
                k: v
                for k, v in data.items()
                if k in _ProjectConfig.__dataclass_fields__
            }
        )
    return _ProjectConfig()


def _save_verify_config(cfg: _ProjectConfig) -> None:
    _VERIFY_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _VERIFY_CONFIG_FILE.write_text(json.dumps(asdict(cfg), indent=2))


def _find_venv(project_path: str) -> Path | None:
    venv = Path(project_path).expanduser() / ".venv"
    return venv if venv.is_dir() else None


def _pick_test_files(project_path: str, ext: str, count: int = 2) -> list[Path]:
    root = Path(project_path).expanduser()
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


def _run_headless_verify(
    target_file: Path, env_extra: dict[str, str] | None = None
) -> _VerifyResult:
    with tempfile.NamedTemporaryFile(suffix=".lua", mode="w", delete=False) as tmp:
        tmp.write(_LUA_VERIFY)
        lua_path = tmp.name

    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)

    wall_start = time.monotonic()
    try:
        result = subprocess.run(
            [
                "nvim",
                "--headless",
                "--cmd",
                f"let g:verify_target_file = '{target_file}'",
                "-c",
                f"luafile {lua_path}",
            ],
            capture_output=True,
            text=True,
            timeout=25,
            env=env,
        )
        wall_ms = int((time.monotonic() - wall_start) * 1000)
        output = result.stdout + result.stderr
        for line in output.splitlines():
            if line.startswith("RESULT:"):
                data = json.loads(line.removeprefix("RESULT:"))
                return _VerifyResult(
                    file=str(target_file),
                    clients=data.get("clients", []),
                    errors=data.get("errors", 0),
                    warns=data.get("warns", 0),
                    attach_ms=data.get("attach_ms", 0),
                    total_ms=data.get("total_ms", 0),
                    wall_ms=wall_ms,
                    raw=data,
                )
            if line.startswith("TIMEOUT:"):
                return _VerifyResult(
                    file=str(target_file), timed_out=True, wall_ms=wall_ms
                )
        return _VerifyResult(
            file=str(target_file),
            errors=1,
            wall_ms=wall_ms,
            raw={"stderr": result.stderr[:500]},
        )
    except subprocess.TimeoutExpired:
        wall_ms = int((time.monotonic() - wall_start) * 1000)
        return _VerifyResult(file=str(target_file), timed_out=True, wall_ms=wall_ms)
    finally:
        Path(lua_path).unlink(missing_ok=True)


def _run_headless_perf(file1: Path, file2: Path, has_git: bool) -> _PerfResult:
    with tempfile.NamedTemporaryFile(suffix=".lua", mode="w", delete=False) as tmp:
        tmp.write(_LUA_PERF)
        lua_path = tmp.name

    wall_start = time.monotonic()
    try:
        result = subprocess.run(
            [
                "nvim",
                "--headless",
                "--cmd",
                f"let g:perf_file1 = '{file1}' | let g:perf_file2 = '{file2}' | let g:perf_has_fugitive = {'1' if has_git else '0'}",
                "-c",
                f"luafile {lua_path}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        wall_ms = int((time.monotonic() - wall_start) * 1000)
        output = result.stdout + result.stderr
        for line in output.splitlines():
            if line.startswith("PERF:"):
                data = json.loads(line.removeprefix("PERF:"))
                return _PerfResult(
                    file1_edit=data.get("file1_edit", 0),
                    file1_lsp=data.get("file1_lsp", 0),
                    file2_edit=data.get("file2_edit", 0),
                    file2_lsp=data.get("file2_lsp", 0),
                    diff1=data.get("diff1", 0),
                    diff2=data.get("diff2", 0),
                    diff_fugitive_lsp=data.get("diff_fugitive_lsp", 0),
                    wall_ms=wall_ms,
                )
        return _PerfResult(wall_ms=wall_ms)
    except subprocess.TimeoutExpired:
        wall_ms = int((time.monotonic() - wall_start) * 1000)
        return _PerfResult(wall_ms=wall_ms)
    finally:
        Path(lua_path).unlink(missing_ok=True)


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


def _print_perf_result(label: str, perf: _PerfResult) -> bool:
    ok = True
    print(f"  [{label}] performance")
    print(f"    file1 edit:   {perf.file1_edit}ms  lsp attach: {perf.file1_lsp}ms")
    print(f"    file2 edit:   {perf.file2_edit}ms  lsp attach: {perf.file2_lsp}ms")
    if perf.diff1 >= 0:
        print(f"    diff open:    {perf.diff1}ms  (repeat: {perf.diff2}ms)")
        print(f"    fugitive lsp: {perf.diff_fugitive_lsp} clients (want 0)")
        if perf.diff_fugitive_lsp > 0:
            print(f"    ⚠ LSP attached to fugitive buffer!")
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
    if rust:
        cfg.rust = rust
    if svelte:
        cfg.svelte = svelte
    if python:
        cfg.python = python

    if show_config:
        print(json.dumps(asdict(cfg), indent=2))
        return

    if save:
        _save_verify_config(cfg)
        print(f"Saved config to {_VERIFY_CONFIG_FILE}")

    targets: list[tuple[str, str, str]] = [
        ("rust", cfg.rust, "rs"),
        ("svelte", cfg.svelte, "svelte"),
        ("python", cfg.python, "py"),
    ]

    all_ok = True
    ran = 0
    print("nvim LSP verification")
    print("=" * 50)

    for label, project_path, ext in targets:
        if not project_path:
            print(f"  [{label}] SKIP (no project configured — use --{label} <path>)")
            continue

        test_files = _pick_test_files(project_path, ext, count=2)
        if not test_files:
            print(f"  [{label}] SKIP (no .{ext} file found under {project_path})")
            continue

        env_extra: dict[str, str] = {}
        venv = _find_venv(project_path)
        if venv:
            env_extra["VIRTUAL_ENV"] = str(venv)
            env_extra["PATH"] = str(venv / "bin") + ":" + os.environ.get("PATH", "")

        print(f"  [{label}] testing {test_files[0]}...")
        result = _run_headless_verify(test_files[0], env_extra or None)
        ok = _print_verify_result(label, result, perf)
        if not ok:
            all_ok = False
        ran += 1

        if perf and len(test_files) >= 2:
            has_git = (Path(project_path) / ".git").is_dir()
            print(
                f"  [{label}] perf test ({test_files[0].name} → {test_files[1].name})..."
            )
            perf_result = _run_headless_perf(test_files[0], test_files[1], has_git)
            if not _print_perf_result(label, perf_result):
                all_ok = False

    print("=" * 50)
    if ran == 0:
        print(
            "No projects configured. Run with --rust/--svelte/--python <path> --save to set up."
        )
        sys.exit(1)

    print("PASS" if all_ok else "FAIL")
    sys.exit(0 if all_ok else 1)
