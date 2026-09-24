from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from setup.runner import REGISTRY, Brick, run, verify


@pytest.fixture(autouse=True)
def isolated_registry():
    original = REGISTRY.copy()
    REGISTRY.clear()
    yield
    REGISTRY.clear()
    REGISTRY.extend(original)


def make_brick(
    name: str, profile: str, check: str | None = None
) -> tuple[MagicMock, Brick]:
    fn = MagicMock()
    s = Brick(fn=fn, name=name, profile=profile, check=check)
    REGISTRY.append(s)
    return fn, s


@pytest.mark.parametrize(
    ("profiles", "expected"),
    [
        (None, {"apt"}),
        (["shell"], {"apt", "tmux"}),
        (["shell", "dev"], {"apt", "tmux", "node"}),
    ],
)
def test_run_resolves_profiles_with_base_implicit(profiles, expected):
    fns = {
        name: make_brick(name, profile=profile)[0]
        for name, profile in (("apt", "base"), ("tmux", "shell"), ("node", "dev"))
    }

    run(profiles=profiles)

    assert {name for name, fn in fns.items() if fn.called} == expected


def test_run_single_brick_by_name():
    fn0, _ = make_brick("base-brick", profile="base")
    fn1, _ = make_brick("dev-brick", profile="dev")

    run(profiles=None, brick_name="dev-brick")

    fn0.assert_not_called()
    fn1.assert_called_once()


def test_run_unknown_brick_exits():
    with pytest.raises(SystemExit):
        run(profiles=None, brick_name="nonexistent")


def test_run_skips_when_check_passes():
    fn, _ = make_brick("checked", profile="base", check="true")

    with patch("setup.runner.check_passes", return_value=True):
        run(profiles=None)

    fn.assert_not_called()


def test_run_executes_when_check_fails():
    fn, _ = make_brick("checked", profile="base", check="false")

    with patch("setup.runner.check_passes", return_value=False):
        run(profiles=None)

    fn.assert_called_once()


def test_run_force_ignores_check():
    fn, _ = make_brick("checked", profile="base", check="true")

    with patch("setup.runner.check_passes", return_value=True):
        run(profiles=None, force=True)

    fn.assert_called_once()


def test_run_fails_when_check_still_fails_after_install(capsys):
    fn, _ = make_brick("checked", profile="base", check="false")

    assert run(profiles=None) is False

    fn.assert_called_once()
    assert "still fails after install" in capsys.readouterr().out


def test_run_passes_when_install_makes_check_pass(tmp_path):
    marker = tmp_path / "installed"
    fn = MagicMock(side_effect=lambda: marker.touch())
    REGISTRY.append(Brick(fn=fn, name="m", profile="base", check=f"test -e {marker}"))

    assert run(profiles=None) is True


def test_run_dry_run_skips_execution():
    fn, _ = make_brick("base-brick", profile="base")

    run(profiles=None, dry_run=True)

    fn.assert_not_called()


def test_run_continues_after_failure(capsys):
    fn_fail = MagicMock(side_effect=RuntimeError("boom"))
    fn_ok = MagicMock()
    REGISTRY.append(Brick(fn=fn_fail, name="fail", profile="base"))
    REGISTRY.append(Brick(fn=fn_ok, name="ok", profile="base"))

    run(profiles=None)

    fn_ok.assert_called_once()
    assert "[FAIL]" in capsys.readouterr().out


def test_verify_returns_true_when_all_pass():
    REGISTRY.append(Brick(fn=MagicMock(), name="a", profile="base", verify="true"))
    REGISTRY.append(Brick(fn=MagicMock(), name="b", profile="base", verify="true"))

    assert verify(profiles=None) is True


def test_verify_returns_false_on_failure():
    REGISTRY.append(Brick(fn=MagicMock(), name="a", profile="base", verify="false"))

    assert verify(profiles=None) is False


def test_verify_skips_bricks_without_verify():
    REGISTRY.append(Brick(fn=MagicMock(), name="no-verify", profile="base"))

    with patch("setup.runner.run_check") as mock_check:
        verify(profiles=None)
    mock_check.assert_not_called()


def test_verify_respects_profile_set():
    REGISTRY.append(
        Brick(fn=MagicMock(), name="base-vfy", profile="base", verify="true")
    )
    REGISTRY.append(
        Brick(fn=MagicMock(), name="server-vfy", profile="server", verify="true")
    )

    with patch("setup.runner.run_check", return_value=(True, "")) as mock_check:
        verify(profiles=["shell"])

    # base is implicit, shell has no steps registered, server is excluded
    assert mock_check.call_count == 1
