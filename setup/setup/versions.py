import json
import re
import tomllib
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path

_TOML_PATH = Path(__file__).parent.parent / "versions.toml"


@dataclass
class ToolVersion:
    name: str
    tag: str
    source: str
    checked: str
    installed: str = ""


def load() -> dict[str, ToolVersion]:
    data = tomllib.loads(_TOML_PATH.read_text())
    return {name: ToolVersion(name=name, **fields) for name, fields in data.items()}


def dump(versions: dict[str, ToolVersion]) -> None:
    lines = []
    for tv in versions.values():
        lines += [
            f"[{tv.name}]",
            f'tag = "{tv.tag}"',
            f'source = "{tv.source}"',
            f'checked = "{tv.checked}"',
        ]
        if tv.installed:
            lines.append(f'installed = "{tv.installed}"')
        lines.append("")
    _TOML_PATH.write_text("\n".join(lines))


def get(tool: str) -> str:
    return load()[tool].tag


def _fetch_latest_gh(repo: str, token: str | None = None) -> str:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases/latest", headers=headers
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())["tag_name"]
    except Exception:
        req2 = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/tags", headers=headers
        )
        with urllib.request.urlopen(req2) as r:
            return json.loads(r.read())[0]["name"]


def _fetch_latest_lua() -> str:
    with urllib.request.urlopen("http://www.lua.org/ftp/") as r:
        content = r.read().decode()
    versions = re.findall(r"lua-([0-9.]+)\.tar\.gz", content)
    stable = [v for v in versions if len(v.split(".")) <= 3]
    return max(stable, key=lambda v: [int(x) for x in v.split(".")])


def _fetch_latest(tv: ToolVersion, token: str | None = None) -> str:
    if tv.source == "lua.org":
        return _fetch_latest_lua()
    if tv.source.startswith("github:"):
        repo = tv.source.removeprefix("github:")
        latest = _fetch_latest_gh(repo, token)
        if tv.name == "luarocks":
            latest = latest.lstrip("v")
        return latest
    raise ValueError(f"Unknown source: {tv.source!r}")


def check_all(token: str | None = None) -> list[tuple[ToolVersion, str]]:
    return [(tv, _fetch_latest(tv, token)) for tv in load().values()]


def bump(tool: str, tag: str) -> None:
    versions = load()
    if tool not in versions:
        raise SystemExit(f"Unknown tool: {tool!r}")
    versions[tool].tag = tag
    versions[tool].checked = date.today().isoformat()
    dump(versions)
