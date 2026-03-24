"""Collect release notes for nvim and lazy-managed plugins into $LOGS_DIR/release-notes/."""

import argparse
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests

from .constants import LOGS_DIR

LAZY_LOCK = Path.home() / ".config/nvim/lazy-lock.json"
LAZY_PLUGIN_DIR = Path.home() / ".local/share/nvim/lazy"
OUTPUT_DIR = LOGS_DIR / "release-notes"
GITHUB_API = "https://api.github.com"
NVIM_RELEASES_URL = f"{GITHUB_API}/repos/neovim/neovim/releases"


@dataclass
class PluginInfo:
    name: str
    owner: str
    repo: str
    current_commit: str


def _git_remote(plugin_dir: Path) -> str | None:
    try:
        url = subprocess.check_output(
            ["git", "-C", str(plugin_dir), "remote", "get-url", "origin"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return url
    except subprocess.CalledProcessError:
        return None


def _parse_github_url(url: str) -> tuple[str, str] | None:
    """Extract (owner, repo) from a GitHub URL."""
    url = url.removesuffix(".git")
    parts = url.rstrip("/").split("/")
    if len(parts) >= 2 and "github" in url:
        return parts[-2], parts[-1]
    return None


def _collect_plugins(lock: dict[str, dict]) -> list[PluginInfo]:
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
        plugins.append(PluginInfo(name=name, owner=owner, repo=repo, current_commit=info["commit"]))
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


def _format_plugin_notes(plugin: PluginInfo, releases: list[dict]) -> str:
    lines = [f"# {plugin.owner}/{plugin.repo}", f"Current commit: `{plugin.current_commit[:12]}`", ""]
    if not releases:
        lines.append("_No releases found (tag-only or private repo)_\n")
        return "\n".join(lines)
    for r in releases:
        tag = r.get("tag_name", "?")
        date = (r.get("published_at") or "")[:10]
        body = (r.get("body") or "").strip()
        lines.append(f"## {tag}  ({date})")
        lines.append(body if body else "_No release notes_")
        lines.append("")
    return "\n".join(lines)


def _nvim_version() -> str:
    try:
        out = subprocess.check_output(["nvim", "--version"], text=True)
        return out.splitlines()[0]
    except Exception:
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect nvim + plugin release notes")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"), help="GitHub API token")
    parser.add_argument("--limit", type=int, default=5, help="Max releases per plugin (default 5)")
    parser.add_argument("--nvim-only", action="store_true", help="Only fetch nvim release notes")
    args = parser.parse_args()

    if not LAZY_LOCK.exists():
        raise SystemExit(f"lazy-lock.json not found at {LAZY_LOCK}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    out_dir = OUTPUT_DIR / today
    out_dir.mkdir(exist_ok=True)

    headers = _gh_headers(args.token)
    if not args.token:
        print("warning: no GITHUB_TOKEN set — rate limited to 60 req/hr")

    # nvim itself
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


def get_completions(args: list[str]) -> list[str]:
    return ["--token", "--limit", "--nvim-only"]
