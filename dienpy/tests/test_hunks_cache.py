"""cache: prune drops runs covering no live hunk, entries record grouped ids only, time is stable."""

import json
from pathlib import Path

from dienpy.hunks import _cache
from dienpy.hunks._config import Config
from dienpy.hunks._hunks import Hunk, under

CONFIG = Config("normal", "sonnet", "bare")


def _h(hid: str, path: str = "a.txt") -> Hunk:
    return Hunk(hid, path, "hunk", "", "", 1)


def _seed(root: Path, entries: dict) -> None:
    (root / ".git").mkdir()
    data = {"version": _cache.VERSION, "analyses": entries, "last": None}
    (root / ".git" / "regroup-cache.json").write_text(json.dumps(data))


def test_prune_keeps_partial_drops_dead(tmp_path: Path) -> None:
    _seed(
        tmp_path,
        {
            "normal|sonnet|bare": {"ids": ["a", "b"], "patches": [], "time": 1},
            "loose|sonnet|bare": {"ids": ["x"], "patches": [], "time": 2},
        },
    )
    _cache.prune(str(tmp_path), [_h("b"), _h("c")])
    data = _cache.load(str(tmp_path))
    assert data and list(data["analyses"]) == ["normal|sonnet|bare"]
    _cache.prune(str(tmp_path), [])
    data = _cache.load(str(tmp_path))
    assert data and data["analyses"] == {}


def test_old_schema_reads_as_empty(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "regroup-cache.json").write_text(
        '{"version": 3, "analyses": {}}'
    )
    assert _cache.load(str(tmp_path)) is None


def test_scoped_entry_records_grouped_ids(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    root = str(tmp_path)
    hunks = [_h("a", "data/x.md"), _h("b", "notes/y.md")]
    assert [h.id for h in under(hunks, "data")] == ["a"]
    assert under(hunks, "dat") == []
    patches = [{"id": "p", "title": "t", "message": "", "hunks": ["a"]}]
    _cache.set_entry(root, CONFIG, hunks, patches)
    entry = _cache.entry(root, CONFIG)
    assert entry and entry["ids"] == ["a"] and entry["patches"] == patches
    stamp = entry["time"]
    _cache.set_entry(root, CONFIG, hunks, patches)
    assert _cache.entry(root, CONFIG)["time"] == stamp
