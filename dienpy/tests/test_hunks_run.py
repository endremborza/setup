"""run: a scoped --force re-partitions the subtree and keeps out-of-scope patches; placements merge by patch id."""

from pathlib import Path

import pytest
from _repo import make, seed
from dienpy.hunks import _cache, _config, _engine, run

CONFIG = _config.Config("normal", "sonnet", "bare")


def test_scoped_force_keeps_other_patches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = make(tmp_path)
    monkeypatch.chdir(repo)
    seed(repo)
    monkeypatch.setattr(_engine, "backend_for", lambda config, auth: None)
    monkeypatch.setattr(
        _engine,
        "partition",
        lambda root, hunks, config, backend: [
            {"title": "all of a", "message": "", "hunks": [h.id for h in hunks]}
        ],
    )
    run.main("normal", "sonnet", "bare", force=True, path="a.txt")
    entry = _cache.entry(str(repo), CONFIG)
    assert entry and [p["title"] for p in entry["patches"]] == ["b edit", "all of a"]
    assert len(entry["patches"][1]["hunks"]) == 2


def test_merge_placement_by_id() -> None:
    snapshot = [
        {"id": "x", "title": "X", "hunks": ["1"]},
        {"id": "y", "title": "Y", "hunks": ["2"]},
    ]
    fresh = [{"id": "y", "title": "Y", "hunks": ["2", "1"]}]  # moved meanwhile
    groups = [
        {"extends": 1, "title": "X", "message": "", "hunks": ["3"]},
        {"extends": 2, "title": "Y", "message": "", "hunks": ["4"]},
        {"title": "Z", "message": "", "hunks": ["5"]},
    ]
    out = _engine.merge_placement(fresh, groups, snapshot)
    assert [p["title"] for p in out] == ["Y", "X", "Z"]
    assert out[0]["hunks"] == ["2", "1", "4"] and out[0]["stale"]
    assert out[1]["hunks"] == ["3"] and "extends" not in out[1]
    assert fresh[0]["hunks"] == ["2", "1"]  # input untouched
