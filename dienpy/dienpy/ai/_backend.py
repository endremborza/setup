"""Backends as a tagged union; capability-checked resolution from profiles.

A caller declares a Need; `resolve` picks the profile bound to the tool (or an
explicitly named one), builds the backend, and refuses loudly when the backend
cannot serve the need — the mismatch surfaces before any tokens are spent.
"""

from dataclasses import dataclass
from typing import Annotated, Any

from protocli import Complete

from . import _profiles

# one vocabulary, interpreted per backend: api maps it to a thinking budget
# (x4 ladder), cli passes it to `claude --effort`, openai refuses it.
EFFORTS = ("low", "medium", "high", "xhigh", "max")
EFFORT_BUDGETS = dict(zip(EFFORTS, (2048, 8192, 32768, 131072, 262144)))

# advisory, not enforced: the backend validates and names the valid set itself
Effort = Annotated[str, Complete(EFFORTS)]
_AUTHS = ("login", "env")


@dataclass(frozen=True)
class Need:
    schema: bool = False
    tools: tuple[str, ...] = ()
    effort: str = ""  # "" = the backend's default, no thinking config passed
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
    effort: str = ""
    timeout: int = 300


@dataclass(frozen=True)
class Cli:
    """`claude -p` subprocess; login auth is the claude command's own claude.ai credentials."""

    model: str
    # env keeps ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN in the environment
    auth: str = "login"
    tools: tuple[str, ...] = ()
    effort: str = ""
    timeout: int = 300


Backend = Openai | Api | Cli


def resolve(tool: str, need: Need, profile: str = "") -> Backend:
    name = profile or _profiles.for_tool(tool)
    # an unrecognized name is a bare model for the claude CLI, so ad-hoc model ids keep working
    spec: dict[str, Any] = _profiles.profiles().get(
        name, {"kind": "cli", "model": name}
    )
    kind = spec.get("kind")
    effort = need.effort or str(spec.get("effort", ""))
    if effort and effort not in EFFORTS:
        raise SystemExit(
            f"profile '{name}': invalid effort '{effort}' (one of: {', '.join(EFFORTS)})"
        )
    # profile timeout (deployment knowledge) beats the caller's workload default
    timeout = int(spec.get("timeout", need.timeout))

    def refuse(what: str) -> SystemExit:
        return SystemExit(f"profile '{name}' ({kind}) cannot serve '{tool}': {what}")

    if kind == "openai":
        if need.tools:
            raise refuse(f"no repo tool access ({', '.join(need.tools)} requested)")
        if effort:
            raise refuse("no effort control on an openai endpoint")
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
        return Api(model=model, effort=effort, timeout=timeout)
    if kind == "cli":
        auth = spec.get("auth", "login")
        if auth not in _AUTHS:
            raise SystemExit(
                f"profile '{name}': invalid auth '{auth}' (one of: {', '.join(_AUTHS)})"
            )
        return Cli(
            model=spec.get("model", name),
            auth=auth,
            tools=need.tools,
            effort=effort,
            timeout=timeout,
        )
    raise SystemExit(f"profile '{name}': unknown backend kind '{kind}'")
