"""Ask one prompt through a profile and print the reply: the text, or JSON under --schema."""

import dataclasses
import json
from pathlib import Path
from typing import Annotated, Any

from protocli import FILES

from . import _profiles
from ._account import AccountName
from ._backend import Effort, Need, resolve
from ._transport import send
from .models import Target
from .run import read_prompt


def load_schema(schema: str) -> dict[str, Any] | None:
    """Inline JSON when it opens with `{` or `[`, else the path of a JSON file; empty is no schema."""
    if not schema:
        return None
    if schema.lstrip().startswith(("{", "[")):
        text = schema
    else:
        try:
            text = Path(schema).read_text()
        except OSError as e:
            raise SystemExit(f"--schema: {e}")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise SystemExit(f"--schema: {e}")
    if not isinstance(parsed, dict):
        raise SystemExit("--schema: a JSON schema is an object")
    return parsed


def main(
    profile: Target | None = None,
    file: Annotated[str, FILES] = "",
    *,
    tool: str = "ask",
    raw: str = "",
    system: str = "",
    schema: str = "",
    tools: list[str] = [],
    effort: Effort = "",
    timeout: int | None = None,
    cwd: Annotated[str, FILES] = "",
    image: list[str] = [],
    envelope: bool = False,
    account: AccountName = "",
) -> None:
    """Ask one prompt and print the reply: the captured call (`moac.send`) as a command.

    The prompt comes from --raw, the file (frontmatter stripped) or piped stdin. The profile
    defaults to the `[tool]` binding of --tool, then `default`, so a caller names its own tool
    key and each machine binds it in moac.toml. --schema (inline JSON or a file) makes the reply
    one JSON object; --tools lets a cli profile use claude tools, while --image sends a picture
    file with the prompt to an openai or cli profile; --effort and --timeout override the
    profile's. --envelope prints one JSON
    object instead: the profile, backend kind and effort, the call's usage (the model that
    answered, tokens, usd, seconds taken) and the reply.
    A profile that cannot serve the call is refused before anything is sent.
    """
    prompt = read_prompt(file, raw)
    if prompt is None:
        raise SystemExit("no prompt: pass a file, --raw, or pipe one in")
    parsed = load_schema(schema)
    name = profile or _profiles.for_tool(tool)
    backend = resolve(
        tool,
        Need(
            schema=parsed is not None,
            tools=tuple(tools),
            effort=effort,
            account=account,
            images=bool(image),
        ),
        name,
    )
    if timeout is not None:
        backend = dataclasses.replace(backend, timeout=timeout)
    reply = send(backend, system, prompt, schema=parsed, cwd=cwd or None, images=image)
    if envelope:
        print(
            json.dumps(
                {
                    "profile": name,
                    "kind": type(backend).__name__.lower(),
                    "effort": getattr(backend, "effort", ""),
                    **dataclasses.asdict(reply.usage),
                    "reply": reply.value,
                }
            )
        )
    elif isinstance(reply.value, dict):
        print(json.dumps(reply.value))
    else:
        print(reply.value)
