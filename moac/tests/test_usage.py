"""Usage windows parsed from the oauth payload's `limits`."""

import datetime

from moac.usage import parse_windows

_T = "2026-09-02T11:59:59+00:00"
_S = "2026-09-01T23:29:59+00:00"

PAYLOAD = {
    "five_hour": {"utilization": 33.0, "resets_at": _S},
    "seven_day": {"utilization": 4.0, "resets_at": _T},
    "limits": [
        {
            "kind": "session",
            "group": "session",
            "percent": 33,
            "resets_at": _S,
            "scope": None,
        },
        {
            "kind": "weekly_all",
            "group": "weekly",
            "percent": 4,
            "resets_at": _T,
            "scope": None,
        },
        {
            "kind": "weekly_scoped",
            "group": "weekly",
            "percent": 6,
            "resets_at": _T,
            "scope": {"model": {"id": None, "display_name": "Fable"}, "surface": None},
        },
    ],
}


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
