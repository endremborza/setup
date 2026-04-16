from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from setup.runner import REGISTRY, Step, run, update


@pytest.fixture(autouse=True)
def isolated_registry():
    original = REGISTRY.copy()
    REGISTRY.clear()
    yield
    REGISTRY.clear()
    REGISTRY.extend(original)


def make_step(name: str, level: int, check: str | None = None) -> tuple[MagicMock, Step]:
    fn = MagicMock()
    s = Step(fn=fn, name=name, level=level, check=check)
    REGISTRY.append(s)
    return fn, s


def test_run_respects_level():
    fn0, _ = make_step("base", level=0)
    fn1, _ = make_step("dev", level=1)
    fn2, _ = make_step("server", level=2)

    run(level=1)

    fn0.assert_called_once()
    fn1.assert_called_once()
    fn2.assert_not_called()


def test_run_single_step_by_name():
    fn0, _ = make_step("base", level=0)
    fn1, _ = make_step("dev", level=1)

    run(level=0, step_name="dev")

    fn0.assert_not_called()
    fn1.assert_called_once()


def test_run_unknown_step_exits():
    with pytest.raises(SystemExit):
        run(level=4, step_name="nonexistent")


def test_run_skips_when_check_passes():
    fn, _ = make_step("checked", level=0, check="true")

    with patch("setup.runner._check_passes", return_value=True):
        run(level=0)

    fn.assert_not_called()


def test_run_executes_when_check_fails():
    fn, _ = make_step("checked", level=0, check="false")

    with patch("setup.runner._check_passes", return_value=False):
        run(level=0)

    fn.assert_called_once()


def test_run_dry_run_skips_execution():
    fn, _ = make_step("base", level=0)

    run(level=0, dry_run=True)

    fn.assert_not_called()


def test_run_continues_after_failure(capsys):
    fn_fail = MagicMock(side_effect=RuntimeError("boom"))
    fn_ok = MagicMock()
    REGISTRY.append(Step(fn=fn_fail, name="fail", level=0))
    REGISTRY.append(Step(fn=fn_ok, name="ok", level=0))

    run(level=0)

    fn_ok.assert_called_once()
    assert "[FAIL]" in capsys.readouterr().out


def test_update_ignores_check():
    fn, _ = make_step("checked", level=0, check="true")

    with patch("setup.runner._check_passes", return_value=True):
        update()

    fn.assert_called_once()


def test_update_single_step():
    fn0, _ = make_step("base", level=0)
    fn1, _ = make_step("dev", level=1)

    update(step_name="base")

    fn0.assert_called_once()
    fn1.assert_not_called()
