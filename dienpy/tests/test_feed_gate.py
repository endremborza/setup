"""The headroom gate over usage windows."""

import datetime

from dienpy.feed import _gate
from moac._profiles import FABLE, OPUS
from moac.usage import Window

_SESSION_RESET = datetime.datetime.fromisoformat("2026-09-01T23:29:59+00:00")
_WEEK_RESET = datetime.datetime.fromisoformat("2026-09-02T11:59:59+00:00")

WINDOWS = [
    Window("session", 33.0, _SESSION_RESET),
    Window("weekly_all", 4.0, _WEEK_RESET),
    Window("weekly_scoped", 6.0, _WEEK_RESET, "Fable"),
]


def test_scoped_window_applies_to_its_model_only() -> None:
    t = _gate.Thresholds(session=75, weekly=97, scoped=5)
    assert [w.kind for w in _gate.blockers(WINDOWS, FABLE, t)] == ["weekly_scoped"]
    assert _gate.blockers(WINDOWS, OPUS, t) == []
    assert _gate.pick(WINDOWS, [FABLE, OPUS], t).model == OPUS


def test_load_at_the_ceiling_still_runs() -> None:
    t = _gate.Thresholds(session=97)
    assert _gate.blockers(WINDOWS, OPUS, t, need=64) == []
    assert [w.kind for w in _gate.blockers(WINDOWS, OPUS, t, need=65)] == ["session"]


def test_all_blocked_wakes_at_earliest_reset() -> None:
    t = _gate.Thresholds(session=30, weekly=97, scoped=97)
    v = _gate.pick(WINDOWS, [FABLE, OPUS], t)
    assert v.model == ""
    assert [w.kind for w in v.blockers] == ["session"]
    assert v.wake_at == _SESSION_RESET


def test_first_eligible_in_preference_order() -> None:
    ws = [Window("session", 10.0, None), Window("weekly_scoped", 99.0, None, "Fable")]
    assert _gate.pick(ws, [FABLE, OPUS], _gate.Thresholds()).model == OPUS
    assert _gate.pick(ws, [OPUS, FABLE], _gate.Thresholds()).model == OPUS
    assert _gate.pick(ws, [FABLE], _gate.Thresholds()).wake_at is None
