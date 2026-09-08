"""cache: prune drops runs covering no live hunk, entries record grouped ids only, time is stable."""

import json
from pathlib import Path

from _repo import git, make

from dienpy.hunks import _cache, _hunks
from dienpy.hunks import list as hunks_list
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
    assert _cache.last_config(root) == {
        "granularity": "normal",
        "model": "sonnet",
        "context": "bare",
    }
    entry = _cache.entry(root, CONFIG)
    assert entry and entry["ids"] == ["a"] and entry["patches"] == patches
    stamp = entry["time"]
    _cache.set_entry(root, CONFIG, hunks, patches)
    assert _cache.entry(root, CONFIG)["time"] == stamp


def test_json_listing_survives_a_prune(tmp_path: Path, capsys, monkeypatch) -> None:
    """nvim parses `list --json` stdout: prune's diagnostic must not land in it."""
    repo = make(tmp_path)
    monkeypatch.chdir(repo)
    root = str(repo)
    hunks = _hunks.parse(root)
    _cache.set_entry(
        root,
        CONFIG,
        hunks,
        [{"id": "p", "title": "t", "message": "", "hunks": [h.id for h in hunks]}],
    )
    git(repo, "checkout", "--", ".")
    for p in ("new.txt", "new_bin"):
        (repo / p).unlink()
    hunks_list.main(json=True)
    out = capsys.readouterr()
    assert json.loads(out.out)["runs"] == {}
    assert "pruned" in out.err


def test_missing_run_names_the_cached_ones(tmp_path: Path) -> None:
    root = str(tmp_path)
    other = Config("loose", "sonnet", "bare")
    assert "`hunks run` first" in str(_cache.missing(root, CONFIG))
    (tmp_path / ".git").mkdir()
    _cache.set_entry(
        root, other, [_h("a")], [{"id": "p", "title": "t", "hunks": ["a"]}]
    )
    msg = str(_cache.missing(root, CONFIG))
    assert "[loose|sonnet|bare]" in msg and "hunks use" in msg
