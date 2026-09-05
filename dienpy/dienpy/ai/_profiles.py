"""Profile store: ~/.config/dienpy/ai.toml layered over built-in defaults.

BUILTIN is the one model table: the tier ids every shell shortcut, launcher and
tool resolves through. A new model version is a one-line change here.
"""

from pathlib import Path
from typing import Annotated, Any

import tomllib
from protocli import Complete

PATH = Path.home() / ".config" / "dienpy" / "ai.toml"

LOCAL_URL = "http://localhost:8081/v1/chat/completions"

HAIKU = "claude-haiku-4-5"
SONNET = "claude-sonnet-5"
OPUS = "claude-opus-5"
FABLE = "claude-fable-5-1"


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
