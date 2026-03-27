"""nvim tooling: verify LSP health, commit config, fetch release notes."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import requests

from .constants import COMPOSITES_DIR, LOGS_DIR

# === shared ===

LAZY_LOCK = Path.home() / ".config/nvim/lazy-lock.json"
LAZY_PLUGIN_DIR = Path.home() / ".local/share/nvim/lazy"
GITHUB_API = "https://api.github.com"


def _nvim_version() -> str:
    try:
        out = subprocess.check_output(["nvim", "--version"], text=True)
        return out.splitlines()[0].removeprefix("NVIM ")
    except Exception:
        return "unknown"


# === verify ===

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


def _verify_main(args: argparse.Namespace) -> None:
    cfg = _load_verify_config()
    if args.rust:
        cfg.rust = args.rust
    if args.svelte:
        cfg.svelte = args.svelte
    if args.python:
        cfg.python = args.python

    if args.show_config:
        print(json.dumps(asdict(cfg), indent=2))
        return

    if args.save:
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
        ok = _print_verify_result(label, result, args.perf)
        if not ok:
            all_ok = False
        ran += 1

        if args.perf and len(test_files) >= 2:
            has_git = (Path(project_path) / ".git").is_dir()
            print(
                f"  [{label}] perf test ({test_files[0].name} → {test_files[1].name})..."
            )
            perf = _run_headless_perf(test_files[0], test_files[1], has_git)
            if not _print_perf_result(label, perf):
                all_ok = False

    print("=" * 50)
    if ran == 0:
        print(
            "No projects configured. Run with --rust/--svelte/--python <path> --save to set up."
        )
        sys.exit(1)

    print("PASS" if all_ok else "FAIL")
    sys.exit(0 if all_ok else 1)


# === smoke ===

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


def _smoke_main(args: argparse.Namespace) -> None:
    if args.files:
        files = [Path(f) for f in args.files]
    else:
        # create temp files of common types to exercise completion autocmds
        import tempfile as _tf

        tmp_files = []
        for suffix in (".md", ".py"):
            f = _tf.NamedTemporaryFile(suffix=suffix, mode="w", delete=False)
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


# === commit ===

# TODO: not DRY enough
_DOTFILES_ROOT = COMPOSITES_DIR / "pkm" / "diencephalon"
_DOTFILES_NVIM = _DOTFILES_ROOT / "dotfiles" / ".config" / "nvim"


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def _changed_nvim_files(cwd: Path) -> list[str]:
    out = _git(["status", "--porcelain", "--", "dotfiles/.config/nvim/"], cwd=cwd)
    return [line[3:] for line in out.splitlines() if line.strip()]


def _format_plugin_versions(lock: dict[str, dict], top_n: int = 20) -> str:
    items = sorted(lock.items())[:top_n]
    lines = [
        f"  {name:<40} {info['commit'][:10]}  ({info.get('branch', '')})"
        for name, info in items
    ]
    if len(lock) > top_n:
        lines.append(f"  ... and {len(lock) - top_n} more (see lazy-lock.json)")
    return "\n".join(lines)


def _commit_main(args: argparse.Namespace) -> None:
    if not LAZY_LOCK.exists():
        raise SystemExit(f"lazy-lock.json not found at {LAZY_LOCK}")
    if not _DOTFILES_ROOT.exists():
        raise SystemExit(f"Dotfiles root not found: {_DOTFILES_ROOT}")

    lock = json.loads(LAZY_LOCK.read_text())
    prefix = (args.message + "\n\n") if args.message else ""
    commit_msg = (
        f"{prefix}nvim config update\n\n"
        f"nvim: {_nvim_version()}\n"
        f"plugins ({len(lock)} total):\n"
        f"{_format_plugin_versions(lock)}\n"
    )

    if args.dry_run:
        print("=== Commit message preview ===")
        print(commit_msg)
        return

    changed = _changed_nvim_files(_DOTFILES_ROOT)
    if not changed:
        raise SystemExit("No changes to nvim config found in dotfiles.")

    if args.all:
        _git(["add", "--", "dotfiles/.config/nvim/"], cwd=_DOTFILES_ROOT)
        print("Staged all changes under dotfiles/.config/nvim/")
    else:
        _git(["add", "--", "dotfiles/.config/nvim/init.lua"], cwd=_DOTFILES_ROOT)
        print("Staged dotfiles/.config/nvim/init.lua")

    lock_in_dotfiles = _DOTFILES_NVIM / "lazy-lock.json"
    if lock_in_dotfiles.exists():
        _git(["add", "--", "dotfiles/.config/nvim/lazy-lock.json"], cwd=_DOTFILES_ROOT)

    result = subprocess.run(
        ["git", "commit", "-m", commit_msg],
        cwd=_DOTFILES_ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"git commit failed:\n{result.stderr}")

    print(f"Committed: {_git(['log', '--oneline', '-1'], cwd=_DOTFILES_ROOT)}")


# === release_notes ===

_RN_OUTPUT_DIR = LOGS_DIR / "release-notes"


@dataclass
class _PluginInfo:
    name: str
    owner: str
    repo: str
    current_commit: str


def _git_remote(plugin_dir: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(plugin_dir), "remote", "get-url", "origin"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except subprocess.CalledProcessError:
        return None


def _parse_github_url(url: str) -> tuple[str, str] | None:
    url = url.removesuffix(".git")
    parts = url.rstrip("/").split("/")
    if len(parts) >= 2 and "github" in url:
        return parts[-2], parts[-1]
    return None


def _collect_plugins(lock: dict[str, dict]) -> list[_PluginInfo]:
    plugins = []
    for name, info in lock.items():
        plugin_dir = LAZY_PLUGIN_DIR / name
        if not plugin_dir.exists():
            continue
        remote = _git_remote(plugin_dir)
        if not remote:
            continue
        parsed = _parse_github_url(remote)
        if not parsed:
            continue
        owner, repo = parsed
        plugins.append(
            _PluginInfo(
                name=name, owner=owner, repo=repo, current_commit=info["commit"]
            )
        )
    return plugins


def _gh_headers(token: str | None) -> dict:
    h = {"Accept": "application/vnd.github.v3+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _fetch_releases(owner: str, repo: str, headers: dict, limit: int = 5) -> list[dict]:
    try:
        resp = requests.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/releases",
            headers=headers,
            params={"per_page": limit},
            timeout=10,
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"  warning: failed to fetch {owner}/{repo}: {e}")
        return []


def _format_plugin_notes(plugin: _PluginInfo, releases: list[dict]) -> str:
    lines = [
        f"# {plugin.owner}/{plugin.repo}",
        f"Current commit: `{plugin.current_commit[:12]}`",
        "",
    ]
    if not releases:
        lines.append("_No releases found (tag-only or private repo)_\n")
        return "\n".join(lines)
    for r in releases:
        tag = r.get("tag_name", "?")
        date = (r.get("published_at") or "")[:10]
        body = (r.get("body") or "").strip()
        lines += [f"## {tag}  ({date})", body or "_No release notes_", ""]
    return "\n".join(lines)


def _rn_main(args: argparse.Namespace) -> None:
    if not LAZY_LOCK.exists():
        raise SystemExit(f"lazy-lock.json not found at {LAZY_LOCK}")

    _RN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    out_dir = _RN_OUTPUT_DIR / today
    out_dir.mkdir(exist_ok=True)

    headers = _gh_headers(args.token)
    if not args.token:
        print("warning: no GITHUB_TOKEN set — rate limited to 60 req/hr")

    print("Fetching neovim releases...")
    nvim_releases = _fetch_releases("neovim", "neovim", headers, args.limit)
    nvim_notes = [f"# neovim/neovim", f"Installed: {_nvim_version()}", ""]
    for r in nvim_releases:
        tag = r.get("tag_name", "?")
        date = (r.get("published_at") or "")[:10]
        body = (r.get("body") or "").strip()
        nvim_notes += [f"## {tag}  ({date})", body or "_No release notes_", ""]
    (out_dir / "neovim.md").write_text("\n".join(nvim_notes))

    if args.nvim_only:
        print(f"Saved to {out_dir}/neovim.md")
        return

    lock = json.loads(LAZY_LOCK.read_text())
    plugins = _collect_plugins(lock)
    print(f"Found {len(plugins)} plugins with GitHub remotes")

    index_lines = [f"# Release Notes — {today}", f"nvim: {_nvim_version()}", ""]
    for plugin in sorted(plugins, key=lambda p: p.name):
        print(f"  {plugin.owner}/{plugin.repo}...")
        releases = _fetch_releases(plugin.owner, plugin.repo, headers, args.limit)
        notes = _format_plugin_notes(plugin, releases)
        fname = f"{plugin.name}.md"
        (out_dir / fname).write_text(notes)
        latest = releases[0]["tag_name"] if releases else "no releases"
        index_lines.append(f"- [{plugin.name}](./{fname}) — {latest}")

    (out_dir / "README.md").write_text("\n".join(index_lines))
    print(f"\nDone. Notes saved to {out_dir}/")


# === entry point ===


def main() -> None:
    parser = argparse.ArgumentParser(description="nvim tooling")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_verify = sub.add_parser(
        "verify", help="Headless LSP verification against test projects"
    )
    p_verify.add_argument("--rust", default=None, help="Path to a Rust project")
    p_verify.add_argument("--svelte", default=None, help="Path to a Svelte project")
    p_verify.add_argument("--python", default=None, help="Path to a Python project")
    p_verify.add_argument(
        "--save", action="store_true", help="Save provided paths as defaults"
    )
    p_verify.add_argument(
        "--show-config", action="store_true", help="Print current config and exit"
    )
    p_verify.add_argument(
        "--perf", action="store_true", help="Enforce performance thresholds"
    )

    p_commit = sub.add_parser(
        "commit", help="Commit nvim config with plugin version snapshot"
    )
    p_commit.add_argument(
        "--message", "-m", default="", help="Extra commit message prefix"
    )
    p_commit.add_argument(
        "--dry-run", action="store_true", help="Print commit message without committing"
    )
    p_commit.add_argument(
        "--all",
        action="store_true",
        help="Stage all nvim changes (default: only init.lua)",
    )

    p_rn = sub.add_parser(
        "release_notes", help="Fetch release notes for nvim and all lazy plugins"
    )
    p_rn.add_argument(
        "--token", default=os.environ.get("GITHUB_TOKEN"), help="GitHub API token"
    )
    p_rn.add_argument(
        "--limit", type=int, default=5, help="Max releases per plugin (default 5)"
    )
    p_rn.add_argument(
        "--nvim-only", action="store_true", help="Only fetch nvim release notes"
    )

    p_smoke = sub.add_parser(
        "smoke", help="Smoke-test runtime autocmd/completion behavior (non-LSP)"
    )
    p_smoke.add_argument(
        "files", nargs="*", help="Files to test (default: temp .md and .py files)"
    )

    args = parser.parse_args()
    if args.cmd == "verify":
        _verify_main(args)
    elif args.cmd == "commit":
        _commit_main(args)
    elif args.cmd == "release_notes":
        _rn_main(args)
    elif args.cmd == "smoke":
        _smoke_main(args)


def get_completions(args: list[str]) -> list[str]:
    subcmds = ["verify", "commit", "release_notes", "smoke"]
    if not args or args[0] not in subcmds:
        return subcmds
    subcmd, rest = args[0], args[1:]
    if subcmd == "verify":
        opts = ["--rust", "--svelte", "--python", "--save", "--show-config", "--perf"]
        return [] if rest and rest[-1] in ("--rust", "--svelte", "--python") else opts
    if subcmd == "commit":
        return ["--message", "--dry-run", "--all"]
    if subcmd == "release_notes":
        return ["--token", "--limit", "--nvim-only"]
    return []
