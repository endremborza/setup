"""feed loop: a command job runs with the gate's profile in its env, logs a row, holds the repo lock only while running."""

import datetime
import time
from pathlib import Path

from dienpy.ai import _profiles
from dienpy.claude import _gate
from dienpy.claude.usage import Window
from dienpy.feed import Job, RepoQueue, Settings, run_jobs
from dienpy.feed._loop import _cost, _Lock, choose
from dienpy.feed._queue import Candidate, Meta
from test_ai_launch import fake_claude

WS = [Window("session", 1.0, None), Window("weekly_scoped", 50.0, None, "Fable")]
UTC = datetime.timezone.utc


def test_job_names() -> None:
    assert Job(prompt=Path("/x/debt-bugs.md")).name == "debt-bugs"
    assert Job(cmd="make experiment HINT='x'").name == "make-experiment-HINT-x"


def test_cmd_job_gets_profile_env_and_row(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    marker = tmp_path / "seen"
    repo = RepoQueue(root=tmp_path, hunks=())
    s = Settings(thresholds=_gate.Thresholds(scoped=10), log_base=tmp_path / "log")
    job = Job(
        cmd=f'echo "$FEED_PROFILE $FEED_MODEL" > {marker}', profiles=("fabx", "opux")
    )
    run_jobs(repo, [job], s, usage=lambda: WS)
    assert marker.read_text().strip() == f"opux {_profiles.OPUS}"
    rows = (tmp_path / "log" / tmp_path.name / "runs.md").read_text().splitlines()
    assert "| echo-FEED" in rows[-1] and "| opux | ok | hunks skipped" in rows[-1]
    assert _Lock(tmp_path).held() is False


def test_cmd_job_times_out_and_takes_its_children_along(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    repo = RepoQueue(root=tmp_path, hunks=())
    s = Settings(log_base=tmp_path / "log", timeout=1)
    started = time.monotonic()
    run_jobs(
        repo, [Job(cmd="sleep 30; echo late", profiles=("opux",))], s, usage=lambda: WS
    )
    assert time.monotonic() - started < 5
    rows = (tmp_path / "log" / tmp_path.name / "runs.md").read_text().splitlines()
    assert "| failed (timeout)" in rows[-1]


_STREAM = (
    "cat >/dev/null\n"
    'echo \'{"type":"system","subtype":"init","session_id":"s9","model":"m"}\'\n'
    'echo \'{"type":"assistant","message":{"content":[{"type":"text","text":"working"}]}}\'\n'
    'echo \'{"type":"result","subtype":"success","is_error":false,"result":"all done","num_turns":1,"session_id":"s9"}\''
)


def test_prompt_job_streams_to_a_log_and_reports(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "bin").mkdir()
    fake_claude(tmp_path / "bin", monkeypatch, _STREAM)
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    prompt = root / "task.md"
    prompt.write_text("---\nunattended: true\n---\nDo it.\n")
    repo = RepoQueue(root=root, hunks=())
    s = Settings(log_base=tmp_path / "log", timeout=5)
    run_jobs(repo, [Job(prompt=prompt, profiles=("opux",))], s, usage=lambda: WS)
    logs = tmp_path / "log" / "repo"
    assert [p.suffix for p in sorted(logs.iterdir())] == [".jsonl", ".md", ".md"]
    report = next(p for p in logs.glob("*-task.md"))
    assert report.read_text().endswith("all done\n")
    assert "| task | opux | ok | hunks skipped | 1 |" in (logs / "runs.md").read_text()


def test_lock_is_exclusive_and_survives_no_holder(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "feed.lock").write_text("")
    assert _Lock(tmp_path).held() is False
    first = _Lock(tmp_path)
    assert first.acquire() and _Lock(tmp_path).held() and not _Lock(tmp_path).acquire()
    first.release()
    assert _Lock(tmp_path).held() is False


def test_cost_needs_the_same_session_window() -> None:
    t = datetime.datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
    same = t + datetime.timedelta(seconds=5)
    assert _cost(Window("session", 10.0, t), Window("session", 42.0, same)) == 32.0
    assert _cost(Window("session", 0.0, None), Window("session", 30.0, t)) == 30.0
    assert (
        _cost(
            Window("session", 80.0, t),
            Window("session", 5.0, t + datetime.timedelta(hours=5)),
        )
        is None
    )
    assert _cost(None, Window("session", 5.0, t)) is None


def _cand(tmp_path: Path, name: str) -> Candidate:
    root = tmp_path / name
    (root / ".git").mkdir(parents=True)
    path = root / f"{name}.md"
    path.write_text("x")
    return Candidate(RepoQueue(root), path, Meta(unattended=True, profiles=("opux",)))


def test_choose_fetches_each_usage_source_once(tmp_path: Path) -> None:
    calls = []

    def usage() -> list[Window]:
        calls.append(1)
        return WS

    now = datetime.datetime.now(UTC)
    choice = choose(
        [_cand(tmp_path, "a"), _cand(tmp_path, "b")],
        Settings(),
        usage,
        now,
        fetch=lambda fn: fn(),
    )
    assert len(calls) == 1
    assert choice.picked is not None and choice.profile == "opux"
    assert [w for _, w in choice.verdicts] == [
        "runnable → opux  ← next",
        "runnable → opux",
    ]
    choose(
        [_cand(tmp_path, "c")],
        Settings(),
        usage,
        now,
        fetch=lambda fn: fn(),
        known={id(usage): WS},
    )
    assert len(calls) == 1
