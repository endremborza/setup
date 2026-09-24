"""Fetch release notes for nvim and all lazy plugins."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime

import requests

from .._git import Repo
from ..constants import LOGS_DIR
from ._shared import GITHUB_API, LAZY_LOCK, LAZY_PLUGIN_DIR, nvim_version

_RN_OUTPUT_DIR = LOGS_DIR / "release-notes"


@dataclass
class _PluginInfo:
    name: str
    owner: str
    repo: str
    current_commit: str


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
        remote = Repo(plugin_dir).maybe("remote", "get-url", "origin")
        parsed = _parse_github_url(remote) if remote else None
        if parsed:
            plugins.append(_PluginInfo(name, *parsed, current_commit=info["commit"]))
    return plugins


def _fetch_releases(
    session: requests.Session, owner: str, repo: str, limit: int
) -> list[dict]:
    try:
        resp = session.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/releases",
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


def _format_releases(releases: list[dict]) -> list[str]:
    lines = []
    for r in releases:
        tag = r.get("tag_name", "?")
        date = (r.get("published_at") or "")[:10]
        body = (r.get("body") or "").strip()
        lines += [f"## {tag}  ({date})", body or "_No release notes_", ""]
    return lines


def _format_plugin_notes(plugin: _PluginInfo, releases: list[dict]) -> str:
    lines = [
        f"# {plugin.owner}/{plugin.repo}",
        f"Current commit: `{plugin.current_commit[:12]}`",
        "",
    ]
    if not releases:
        lines.append("_No releases found (tag-only or private repo)_\n")
    return "\n".join(lines + _format_releases(releases))


def main(*, token: str | None = None, limit: int = 5, nvim_only: bool = False) -> None:
    """Fetch release notes for nvim and all lazy plugins (defaults --token to $GITHUB_TOKEN)."""
    if not LAZY_LOCK.exists():
        raise SystemExit(f"lazy-lock.json not found at {LAZY_LOCK}")

    token = token or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("warning: no GITHUB_TOKEN set — rate limited to 60 req/hr")
    today = datetime.now().strftime("%Y-%m-%d")
    out_dir = _RN_OUTPUT_DIR / today
    out_dir.mkdir(parents=True, exist_ok=True)
    installed = nvim_version()

    session = requests.Session()
    session.headers["Accept"] = "application/vnd.github.v3+json"
    if token:
        session.headers["Authorization"] = f"Bearer {token}"

    print("Fetching neovim releases...")
    nvim_notes = ["# neovim/neovim", f"Installed: {installed}", ""]
    nvim_notes += _format_releases(_fetch_releases(session, "neovim", "neovim", limit))
    (out_dir / "neovim.md").write_text("\n".join(nvim_notes))

    if nvim_only:
        print(f"Saved to {out_dir}/neovim.md")
        return

    plugins = sorted(
        _collect_plugins(json.loads(LAZY_LOCK.read_text())), key=lambda p: p.name
    )
    print(f"Found {len(plugins)} plugins with GitHub remotes")

    with ThreadPoolExecutor(max_workers=8) as pool:
        fetched = pool.map(
            lambda p: _fetch_releases(session, p.owner, p.repo, limit), plugins
        )

    index_lines = [f"# Release Notes — {today}", f"nvim: {installed}", ""]
    for plugin, releases in zip(plugins, fetched):
        fname = f"{plugin.name}.md"
        (out_dir / fname).write_text(_format_plugin_notes(plugin, releases))
        latest = releases[0]["tag_name"] if releases else "no releases"
        index_lines.append(f"- [{plugin.name}](./{fname}) — {latest}")

    (out_dir / "README.md").write_text("\n".join(index_lines))
    print(f"\nDone. Notes saved to {out_dir}/")
