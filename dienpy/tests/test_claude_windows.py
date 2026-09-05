"""usage windows from the oauth payload's `limits`, and the headroom gate over them."""

import datetime

from dienpy.claude import _gate
from dienpy.claude.usage import Window, parse_windows

_T = "2026-09-02T11:59:59+00:00"
_S = "2026-09-01T23:29:59+00:00"

PAYLOAD = {
    "five_hour": {"utilization": 33.0, "resets_at": _S},
    "seven_day": {"utilization": 4.0, "resets_at": _T},
    "limits": [
        {"kind": "session", "group": "session", "percent": 33, "resets_at": _S, "scope": None},
        {"kind": "weekly_all", "group": "weekly", "percent": 4, "resets_at": _T, "scope": None},
        {
            "kind": "weekly_scoped",
            "group": "weekly",
            "percent": 6,
            "resets_at": _T,
            "scope": {"model": {"id": None, "display_name": "Fable"}, "surface": None},
        },
    ],
}

FABLE = "claude-fable-5-1"
OPUS = "claude-opus-5"


def test_parse_limits_with_scope() -> None:
    ws = parse_windows(PAYLOAD)
    assert [(w.kind, w.percent, w.model) for w in ws] == [
        ("session", 33.0, ""),
        ("weekly_all", 4.0, ""),
        ("weekly_scoped", 6.0, "Fable"),
    ]
    assert ws[2].label == "7-Day Fable"
    assert ws[0].resets_at == datetime.datetime.fromisoformat(_S)


def test_legacy_payload_without_limits() -> None:
    legacy = {k: v for k, v in PAYLOAD.items() if k != "limits"}
    assert [w.kind for w in parse_windows(legacy)] == ["session", "weekly_all"]


def test_scoped_window_applies_to_its_model_only() -> None:
    ws = parse_windows(PAYLOAD)
    t = _gate.Thresholds(session=75, weekly=97, scoped=5)
    assert [w.kind for w in _gate.blockers(ws, FABLE, t)] == ["weekly_scoped"]
    assert _gate.blockers(ws, OPUS, t) == []
    assert _gate.pick(ws, [FABLE, OPUS], t).model == OPUS


def test_all_blocked_wakes_at_earliest_reset() -> None:
    ws = parse_windows(PAYLOAD)
    t = _gate.Thresholds(session=30, weekly=97, scoped=97)
    v = _gate.pick(ws, [FABLE, OPUS], t)
    assert v.model == ""
    assert [w.kind for w in v.blockers] == ["session"]
    assert v.wake_at == datetime.datetime.fromisoformat(_S)


def test_first_eligible_in_preference_order() -> None:
    ws = [Window("session", 10.0, None), Window("weekly_scoped", 99.0, None, "Fable")]
    assert _gate.pick(ws, [FABLE, OPUS], _gate.Thresholds()).model == OPUS
    assert _gate.pick(ws, [OPUS, FABLE], _gate.Thresholds()).model == OPUS
    assert _gate.pick(ws, [FABLE], _gate.Thresholds()).wake_at is None
