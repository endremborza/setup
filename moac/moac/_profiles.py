"""Profile store: ~/.config/moac/moac.toml layered over built-in defaults.

BUILTIN is the one model table: the tier ids every shell shortcut, launcher and
tool resolves through. A new model version is a one-line change here.
"""

import functools
from pathlib import Path
from typing import Annotated, Any

from dienraw import toml
from protocli import Complete

PATH = Path.home() / ".config" / "moac" / "moac.toml"

LOCAL_URL = "http://localhost:8081/v1/chat/completions"

HAIKU = "claude-haiku-5-5"
SONNET = "claude-sonnet-5-5"
OPUS = "claude-opus-5-5"
FABLE = "claude-fable-5-2"


def _cli(model: str, effort: str = "") -> dict[str, Any]:
    spec: dict[str, Any] = {"kind": "cli", "model": model}
    if effort:
        spec["effort"] = effort
    return spec


BUILTIN: dict[str, dict[str, Any]] = {
    "haiku": _cli(HAIKU),
    "sonnet": _cli(SONNET),
    "opus": _cli(OPUS),
    "fable": _cli(FABLE),
    "soh": _cli(SONNET, "high"),
    "som": _cli(SONNET, "medium"),
    "opuh": _cli(OPUS, "high"),
    "opux": _cli(OPUS, "xhigh"),
    "opum": _cli(OPUS, "max"),
    "fabx": _cli(FABLE, "xhigh"),
    "local": {"kind": "openai", "url": LOCAL_URL},
}
_DEFAULT = "sonnet"


@functools.cache
def _load(path: Path, stamp: int) -> dict[str, Any]:
    return toml.load(path)


def config() -> dict[str, Any]:
    """The toml, parsed once per (path, mtime): an edit is seen, a long loop pays no re-parse."""
    try:
        stamp = PATH.stat().st_mtime_ns
    except FileNotFoundError:
        return {}
    return _load(PATH, stamp)


def profiles() -> dict[str, dict[str, Any]]:
    return {**BUILTIN, **config().get("profile", {})}


def names() -> list[str]:
    return sorted(profiles())


ProfileName = Annotated[str, Complete(names)]


def default_name() -> str:
    return config().get("default", _DEFAULT)


def bindings() -> dict[str, str]:
    return config().get("tool", {})


def for_tool(tool: str) -> str:
    return bindings().get(tool, default_name())


def get(name: str) -> dict[str, Any]:
    spec = profiles().get(name)
    if spec is None:
        raise SystemExit(f"unknown profile '{name}' (known: {', '.join(names())})")
    return spec
