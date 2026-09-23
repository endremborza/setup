"""cli argv shared by send/launch, permission-mode rules, stream-json outcome parsing, supervision."""

import io
import json
import os
import subprocess
import time
from pathlib import Path

import pytest
from dienpy.ai import _profiles, _stream
from dienpy.ai._backend import Cli, Need, resolve
from dienpy.ai._transport import TIMEOUT, cli_argv, cli_env, launch, send, supervise
from dienpy.ai.run import unattended_suffix


def test_argv_carries_model_effort_and_mode() -> None:
    assert cli_argv(Cli(model="m")) == ["claude", "--model", "m"]
    assert cli_argv(Cli(model="m", effort="xhigh", permission_mode="auto")) == [
        "claude",
        "--model",
        "m",
        "--effort",
        "xhigh",
        "--permission-mode",
        "auto",
    ]


def test_login_auth_drops_api_keys(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "t")
    assert "ANTHROPIC_API_KEY" not in cli_env(Cli(model="m"))
    assert cli_env(Cli(model="m", auth="env"))["ANTHROPIC_AUTH_TOKEN"] == "t"


def test_unattended_suffix_commit_toggle() -> None:
    assert "Never commit" in unattended_suffix()
    assert "Never commit" not in unattended_suffix(commit=True)


def test_builtin_shortcuts_resolve_pinned_models() -> None:
    fabx = resolve("run", Need(timeout=7), profile="fabx")
    assert fabx == Cli(model=_profiles.FABLE, effort="xhigh", timeout=7)
    assert resolve("run", Need(), profile="opux").model == _profiles.OPUS
    assert resolve("run", Need(), profile="haiku").effort == ""


def test_follow_collects_session_and_result() -> None:
    events = [
        {"type": "system", "subtype": "init", "session_id": "s1", "model": "m"},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}
                ]
            },
        },
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "done.",
            "num_turns": 3,
            "session_id": "s1",
        },
    ]
    log = io.StringIO()
    out = _stream.follow(
        io.StringIO("".join(json.dumps(e) + "\n" for e in events)), log
    )
    assert out.session_id == "s1" and out.result == "done." and out.turns == 3
    assert out.ok
    assert log.getvalue().count("\n") == 3


def test_follow_without_result_is_not_ok() -> None:
    out = _stream.follow(
        io.StringIO('{"type":"system","subtype":"init","session_id":"s2"}\n'), None
    )
    assert out.session_id == "s2" and out.result == ""
    assert _stream.Outcome(returncode=1, session_id="s2").ok is False


def _drain(proc: subprocess.Popen) -> _stream.Outcome:
    return _stream.Outcome(result=proc.stdout.read())


def test_supervise_timeout_kills_the_whole_group() -> None:
    started = time.monotonic()
    out = supervise(
        "sleep 30; echo late", 1, _drain, shell=True, stdout=subprocess.PIPE
    )
    assert time.monotonic() - started < 5
    assert out.subtype == TIMEOUT and not out.ok and out.returncode == -9
    assert (
        subprocess.run(
            ["pgrep", "-f", "sleep 30; echo late"], capture_output=True
        ).returncode
        == 1
    )


def test_supervise_passes_exit_status_and_replaces_bad_bytes() -> None:
    out = supervise(
        ["sh", "-c", "printf '\\377ok'; exit 3"], 5, _drain, stdout=subprocess.PIPE
    )
    assert out.returncode == 3 and out.result == "�ok" and out.subtype == ""


def fake_claude(tmp_path: Path, monkeypatch, script: str) -> Path:
    """A `claude` on PATH that runs `script` (sh) instead; its argv arrives as "$@"."""
    fake = tmp_path / "claude"
    fake.write_text(f"#!/bin/sh\n{script}\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    return fake


def test_launch_notices_a_prompt_left_unread(tmp_path: Path, monkeypatch) -> None:
    fake_claude(tmp_path, monkeypatch, "exit 0")
    out = launch(Cli(model="m", timeout=5), "x" * 300_000)
    assert out.returncode == 0 and out.is_error and "before reading" in out.result


def test_send_captures_the_json_reply_and_times_out_loudly(
    tmp_path: Path, monkeypatch
) -> None:
    fake_claude(
        tmp_path,
        monkeypatch,
        'cat >/dev/null; printf \'{"is_error": false, "result": " hi ", "structured_output": {"k": 1}}\'',
    )
    assert send(Cli(model="m", timeout=5), "sys", "user") == "hi"
    assert send(Cli(model="m", timeout=5), "", "user", schema={"type": "object"}) == {
        "k": 1
    }
    fake_claude(tmp_path, monkeypatch, "cat >/dev/null; sleep 30; echo late")
    started = time.monotonic()
    with pytest.raises(SystemExit) as e:
        send(Cli(model="m", timeout=1), "", "user")
    assert "timed out" in str(e.value) and time.monotonic() - started < 5
