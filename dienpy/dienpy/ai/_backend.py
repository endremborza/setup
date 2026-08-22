"""Backends as a tagged union; capability-checked resolution from profiles.

A caller declares a Need; `resolve` picks the profile bound to the tool (or an
explicitly named one), builds the backend, and refuses loudly when the backend
cannot serve the need — the mismatch surfaces before any tokens are spent.
"""

from dataclasses import dataclass
from typing import Any

from . import _profiles

EFFORTS = ("none", "low", "medium", "high")
_AUTHS = ("login", "env")


@dataclass(frozen=True)
class Need:
    schema: bool = False
    tools: tuple[str, ...] = ()
    effort: str = "none"
    timeout: int = 300


@dataclass(frozen=True)
class Openai:
    """OpenAI-compatible chat-completions endpoint — llama-server, vLLM, or a tunneled remote."""

    url: str
    model: str = ""
    timeout: int = 300


@dataclass(frozen=True)
class Api:
    """Direct SDK call with an API key; provider inferred from the model prefix."""

    model: str
    effort: str = "none"
    timeout: int = 300


@dataclass(frozen=True)
class Cli:
    """`claude -p` subprocess; login auth is the claude command's own claude.ai credentials."""

    model: str
    auth: str = (
        "login"  # env keeps ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN in the environment
    )
    tools: tuple[str, ...] = ()
    timeout: int = 300


Backend = Openai | Api | Cli


def resolve(tool: str, need: Need, profile: str = "") -> Backend:
    name = profile or _profiles.for_tool(tool)
    # an unrecognized name is a bare model for the claude CLI, so ad-hoc model ids keep working
    spec: dict[str, Any] = _profiles.profiles().get(
        name, {"kind": "cli", "model": name}
    )
    kind = spec.get("kind")
    if need.effort not in EFFORTS:
        raise SystemExit(
            f"invalid effort '{need.effort}' (one of: {', '.join(EFFORTS)})"
        )
    timeout = int(spec.get("timeout", need.timeout))

    def refuse(what: str) -> SystemExit:
        return SystemExit(f"profile '{name}' ({kind}) cannot serve '{tool}': {what}")

    if kind == "openai":
        if need.tools:
            raise refuse(f"no repo tool access ({', '.join(need.tools)} requested)")
        if need.effort != "none":
            raise refuse("thinking effort is an api-only knob")
        url = spec.get("url")
        if not url:
            raise SystemExit(f"profile '{name}': openai backend needs a url")
        return Openai(url=url, model=spec.get("model", ""), timeout=timeout)
    if kind == "api":
        if need.tools:
            raise refuse(f"no repo tool access ({', '.join(need.tools)} requested)")
        if need.schema:
            raise refuse("schema output not implemented for api backends")
        model = spec.get("model")
        if not model:
            raise SystemExit(f"profile '{name}': api backend needs a model")
        effort = need.effort if need.effort != "none" else spec.get("effort", "none")
        return Api(model=model, effort=effort, timeout=timeout)
    if kind == "cli":
        if need.effort != "none":
            raise refuse(
                "thinking effort is an api-only knob; pick a stronger model instead"
            )
        auth = spec.get("auth", "login")
        if auth not in _AUTHS:
            raise SystemExit(
                f"profile '{name}': invalid auth '{auth}' (one of: {', '.join(_AUTHS)})"
            )
        return Cli(
            model=spec.get("model", name), auth=auth, tools=need.tools, timeout=timeout
        )
    raise SystemExit(f"profile '{name}': unknown backend kind '{kind}'")
