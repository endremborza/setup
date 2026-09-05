"""stale marks: extend and rebind flag the groups they change; sanitize keeps the flag."""

from dienpy.hunks import _engine, _rebind
from dienpy.hunks._groups import sanitize
from dienpy.hunks._hunks import Hunk

HEAD = "deadbeef"


def _h(hid: str, path: str, start: int, count: int) -> Hunk:
    return Hunk(hid, path, "hunk", "", start, count)


def test_rebind_marks_edited_group_only() -> None:
    entry = {
        "head": HEAD,
        "anchors": {"a1": ["a.txt", 10, 6], "b1": ["b.txt", 5, 6]},
        "groups": [
            {"title": "g0", "message": "", "hunks": ["a1"]},
            {"title": "g1", "message": "", "hunks": ["b1"]},
        ],
    }
    live = [_h("a1e", "a.txt", 10, 7), _h("b1", "b.txt", 5, 6)]
    res = _rebind.rebind(live, entry, HEAD)
    assert res.groups[0].get("stale") is True
    assert "stale" not in res.groups[1]


def test_incremental_merge_marks_extended_group(monkeypatch) -> None:
    existing = [{"title": "g0", "message": "", "hunks": ["x"]}]
    monkeypatch.setattr(_engine, "build_incremental_prompt", lambda *a, **k: "")
    monkeypatch.setattr(
        _engine, "_call", lambda *a, **k: [{"title": "", "message": "", "hunks": ["y"], "extends": 1}]
    )
    merged = _engine.analyze_incremental("/", existing, [_h("y", "a", 1, 1)], None, None)  # type: ignore[arg-type]
    assert merged[0]["hunks"] == ["x", "y"] and merged[0]["stale"] is True
    assert "stale" not in existing[0]


def test_sanitize_keeps_stale() -> None:
    out = sanitize([{"title": "a", "message": "", "hunks": ["x"], "stale": True}], {"x"})
    assert out[0]["stale"] is True
