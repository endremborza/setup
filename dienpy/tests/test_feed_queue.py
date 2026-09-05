"""prompt queue: frontmatter, repo defaults, state round-trip, lifecycle verdicts, headroom, pick order."""

import datetime
import os
from pathlib import Path

import pytest

from dienpy.ai import _prompt_file
from dienpy.claude import _gate
from dienpy.claude.usage import Window
from dienpy.feed import _queue
from dienpy.feed._queue import Candidate, Meta, RepoQueue, State

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 9, 3, 12, 0, tzinfo=UTC)


def test_frontmatter_split_and_absence() -> None:
    meta, body = _prompt_file.split("---\nmode: repeat  # weekly\nprofiles: fabx, opux\ntarget: plans/a.md §B: c\n---\n\nDo it.\n")
    assert meta == {"mode": "repeat", "profiles": "fabx, opux", "target": "plans/a.md §B: c"}
    assert body == "Do it.\n"
    assert _prompt_file.split("no fence\n---\n") == ({}, "no fence\n---\n")
    assert _prompt_file.split("---\nunterminated: yes\n") == ({}, "---\nunterminated: yes\n")


def test_parse_meta_defaults_and_validation(tmp_path: Path) -> None:
    m = _queue.parse_meta({"unattended": "true", "every": "90m", "priority": "1"}, tmp_path)
    assert m == Meta(unattended=True, every_h=1.5, priority=1)
    with pytest.raises(SystemExit):
        _queue.parse_meta({"mode": "sometimes"}, tmp_path)
    with pytest.raises(SystemExit):
        _queue.parse_meta({"every": "soon"}, tmp_path)


def _repo(tmp_path: Path, feed_toml: str | None = None) -> RepoQueue:
    (tmp_path / ".cril" / "prompts").mkdir(parents=True)
    if feed_toml is not None:
        (tmp_path / ".cril" / "feed.toml").write_text(feed_toml)
    return _queue.load_repo(tmp_path)


def test_repo_defaults_and_feed_toml(tmp_path: Path) -> None:
    assert _repo(tmp_path).hunks == _queue.DEFAULT_HUNKS
    repo = _repo(tmp_path / "b", 'hunks = []\nprofiles = ["opux"]\nenv = "hedonic"\n')
    assert repo.hunks == () and repo.profiles == ("opux",) and repo.env == "hedonic"


def test_collect_skips_files_without_frontmatter(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo.prompts / "a.md").write_text("---\nunattended: true\n---\nA\n")
    (repo.prompts / "README.md").write_text("# nothing\n")
    assert [c.name for c in _queue.collect([repo])] == ["a"]


def test_state_round_trip_prunes_deleted_prompts(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo.prompts / "keep.md").write_text("---\nunattended: true\n---\n")
    states = {
        "keep": State(last=NOW, outcome="ok", attempts=2, costs=(30.0, 35.5), report="feed/r/x.md"),
        "gone": State(last=NOW, outcome="failed", attempts=1),
    }
    _queue.save_state(repo, states)
    loaded = _queue.load_state(repo)
    assert list(loaded) == ["keep"]
    assert loaded["keep"] == states["keep"]


def test_record_keeps_last_three_costs() -> None:
    s = State(costs=(1.0, 2.0, 3.0), attempts=3)
    s = _queue.record(s, now=NOW, outcome="ok", cost=4.0, report="")
    assert s.costs == (2.0, 3.0, 4.0) and s.attempts == 4 and s.outcome == "ok"
    assert _queue.record(s, now=NOW, outcome="limit", cost=None, report="").costs == (2.0, 3.0, 4.0)


def _cand(tmp_path: Path, meta: Meta, state: State = State(), name: str = "p") -> Candidate:
    tmp_path.mkdir(exist_ok=True)
    path = tmp_path / f"{name}.md"
    path.write_text("x")
    return Candidate(RepoQueue(tmp_path), path, meta, state)


def test_lifecycle_verdicts(tmp_path: Path) -> None:
    ago = NOW - datetime.timedelta(hours=2)
    assert _queue.lifecycle(_cand(tmp_path, Meta()), NOW) == "not unattended"
    assert _queue.lifecycle(_cand(tmp_path, Meta(unattended=True)), NOW) == ""
    once_ok = _cand(tmp_path, Meta(unattended=True), State(last=ago, outcome="ok"))
    assert _queue.lifecycle(once_ok, NOW).startswith("landed?")
    rep = Meta(unattended=True, mode="repeat", every_h=1)
    assert _queue.lifecycle(_cand(tmp_path, rep, State(last=ago, outcome="ok")), NOW) == ""
    rep6 = Meta(unattended=True, mode="repeat", every_h=6)
    assert _queue.lifecycle(_cand(tmp_path, rep6, State(last=ago, outcome="ok")), NOW).startswith("cooldown")
    failed = _cand(tmp_path, Meta(unattended=True), State(last=NOW, outcome="failed"))
    os.utime(failed.path, times=(ago.timestamp(), ago.timestamp()))
    assert _queue.lifecycle(failed, NOW).startswith("failed")
    edited = _cand(tmp_path, Meta(unattended=True), State(last=ago - datetime.timedelta(days=400), outcome="failed"))
    assert _queue.lifecycle(edited, NOW) == ""


def test_headroom_uses_need_against_session(tmp_path: Path) -> None:
    ws = [Window("session", 70.0, None), Window("weekly_all", 10.0, None), Window("weekly_scoped", 20.0, None, "Fable")]
    t = _gate.Thresholds()
    assert _queue.headroom(("fabx", "opux"), 20, ws, t) == ("fabx", "")
    assert _queue.headroom(("fabx", "opux"), 35, ws, t) == ("", "needs 35 / have 27")
    measured = _cand(tmp_path, Meta(unattended=True, need=35, profiles=("fabx",)), State(costs=(10.0, 12.0)))
    assert measured.need == 11.0 and _queue.headroom(measured.profiles, measured.need, ws, t)[0] == "fabx"


def test_order_priority_then_starved_repo(tmp_path: Path) -> None:
    a = _cand(tmp_path / "a", Meta(unattended=True, priority=3), name="z")
    b = _cand(tmp_path / "b", Meta(unattended=True, priority=3), name="y")
    c = _cand(tmp_path / "c", Meta(unattended=True, priority=1), name="x")
    last = {"a": NOW, "b": NOW - datetime.timedelta(days=1)}
    assert [x.name for x in _queue.order([a, b, c], last)] == ["x", "y", "z"]
