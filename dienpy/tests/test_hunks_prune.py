"""prune: zero-coverage analyses are dropped, id or anchor overlap survives, empty diff clears all."""

import json
from pathlib import Path

from dienpy.hunks import _cache
from dienpy.hunks._hunks import Hunk

HEAD = "deadbeef"


def _h(hid: str, path: str = "a.txt", start: int = 10, count: int = 6) -> Hunk:
    return Hunk(hid, path, "hunk", "", start, count)


def _seed(root: Path, entries: dict) -> None:
    (root / ".git").mkdir()
    data = {"version": _cache.VERSION, "analyses": entries, "last": None}
    (root / ".git" / "regroup-cache.json").write_text(json.dumps(data))


def test_drops_zero_coverage_keeps_partial(tmp_path: Path) -> None:
    _seed(
        tmp_path,
        {
            "normal|sonnet|bare": {"ids": ["a", "b"], "groups": [], "time": 1},
            "loose|sonnet|bare": {"ids": ["x"], "groups": [], "time": 2},
        },
    )
    _cache.prune(str(tmp_path), [_h("b"), _h("c")], HEAD)
    data = _cache.load(str(tmp_path))
    assert data is not None
    assert list(data["analyses"]) == ["normal|sonnet|bare"]


def test_anchor_overlap_survives_full_id_turnover(tmp_path: Path) -> None:
    """Every hunk edited: no id in common, but the anchors still describe the diff."""
    _seed(
        tmp_path,
        {
            "normal|sonnet|bare": {
                "ids": ["old"],
                "groups": [],
                "time": 1,
                "head": HEAD,
                "anchors": {"old": ["a.txt", 8, 5]},
            },
            "loose|sonnet|bare": {
                "ids": ["far"],
                "groups": [],
                "time": 2,
                "head": HEAD,
                "anchors": {"far": ["a.txt", 90, 4]},
            },
            "granular|sonnet|bare": {
                "ids": ["moved"],
                "groups": [],
                "time": 3,
                "head": "0ther",
                "anchors": {"moved": ["a.txt", 8, 5]},
            },
        },
    )
    _cache.prune(str(tmp_path), [_h("new")], HEAD)
    data = _cache.load(str(tmp_path))
    assert data is not None
    assert list(data["analyses"]) == ["normal|sonnet|bare"]


def test_empty_live_drops_all(tmp_path: Path) -> None:
    _seed(tmp_path, {"normal|sonnet|bare": {"ids": ["a"], "groups": [], "time": 1}})
    _cache.prune(str(tmp_path), [], HEAD)
    data = _cache.load(str(tmp_path))
    assert data is not None
    assert data["analyses"] == {}


def test_no_cache_is_noop(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    _cache.prune(str(tmp_path), [_h("a")], HEAD)
    assert _cache.load(str(tmp_path)) is None


if __name__ == "__main__":
    import tempfile

    for fn in (
        test_drops_zero_coverage_keeps_partial,
        test_anchor_overlap_survives_full_id_turnover,
        test_empty_live_drops_all,
        test_no_cache_is_noop,
    ):
        with tempfile.TemporaryDirectory() as d:
            fn(Path(d))
    print("PRUNE PASS")
