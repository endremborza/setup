"""rebind: edited hunks keep their group via HEAD-side anchors; merges are flagged, not lost."""

from dienpy.hunks import _rebind
from dienpy.hunks._hunks import Hunk

HEAD = "deadbeef"

# a1, a2 in a.txt (different groups), b1 in b.txt
ENTRY = {
    "ids": ["a1", "a2", "b1"],
    "head": HEAD,
    "anchors": {"a1": ["a.txt", 10, 6], "a2": ["a.txt", 40, 3], "b1": ["b.txt", 5, 6]},
    "groups": [
        {"title": "g0", "message": "", "hunks": ["a1", "b1"]},
        {"title": "g1", "message": "", "hunks": ["a2"]},
    ],
}


def _h(hid: str, path: str, start: int, count: int) -> Hunk:
    return Hunk(hid, path, "hunk", "", start, count)


def _same(hid: str) -> Hunk:
    return _h(hid, *ENTRY["anchors"][hid])


def test_edit_keeps_group_and_position() -> None:
    live = [_h("a1e", "a.txt", 10, 7), _same("a2"), _same("b1")]
    res = _rebind.rebind(live, ENTRY, HEAD)
    assert res.rebound == {"a1e": "a1"}
    assert res.new == [] and res.gone == [] and res.ambiguous == []
    assert res.groups[0]["hunks"] == ["a1e", "b1"]
    assert res.groups[1]["hunks"] == ["a2"]
    assert ENTRY["groups"][0]["hunks"] == ["a1", "b1"]  # input untouched


def test_merged_hunk_takes_largest_overlap_and_is_flagged() -> None:
    live = [_h("m", "a.txt", 8, 40), _same("b1")]
    res = _rebind.rebind(live, ENTRY, HEAD)
    assert res.rebound == {"m": "a1"}  # 6 lines of overlap vs a2's 3
    assert res.ambiguous == ["m"]
    assert res.groups[0]["hunks"] == ["m", "b1"]
    assert res.groups[0]["ambiguous"] == ["m"]
    assert res.groups[1]["hunks"] == []


def test_split_hunk_carries_both_halves() -> None:
    live = [
        _h("s1", "a.txt", 10, 3),
        _h("s2", "a.txt", 14, 2),
        _same("a2"),
        _same("b1"),
    ]
    res = _rebind.rebind(live, ENTRY, HEAD)
    assert res.rebound == {"s1": "a1", "s2": "a1"}
    assert res.groups[0]["hunks"] == ["s1", "s2", "b1"]


def test_undone_hunk_is_dropped_group_survives() -> None:
    live = [_same("a2"), _same("b1")]
    res = _rebind.rebind(live, ENTRY, HEAD)
    assert res.gone == ["a1"] and res.rebound == {}
    assert res.groups[0]["hunks"] == ["b1"]


def test_unrelated_change_stays_new() -> None:
    live = [_same("a1"), _same("a2"), _same("b1"), _h("n", "c.txt", 1, 4)]
    res = _rebind.rebind(live, ENTRY, HEAD)
    assert res.new == ["n"] and res.rebound == {}


def test_moved_head_disables_positional_matching() -> None:
    live = [_h("a1e", "a.txt", 10, 7), _same("a2"), _same("b1")]
    res = _rebind.rebind(live, ENTRY, "0ther")
    assert res.new == ["a1e"] and res.rebound == {}
    assert res.gone == ["a1"]


def test_new_file_anchors_on_the_path() -> None:
    entry = {
        "ids": ["u1"],
        "head": HEAD,
        "anchors": {"u1": ["new.txt", 0, 0]},
        "groups": [
            {
                "title": "g",
                "message": "",
                "hunks": ["u1"],
                "mixed": [{"hunk": "u1", "note": "n"}],
            }
        ],
    }
    res = _rebind.rebind([_h("u2", "new.txt", 0, 0)], entry, HEAD)
    assert res.rebound == {"u2": "u1"}
    assert res.groups[0]["mixed"] == [{"hunk": "u2", "note": "n"}]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("REBIND PASS")
