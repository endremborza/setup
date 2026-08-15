"""prune: zero-coverage analyses are dropped, partial overlap survives, empty diff clears all."""

import json
from pathlib import Path

from dienpy.hunks import _cache


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
    _cache.prune(str(tmp_path), {"b", "c"})
    data = _cache.load(str(tmp_path))
    assert data is not None
    assert list(data["analyses"]) == ["normal|sonnet|bare"]


def test_empty_live_drops_all(tmp_path: Path) -> None:
    _seed(tmp_path, {"normal|sonnet|bare": {"ids": ["a"], "groups": [], "time": 1}})
    _cache.prune(str(tmp_path), set())
    data = _cache.load(str(tmp_path))
    assert data is not None
    assert data["analyses"] == {}


def test_no_cache_is_noop(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    _cache.prune(str(tmp_path), {"a"})
    assert _cache.load(str(tmp_path)) is None


if __name__ == "__main__":
    import tempfile

    for fn in (test_drops_zero_coverage_keeps_partial, test_empty_live_drops_all, test_no_cache_is_noop):
        with tempfile.TemporaryDirectory() as d:
            fn(Path(d))
    print("PRUNE PASS")
