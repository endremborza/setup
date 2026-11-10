"""`moac ask`: schema loading, profile resolution through the tool binding, the printed reply."""

import json

import pytest

from moac import ask as ask_cmd


def test_schema_is_inline_json_or_a_file(tmp_path) -> None:
    inline = '{"type": "object"}'
    path = tmp_path / "s.json"
    path.write_text(inline)
    assert (
        ask_cmd.load_schema(inline)
        == ask_cmd.load_schema(str(path))
        == {"type": "object"}
    )
    assert ask_cmd.load_schema("") is None
    with pytest.raises(SystemExit):
        ask_cmd.load_schema("[1]")


def test_envelope_names_the_profile_and_carries_the_reply(monkeypatch, capsys) -> None:
    calls = []

    def fake_send(backend, system, user, *, schema, cwd):
        calls.append((backend, user, schema, cwd))
        return {"choice": "b"}

    monkeypatch.setattr(ask_cmd, "send", fake_send)
    ask_cmd.main(
        "haiku",
        raw="pick one",
        schema='{"type": "object"}',
        tools=["Read"],
        cwd="/frames",
        envelope=True,
    )
    out = json.loads(capsys.readouterr().out)
    backend, user, schema, cwd = calls[0]
    assert (user, schema, cwd, backend.tools) == (
        "pick one",
        {"type": "object"},
        "/frames",
        ("Read",),
    )
    assert out["profile"] == "haiku" and out["kind"] == "cli"
    assert out["reply"] == {"choice": "b"}
