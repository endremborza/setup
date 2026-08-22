"""Profile store: ~/.config/dienpy/ai.toml layered over built-in defaults."""

from pathlib import Path
from typing import Annotated, Any

import tomllib
from protocli import Complete

PATH = Path.home() / ".config" / "dienpy" / "ai.toml"

LOCAL_URL = "http://localhost:8081/v1/chat/completions"

BUILTIN: dict[str, dict[str, Any]] = {
    "haiku": {"kind": "cli", "model": "haiku"},
    "sonnet": {"kind": "cli", "model": "sonnet"},
    "opus": {"kind": "cli", "model": "opus"},
    "fable": {"kind": "cli", "model": "fable"},
    "local": {"kind": "openai", "url": LOCAL_URL},
}
_DEFAULT = "sonnet"


def _read() -> dict[str, Any]:
    if not PATH.exists():
        return {}
    try:
        return tomllib.loads(PATH.read_text())
    except tomllib.TOMLDecodeError as e:
        raise SystemExit(f"{PATH}: {e}")


def profiles() -> dict[str, dict[str, Any]]:
    return {**BUILTIN, **_read().get("profile", {})}


def names() -> list[str]:
    return sorted(profiles())


ProfileName = Annotated[str, Complete(names)]


def default_name() -> str:
    return _read().get("default", _DEFAULT)


def bindings() -> dict[str, str]:
    return _read().get("tool", {})


def for_tool(tool: str) -> str:
    return bindings().get(tool, default_name())


def get(name: str) -> dict[str, Any]:
    spec = profiles().get(name)
    if spec is None:
        raise SystemExit(f"unknown ai profile '{name}' (known: {', '.join(names())})")
    return spec
