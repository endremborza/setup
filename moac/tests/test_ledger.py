"""The ledger and what feeds it: a captured call's row, image input on an openai endpoint, the
labels `resolve` gives a backend, and what `moac ledger` and `moac profiles` print of them."""

import json

import pytest
import requests

from moac import Api, Need, Openai, resolve, send
from moac import _ledger, _profiles, _serve
from moac import ledger as ledger_cmd
from moac import profiles as profiles_cmd

_TOML = """\
[profile.eye]
kind = "openai"
url = "http://localhost:9/v1/chat/completions"
model = "tiny"
serve = "eye.service"

[tool]
look = "eye"
"""


class _Answer:
    ok = True

    def json(self) -> dict:
        return {
            "model": "tiny-q4",
            "choices": [{"message": {"content": "a skeleton"}}],
            "usage": {"prompt_tokens": 300, "completion_tokens": 4},
        }


@pytest.fixture
def endpoint(monkeypatch):
    """The bodies posted to a fake endpoint, which answers each."""
    bodies: list[dict] = []

    def post(url, json, timeout):
        bodies.append(json)
        return _Answer()

    monkeypatch.setattr(requests, "post", post)
    return bodies


@pytest.fixture
def eye(tmp_path):
    _profiles.PATH.write_text(_TOML)
    return resolve("look", Need(images=True))


def test_a_call_is_one_ledger_row_without_its_prompt(eye, endpoint, tmp_path) -> None:
    picture = tmp_path / "frame.png"
    picture.write_bytes(b"\x89PNG")
    reply = send(eye, "", "what stands there?", images=[picture])
    assert reply.value == "a skeleton"
    image, text = endpoint[0]["messages"][0]["content"]
    assert image["image_url"]["url"].startswith("data:image/png;base64,")
    assert text == {"type": "text", "text": "what stands there?"}
    (row,) = _ledger.rows()
    assert (row["tool"], row["profile"], row["kind"]) == ("look", "eye", "openai")
    assert (row["model"], row["input_tokens"], row["images"]) == ("tiny-q4", 300, 1)
    assert row["seconds"] == reply.usage.seconds
    assert "stands" not in json.dumps(row) and "skeleton" not in json.dumps(row)


def test_a_failed_call_is_a_row_too(eye, monkeypatch) -> None:
    def post(url, json, timeout):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(requests, "post", post)
    with pytest.raises(SystemExit):
        send(eye, "", "anyone?")
    (row,) = _ledger.rows()
    assert "refused" in row["error"] and row["profile"] == "eye"


def test_labels_do_not_tell_backends_apart_and_an_api_takes_no_image(
    eye, tmp_path, monkeypatch
) -> None:
    assert eye == Openai(url="http://localhost:9/v1/chat/completions", model="tiny")
    assert (eye.profile, eye.tool) == ("eye", "look")
    monkeypatch.setattr(_profiles, "PATH", tmp_path / "api.toml")
    _profiles.PATH.write_text('[profile.deep]\nkind = "api"\nmodel = "claude-x"\n')
    with pytest.raises(SystemExit, match="no image input"):
        resolve("look", Need(images=True), profile="deep")
    with pytest.raises(SystemExit, match="api backends"):
        send(Api(model="claude-x"), "", "look", images=["frame.png"])


def test_ledger_sums_calls_per_tool_and_profile(eye, endpoint, capsys) -> None:
    for _ in range(3):
        send(eye, "", "again")
    ledger_cmd.main(tool="look")
    out = capsys.readouterr().out
    assert "eye" in out and "tiny-q4" in out and "900" in out
    ledger_cmd.main(tool="other")
    assert "tiny-q4" not in capsys.readouterr().out
    ledger_cmd.main(last=1)
    assert capsys.readouterr().out.count("tiny-q4") == 1


def test_profiles_say_what_serves_one_and_whether_it_is_up(
    eye, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(_serve, "active", lambda served: False)
    profiles_cmd.main()
    out = capsys.readouterr().out
    assert "serve=eye.service" in out and "down (moac up eye)" in out
    assert str(_profiles.PATH) in out and str(_ledger.PATH) in out
    monkeypatch.setattr(_serve, "active", lambda served: True)
    monkeypatch.setattr(_serve, "reports", lambda spec: {"ctx": 4096, "vision": True})
    profiles_cmd.main()
    assert "up ctx=4096 vision=True" in capsys.readouterr().out
