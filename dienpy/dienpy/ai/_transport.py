"""One `send` per backend kind, plus provider model listing.

`system` and `user` are separate roles on openai/api transports; the cli
transport concatenates them into the single `-p` prompt. With a schema, the
return value is the parsed object (each backend using its own mechanism:
response_format, --json-schema); without one it is the reply text.
"""

import json
import os
import subprocess
from typing import Any

from ._backend import Api, Backend, Cli, Openai

EFFORT_BUDGETS: dict[str, int | None] = {
    "none": None,
    "low": 2048,
    "medium": 8192,
    "high": 32768,
}

_ANTHROPIC_THINKING_BETA = "interleaved-thinking-2025-05-14"


def send(
    backend: Backend,
    system: str,
    user: str,
    *,
    schema: dict | None = None,
    max_tokens: int = 1024,
    temperature: float = 1.0,
    cwd: str | None = None,
) -> str | dict:
    if isinstance(backend, Openai):
        return _send_openai(backend, system, user, schema, max_tokens, temperature)
    if isinstance(backend, Api):
        return _send_api(backend, system, user, max_tokens, temperature)
    return _send_cli(backend, system, user, schema, cwd)


def fetch_models(provider: str) -> list[str]:
    if provider == "anthropic":
        import anthropic

        _require("ANTHROPIC_API_KEY")
        return sorted(m.id for m in anthropic.Anthropic().models.list())
    if provider == "google":
        return sorted(
            m.name.removeprefix("models/")
            for m in _google_client().models.list()
            if "generateContent" in (m.supported_actions or [])
        )
    raise SystemExit(f"unknown provider '{provider}'")


def _require(var: str) -> None:
    if not os.environ.get(var):
        raise SystemExit(f"{var} is not set.")


def _send_openai(
    backend: Openai,
    system: str,
    user: str,
    schema: dict | None,
    max_tokens: int,
    temperature: float,
) -> str | dict:
    import requests

    messages = [{"role": "system", "content": system}] if system else []
    messages.append({"role": "user", "content": user})
    body: dict[str, Any] = {
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if backend.model:
        body["model"] = backend.model
    if schema is not None:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "out", "schema": schema, "strict": True},
        }
    try:
        r = requests.post(backend.url, json=body, timeout=backend.timeout)
    except requests.RequestException as e:
        raise SystemExit(f"endpoint {backend.url} unreachable: {e}")
    if not r.ok:
        raise SystemExit(f"endpoint error {r.status_code}: {_openai_error(r)}")
    content = (r.json()["choices"][0]["message"].get("content") or "").strip()
    if not content:
        raise SystemExit("empty reply from endpoint")
    if schema is None:
        return content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        raise SystemExit(f"endpoint returned non-JSON despite schema: {content[:400]}")


def _openai_error(r) -> str:
    try:
        detail = r.json().get("error", {})
        if isinstance(detail, str):
            return detail
        return detail.get("message") or str(detail)
    except Exception:
        return r.text[:400]


def _send_api(
    backend: Api, system: str, user: str, max_tokens: int, temperature: float
) -> str:
    budget = EFFORT_BUDGETS[backend.effort]
    if backend.model.startswith("claude"):
        return _send_anthropic(backend, system, user, max_tokens, budget, temperature)
    if backend.model.startswith("gemini"):
        return _send_google(backend, system, user, max_tokens, budget, temperature)
    raise SystemExit(
        f"cannot infer provider for model '{backend.model}' (expected claude-* or gemini-*)"
    )


def _send_anthropic(
    backend: Api,
    system: str,
    user: str,
    max_tokens: int,
    budget: int | None,
    temperature: float,
) -> str:
    import anthropic

    _require("ANTHROPIC_API_KEY")
    kwargs: dict[str, Any] = {
        "model": backend.model,
        "max_tokens": max(max_tokens, budget + 1024) if budget else max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "temperature": temperature,
    }
    if budget:
        kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget}
        kwargs["extra_headers"] = {"anthropic-beta": _ANTHROPIC_THINKING_BETA}
    msg = anthropic.Anthropic().messages.create(**kwargs)
    for block in msg.content:
        if block.type == "text":
            return block.text.strip()
    raise SystemExit("No text content in model response.")


def _google_client():
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        return genai.Client(api_key=api_key)
    try:
        return genai.Client()
    except Exception:
        raise SystemExit(
            "Google auth not configured. Set GEMINI_API_KEY or run: "
            "gcloud auth application-default login"
        )


def _send_google(
    backend: Api,
    system: str,
    user: str,
    max_tokens: int,
    budget: int | None,
    temperature: float,
) -> str:
    from google.genai import types

    config = types.GenerateContentConfig(
        system_instruction=system,
        max_output_tokens=max_tokens,
        temperature=temperature,
        thinking_config=types.ThinkingConfig(thinking_budget=budget)
        if budget
        else None,
    )
    response = _google_client().models.generate_content(
        model=backend.model, contents=user, config=config
    )
    return (response.text or "").strip()


def _send_cli(
    backend: Cli, system: str, user: str, schema: dict | None, cwd: str | None
) -> str | dict:
    prompt = f"{system}\n\n{user}" if system else user
    cmd = [
        "claude",
        "-p",
        "--output-format",
        "json",
        "--model",
        backend.model,
        "--tools",
        ",".join(backend.tools),
    ]
    if schema is not None:
        cmd += ["--json-schema", json.dumps(schema)]
    env = os.environ.copy()
    if backend.auth == "login":
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
    try:
        res = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            cwd=cwd,
            env=env,
            timeout=backend.timeout,
        )
    except subprocess.TimeoutExpired:
        raise SystemExit(f"claude timed out after {backend.timeout}s")
    except FileNotFoundError:
        raise SystemExit("claude CLI not found on PATH")
    if res.returncode != 0:
        raise SystemExit("claude failed: " + _cli_failure(res))
    try:
        outer = json.loads(res.stdout)
    except json.JSONDecodeError:
        raise SystemExit(
            f"claude returned non-JSON output: {res.stdout.strip()[-400:]}"
        )
    if outer.get("is_error"):
        raise SystemExit(f"claude error: {outer.get('result')}")
    if schema is None:
        result = outer.get("result")
        if not isinstance(result, str):
            raise SystemExit("no text result in claude output")
        return result.strip()
    payload = outer.get("structured_output")
    if payload is None and isinstance(outer.get("result"), str):
        try:
            payload = json.loads(outer["result"])
        except json.JSONDecodeError:
            payload = None
    if not isinstance(payload, dict):
        raise SystemExit("no structured output in claude output")
    return payload


def _cli_failure(res: subprocess.CompletedProcess) -> str:
    parts = []
    try:
        outer = json.loads(res.stdout or "")
        if isinstance(outer.get("result"), str):
            parts.append(outer["result"])
    except json.JSONDecodeError:
        if res.stdout and res.stdout.strip():
            parts.append(res.stdout.strip()[-400:])
    if res.stderr and res.stderr.strip():
        parts.append(res.stderr.strip()[-400:])
    return "\n".join(parts) or f"exit code {res.returncode}"
