"""ai backend: profile layering, tool bindings, capability-checked resolve."""

import tempfile
from pathlib import Path

from dienpy.ai import _profiles
from dienpy.ai._backend import Api, Cli, Need, Openai, resolve

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
"""


def _with_config(text: str | None):
    d = tempfile.TemporaryDirectory()
    path = Path(d.name) / "ai.toml"
    if text is not None:
        path.write_text(text)
    _profiles.PATH = path
    return d


def _refused(fn) -> str:
    try:
        fn()
    except SystemExit as e:
        return str(e)
    raise AssertionError("expected SystemExit")


def test_missing_file_is_working_defaults() -> None:
    with _with_config(None):
        assert "sonnet" in _profiles.names()
        assert _profiles.for_tool("hunks") == "sonnet"
        backend = resolve("hunks", Need(schema=True))
        assert backend == Cli(model="sonnet")


def test_toml_layers_over_builtins() -> None:
    with _with_config(_TOML):
        assert _profiles.get("tunnel")["url"].startswith("http://localhost:9999")
        assert _profiles.get("haiku") == {"kind": "cli", "model": "haiku"}
        assert _profiles.for_tool("hunks") == "slow"
        assert _profiles.for_tool("commit") == "tunnel"


def test_resolve_builds_each_kind() -> None:
    with _with_config(_TOML):
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


def test_unknown_profile_is_bare_cli_model() -> None:
    with _with_config(None):
        assert resolve("x", Need(), profile="claude-opus-5") == Cli(
            model="claude-opus-5"
        )


def test_capability_mismatches_refuse_loudly() -> None:
    with _with_config(_TOML):
        msg = _refused(
            lambda: resolve("hunks", Need(tools=("Read",)), profile="tunnel")
        )
        assert "tunnel" in msg and "Read" in msg
        msg = _refused(lambda: resolve("x", Need(schema=True), profile="deep"))
        assert "schema" in msg
        msg = _refused(lambda: resolve("x", Need(effort="high"), profile="tunnel"))
        assert "effort" in msg
        msg = _refused(lambda: resolve("x", Need(effort="ultracode"), profile="slow"))
        assert "invalid effort" in msg


def test_bad_specs_refuse_loudly() -> None:
    with _with_config('[profile.p]\nkind = "openai"\n'):
        assert "url" in _refused(lambda: resolve("x", Need(), profile="p"))
    with _with_config('[profile.p]\nkind = "smoke"\n'):
        assert "kind" in _refused(lambda: resolve("x", Need(), profile="p"))
    with _with_config('[profile.p]\nkind = "cli"\nauth = "oauth"\n'):
        assert "auth" in _refused(lambda: resolve("x", Need(), profile="p"))
    with _with_config('[profile.p]\nkind = "cli"\neffort = "extreme"\n'):
        assert "invalid effort" in _refused(lambda: resolve("x", Need(), profile="p"))


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("AI BACKEND PASS")
