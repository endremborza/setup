"""_sanitize: prune dead hunk ids, drop emptied groups, merge same-titled groups."""

from dienpy.hunks.run import _sanitize


def test_prunes_dead_ids_and_empty_groups() -> None:
    groups = [
        {"title": "a", "message": "", "hunks": ["x", "dead1"], "committed": "abc123"},
        {"title": "b", "message": "", "hunks": ["dead2"]},
    ]
    out = _sanitize(groups, {"x"})
    assert out == [{"title": "a", "message": "", "hunks": ["x"], "committed": "abc123"}]
    assert groups[0]["hunks"] == ["x", "dead1"]  # input untouched


def test_merges_same_titled_groups() -> None:
    groups = [
        {"title": "a", "message": "first", "hunks": ["x", "dead"]},
        {"title": "b", "message": "", "hunks": ["y"]},
        {"title": "a", "message": "dup", "hunks": ["z", "w"]},
    ]
    out = _sanitize(groups, {"x", "y", "z", "w"})
    assert out == [
        {"title": "a", "message": "first", "hunks": ["x", "z", "w"]},
        {"title": "b", "message": "", "hunks": ["y"]},
    ]


def test_mixed_pruned_and_merged() -> None:
    groups = [
        {"title": "a", "message": "", "hunks": ["x"], "mixed": [{"hunk": "x", "note": "n1"}, {"hunk": "dead", "note": "n2"}]},
        {"title": "a", "message": "", "hunks": ["y"], "mixed": [{"hunk": "y", "note": "n3"}]},
        {"title": "b", "message": "", "hunks": ["z"], "mixed": [{"hunk": "dead", "note": "n4"}]},
    ]
    out = _sanitize(groups, {"x", "y", "z"})
    assert out == [
        {"title": "a", "message": "", "hunks": ["x", "y"], "mixed": [{"hunk": "x", "note": "n1"}, {"hunk": "y", "note": "n3"}]},
        {"title": "b", "message": "", "hunks": ["z"]},
    ]


if __name__ == "__main__":
    test_prunes_dead_ids_and_empty_groups()
    test_merges_same_titled_groups()
    test_mixed_pruned_and_merged()
    print("SANITIZE PASS")
