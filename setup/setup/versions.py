import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import tomllib

_TOML_PATH = Path(__file__).parent.parent / "versions.toml"
_TIMEOUT = 15


# Upstream tag formats disagree with the pins they name: `tectonic@0.17.0`,
# `jq-1.8.2`, `bun-v1.4.2`, `v0.12.5`, `3.7c`. Compare the number, never the
# raw string, or a tool reads as behind forever.
_NUMBER = re.compile(r"\d+\.\d+[\w.\-]*")
_PART = re.compile(r"\d+|[a-zA-Z]+")


def number(tag: str) -> str:
    m = _NUMBER.search(tag)
    return m.group(0) if m else ""


def version_key(tag: str) -> tuple:
    """Numeric order per part (`1.10` after `1.9`); a suffix follows its bare
    version (`3.7c` after `3.7`) and letters sort below digits at the same slot."""
    return tuple(
        (1, int(p)) if p.isdigit() else (0, p.lower())
        for p in _PART.findall(number(tag))
    )


@dataclass
class ToolVersion:
    name: str
    tag: str
    source: str
    checked: str


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
            "",
        ]
    _TOML_PATH.write_text("\n".join(lines))


def get(tool: str) -> str:
    return load()[tool].tag


def _gh_json(path: str, token: str | None):
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"https://api.github.com/{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return json.loads(r.read())


def _fetch_latest_gh(repo: str, token: str | None = None) -> str:
    """Repos without releases only have tags, which GitHub lists unsorted."""
    try:
        return _gh_json(f"repos/{repo}/releases/latest", token)["tag_name"]
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    tags = [t["name"] for t in _gh_json(f"repos/{repo}/tags", token)]
    return max(tags, key=version_key)


def _fetch_latest_lua() -> str:
    with urllib.request.urlopen("https://www.lua.org/ftp/", timeout=_TIMEOUT) as r:
        content = r.read().decode()
    versions = re.findall(r"lua-([0-9.]+)\.tar\.gz", content)
    stable = [v for v in versions if len(v.split(".")) <= 3]
    return max(stable, key=version_key)


def _fetch_latest(tv: ToolVersion, token: str | None = None) -> str:
    if tv.source == "lua.org":
        return _fetch_latest_lua()
    if tv.source.startswith("github:"):
        return _fetch_latest_gh(tv.source.removeprefix("github:"), token)
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
