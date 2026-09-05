"""cli argv shared by send/launch, permission-mode rules, stream-json outcome parsing."""

import io
import json

from dienpy.ai import _stream
from dienpy.ai._backend import Cli, Need, resolve
from dienpy.ai._transport import cli_argv, cli_env
from dienpy.ai.run import unattended_suffix


def test_argv_carries_model_effort_and_mode() -> None:
    assert cli_argv(Cli(model="m")) == ["claude", "--model", "m"]
    assert cli_argv(Cli(model="m", effort="xhigh", permission_mode="auto")) == [
        "claude", "--model", "m", "--effort", "xhigh", "--permission-mode", "auto",
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
    assert fabx == Cli(model="claude-fable-5-1", effort="xhigh", timeout=7)
    assert resolve("run", Need(), profile="opux").model == "claude-opus-5"
    assert resolve("run", Need(), profile="haiku").effort == ""


def test_follow_collects_session_and_result() -> None:
    events = [
        {"type": "system", "subtype": "init", "session_id": "s1", "model": "m"},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}]}},
        {"type": "result", "subtype": "success", "is_error": False, "result": "done.", "num_turns": 3, "session_id": "s1"},
    ]
    log = io.StringIO()
    out = _stream.follow(io.StringIO("".join(json.dumps(e) + "\n" for e in events)), log)
    assert out.session_id == "s1" and out.result == "done." and out.turns == 3
    assert out.ok
    assert log.getvalue().count("\n") == 3


def test_follow_without_result_is_not_ok() -> None:
    out = _stream.follow(io.StringIO('{"type":"system","subtype":"init","session_id":"s2"}\n'), None)
    assert out.session_id == "s2" and out.result == ""
    assert _stream.Outcome(returncode=1, session_id="s2").ok is False
