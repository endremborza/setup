"""One `send` per backend kind, plus provider model listing and the cli launcher.

`system` and `user` are separate roles on openai/api transports; the cli
transport concatenates them into the single `-p` prompt. With a schema, the
return value is the parsed object (each backend using its own mechanism:
response_format, --json-schema); without one it is the reply text.

`launch` is the other cli shape: a session with inherited stdio (interactive, or
`-p` streaming to the terminal / a stream-json log) — what a shell shortcut or an
unattended queue starts, as opposed to the captured call `send` makes.

`supervise` is the one child-process runner under both: a timeout that kills the
whole process group, and a launcher signal (SIGTERM, SIGHUP, Ctrl-C) that takes the
child down before the launcher exits.
"""

import contextlib
import dataclasses
import json
import os
import signal
import subprocess
import threading
from collections.abc import Callable, Iterator
from typing import IO, Any

from . import _stream
from ._backend import GEMINI_BUDGETS, Api, Backend, Cli, Openai

# the outcome subtype of a run `supervise` had to kill
TIMEOUT = "timeout"

# thinking tokens count against max_tokens, so a caller's reply budget is only a floor
_THINKING_FLOOR = 16000
_LIST_TIMEOUT = 30


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
        if schema is not None:
            raise SystemExit("schema output not implemented for api backends")
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
    if backend.model.startswith("claude"):
        return _send_anthropic(backend, system, user, max_tokens)
    if backend.model.startswith("gemini"):
        budget = GEMINI_BUDGETS[backend.effort] if backend.effort else None
        return _send_google(backend, system, user, max_tokens, budget, temperature)
    raise SystemExit(
        f"cannot infer provider for model '{backend.model}' (expected claude-* or gemini-*)"
    )


def _send_anthropic(backend: Api, system: str, user: str, max_tokens: int) -> str:
    """Adaptive thinking throughout, effort steering its depth; current models refuse
    sampling knobs next to thinking, so temperature never reaches this transport."""
    import anthropic

    _require("ANTHROPIC_API_KEY")
    kwargs: dict[str, Any] = {
        "model": backend.model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "thinking": {"type": "adaptive"},
    }
    if backend.effort:
        kwargs["output_config"] = {"effort": backend.effort}
    msg = anthropic.Anthropic().messages.create(**kwargs)
    if msg.stop_reason == "refusal":
        raise SystemExit("model refused the request")
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


def cli_argv(backend: Cli) -> list[str]:
    cmd = ["claude", "--model", backend.model]
    if backend.effort:
        cmd += ["--effort", backend.effort]
    if backend.permission_mode:
        cmd += ["--permission-mode", backend.permission_mode]
    return cmd


def cli_env(backend: Cli) -> dict[str, str]:
    env = os.environ.copy()
    if backend.auth == "login":
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
    return env


@contextlib.contextmanager
def _terminating() -> Iterator[None]:
    """SIGTERM/SIGHUP raise in the launcher, so the child is taken down on the way out."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def raise_exit(signum: int, frame: object) -> None:
        raise SystemExit(128 + signum)

    previous = {
        s: signal.signal(s, raise_exit) for s in (signal.SIGTERM, signal.SIGHUP)
    }
    try:
        yield
    finally:
        for s, handler in previous.items():
            signal.signal(s, handler)


def supervise(
    cmd: list[str] | str,
    timeout: float | None,
    consume: Callable[[subprocess.Popen], _stream.Outcome],
    *,
    group: bool = True,
    **popen: Any,
) -> _stream.Outcome:
    """Run `cmd` to completion; `consume` reads the child while it runs.

    The child leads its own process group so a timeout or a dying launcher kills
    everything it spawned. `group=False` leaves it in the terminal's session: an
    interactive claude must stay in the foreground group to own the tty (and inherits
    the terminal's own Ctrl-C and hangup). Pipes decode with replacement, so stray
    bytes never abort a run.
    """
    proc = subprocess.Popen(cmd, start_new_session=group, errors="replace", **popen)
    timed_out = threading.Event()

    def kill() -> None:
        try:
            if group:
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
        except ProcessLookupError:
            pass

    def expire() -> None:
        # flag before kill, so wait() cannot return with the flag still unset
        timed_out.set()
        kill()

    timer = threading.Timer(timeout, expire) if timeout else None
    with _terminating():
        if timer:
            timer.start()
        try:
            outcome = consume(proc)
            rc = proc.wait()
        except BaseException:
            kill()
            proc.wait()
            raise
        finally:
            if timer:
                timer.cancel()
    if timed_out.is_set():
        return dataclasses.replace(
            outcome,
            returncode=rc,
            is_error=True,
            subtype=TIMEOUT,
            result=f"timed out after {timeout:.0f}s",
        )
    return dataclasses.replace(outcome, returncode=rc)


def launch(
    backend: Cli,
    prompt: str | None,
    *,
    interactive: bool = False,
    safe: bool = False,
    system: str = "",
    resume: str = "",
    log: IO[str] | None = None,
    cwd: str | None = None,
) -> _stream.Outcome:
    """Start a claude session and wait for it.

    Interactive sessions inherit the terminal (a prompt, if any, arrives on stdin the
    way a pipe would). Non-interactive ones run `-p` with the prompt on stdin and the
    permission mode forced to auto unless the profile set one; with `log`, the session
    streams stream-json into it while progress lines go to stdout, and the outcome
    carries the session id and final result — otherwise the reply prints as text.
    """
    if not interactive and not prompt:
        raise SystemExit("a non-interactive session needs a prompt")
    if interactive and (log or resume):
        raise SystemExit("log/resume apply to non-interactive sessions")
    if not interactive and not backend.permission_mode:
        backend = dataclasses.replace(backend, permission_mode="auto")
    cmd = cli_argv(backend)
    if safe:
        cmd.append("--safe-mode")
    if system:
        cmd += ["--append-system-prompt", system]
    if not interactive:
        cmd.append("-p")
        if resume:
            cmd += ["--resume", resume]
        if log is not None:
            cmd += ["--output-format", "stream-json", "--verbose"]
    unread = False

    def consume(proc: subprocess.Popen) -> _stream.Outcome:
        nonlocal unread
        if proc.stdin is not None:
            try:
                proc.stdin.write(prompt or "")
                proc.stdin.close()
            except BrokenPipeError:
                unread = True
        if proc.stdout is None:
            return _stream.Outcome()
        return _stream.follow(proc.stdout, log)

    try:
        outcome = supervise(
            cmd,
            None if interactive else backend.timeout,
            consume,
            group=not interactive,
            stdin=subprocess.PIPE if prompt is not None else None,
            stdout=subprocess.PIPE if log is not None else None,
            cwd=cwd,
            env=cli_env(backend),
        )
    except FileNotFoundError:
        raise SystemExit("claude CLI not found on PATH")
    if unread and outcome.ok:
        return dataclasses.replace(
            outcome, is_error=True, result="claude exited before reading the prompt"
        )
    return outcome


def _send_cli(
    backend: Cli, system: str, user: str, schema: dict | None, cwd: str | None
) -> str | dict:
    prompt = f"{system}\n\n{user}" if system else user
    cmd = cli_argv(backend) + [
        "-p",
        "--output-format",
        "json",
        "--tools",
        ",".join(backend.tools),
    ]
    if schema is not None:
        cmd += ["--json-schema", json.dumps(schema)]
    stderr: list[str] = []

    def consume(proc: subprocess.Popen) -> _stream.Outcome:
        out, err = proc.communicate(prompt)
        stderr.append(err)
        return _stream.Outcome(result=out)

    try:
        res = supervise(
            cmd,
            backend.timeout,
            consume,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=cli_env(backend),
        )
    except FileNotFoundError:
        raise SystemExit("claude CLI not found on PATH")
    if res.subtype == TIMEOUT:
        raise SystemExit(f"claude {res.result}")
    if res.returncode != 0:
        raise SystemExit("claude failed: " + _cli_failure(res, stderr[0]))
    try:
        outer = json.loads(res.result)
    except json.JSONDecodeError:
        raise SystemExit(
            f"claude returned non-JSON output: {res.result.strip()[-400:]}"
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


def _cli_failure(res: _stream.Outcome, stderr: str) -> str:
    parts = []
    try:
        outer = json.loads(res.result or "")
        if isinstance(outer.get("result"), str):
            parts.append(outer["result"])
    except json.JSONDecodeError:
        if res.result and res.result.strip():
            parts.append(res.result.strip()[-400:])
    if stderr and stderr.strip():
        parts.append(stderr.strip()[-400:])
    return "\n".join(parts) or f"exit code {res.returncode}"
