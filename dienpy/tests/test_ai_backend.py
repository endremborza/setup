"""ai backend: profile layering, tool bindings, capability-checked resolve, the run target completion."""

from pathlib import Path

import pytest
from dienpy.ai import _cache, _profiles, models
from dienpy.ai._backend import Api, Cli, Need, Openai, resolve
from dienpy.ai.run import backend

_TOML = """\
default = "tunnel"

[profile.tunnel]
kind = "openai"
url = "http://localhost:9999/v1/chat/completions"
model = "qwen"

[profile.deep]
kind = "api"
model = "claude-opus-5"
effort = "medium"

[profile.slow]
kind = "cli"
model = "opus"
timeout = 1800

[tool]
hunks = "slow"
run = "slow"
"""


@pytest.fixture
def config(tmp_path: Path, monkeypatch):
    """`config(text)` points the profile store at a fresh toml (None: no file)."""
    n = 0

    def _set(text: str | None) -> None:
        nonlocal n
        n += 1
        path = tmp_path / str(n) / "ai.toml"
        path.parent.mkdir()
        if text is not None:
            path.write_text(text)
        monkeypatch.setattr(_profiles, "PATH", path)

    return _set


def _refused(fn) -> str:
    with pytest.raises(SystemExit) as e:
        fn()
    return str(e.value)


def test_missing_file_is_working_defaults(config) -> None:
    config(None)
    assert "sonnet" in _profiles.names()
    assert _profiles.for_tool("hunks") == "sonnet"
    assert resolve("hunks", Need(schema=True)) == Cli(model=_profiles.SONNET)


def test_toml_layers_over_builtins(config) -> None:
    config(_TOML)
    assert _profiles.get("tunnel")["url"].startswith("http://localhost:9999")
    assert _profiles.get("haiku") == {"kind": "cli", "model": _profiles.HAIKU}
    assert _profiles.for_tool("hunks") == "slow"
    assert _profiles.for_tool("commit") == "tunnel"


def test_resolve_builds_each_kind(config) -> None:
    config(_TOML)
    assert resolve("commit", Need()) == Openai(
        url="http://localhost:9999/v1/chat/completions", model="qwen"
    )
    assert resolve("x", Need(effort="high"), profile="deep") == Api(
        model="claude-opus-5", effort="high"
    )
    assert resolve("x", Need(), profile="deep") == Api(
        model="claude-opus-5", effort="medium"
    )
    assert resolve("hunks", Need(schema=True, timeout=900)) == Cli(
        model="opus", timeout=1800
    )
    assert resolve("x", Need(effort="xhigh"), profile="slow") == Cli(
        model="opus", effort="xhigh", timeout=1800
    )


def test_unknown_profile_is_bare_cli_model(config) -> None:
    config(None)
    assert resolve("x", Need(), profile="claude-opus-5") == Cli(model="claude-opus-5")


def test_run_backend_binding_and_timeout_precedence(config) -> None:
    config(_TOML)
    assert backend().model == "opus" and backend().timeout == 1800
    assert backend("slow", timeout=60).timeout == 60
    assert backend("fabx").timeout == 10800
    assert "tunnel" in _refused(lambda: backend("tunnel"))


def test_capability_mismatches_refuse_loudly(config) -> None:
    config(_TOML)
    msg = _refused(lambda: resolve("hunks", Need(tools=("Read",)), profile="tunnel"))
    assert "tunnel" in msg and "Read" in msg
    assert "schema" in _refused(lambda: resolve("x", Need(schema=True), profile="deep"))
    assert "effort" in _refused(
        lambda: resolve("x", Need(effort="high"), profile="tunnel")
    )
    assert "invalid effort" in _refused(
        lambda: resolve("x", Need(effort="ultracode"), profile="slow")
    )


def test_bad_specs_refuse_loudly(config) -> None:
    config('[profile.p]\nkind = "openai"\n')
    assert "url" in _refused(lambda: resolve("x", Need(), profile="p"))
    config('[profile.p]\nkind = "smoke"\n')
    assert "kind" in _refused(lambda: resolve("x", Need(), profile="p"))
    config('[profile.p]\nkind = "cli"\nauth = "oauth"\n')
    assert "auth" in _refused(lambda: resolve("x", Need(), profile="p"))
    config('[profile.p]\nkind = "cli"\neffort = "extreme"\n')
    assert "invalid effort" in _refused(lambda: resolve("x", Need(), profile="p"))


def test_run_target_completes_profiles_and_cached_models(
    config, tmp_path, monkeypatch
) -> None:
    config(None)
    monkeypatch.setattr(_cache, "PATH", tmp_path / "models.json")
    assert models.choices() == _profiles.names()
    _cache.save("anthropic", ["claude-x-1"])
    _cache.save("google", ["gemini-x"])
    assert models.choices() == _profiles.names() + ["claude-x-1"]
    assert _cache.needs_refresh("anthropic") is False and _cache.needs_refresh("other")
