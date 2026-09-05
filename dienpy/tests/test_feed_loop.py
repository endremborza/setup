"""feed loop: a command job runs with the gate's profile in its env, logs a row, releases the lock."""

import datetime
from pathlib import Path

from dienpy.claude import _gate
from dienpy.claude.usage import Window
from dienpy.feed import Job, RepoQueue, Settings, run_jobs
from dienpy.feed._loop import choose
from dienpy.feed._queue import Candidate, Meta

WS = [Window("session", 1.0, None), Window("weekly_scoped", 50.0, None, "Fable")]


def test_job_names() -> None:
    assert Job(prompt=Path("/x/debt-bugs.md")).name == "debt-bugs"
    assert Job(cmd="make experiment HINT='x'").name == "make-experiment-HINT-x"


def test_cmd_job_gets_profile_env_and_row(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    marker = tmp_path / "seen"
    repo = RepoQueue(root=tmp_path, hunks=())
    s = Settings(thresholds=_gate.Thresholds(scoped=10), log_base=tmp_path / "log")
    job = Job(cmd=f'echo "$FEED_PROFILE $FEED_MODEL" > {marker}', profiles=("fabx", "opux"))
    run_jobs(repo, [job], s, usage=lambda: WS)
    assert marker.read_text().strip() == "opux claude-opus-5"
    rows = (tmp_path / "log" / tmp_path.name / "runs.md").read_text().splitlines()
    assert "| echo-FEED" in rows[-1] and "| opux | ok | hunks skipped" in rows[-1]
    assert not (tmp_path / ".git" / "feed.lock").exists()


def test_cmd_job_times_out(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    repo = RepoQueue(root=tmp_path, hunks=())
    s = Settings(log_base=tmp_path / "log", timeout=1)
    run_jobs(repo, [Job(cmd="sleep 30", profiles=("opux",))], s, usage=lambda: WS)
    rows = (tmp_path / "log" / tmp_path.name / "runs.md").read_text().splitlines()
    assert "| failed (-9)" in rows[-1]


def test_choose_fetches_each_usage_source_once(tmp_path: Path) -> None:
    calls = []

    def usage() -> list[Window]:
        calls.append(1)
        return WS

    def cand(name: str) -> Candidate:
        root = tmp_path / name
        (root / ".git").mkdir(parents=True)
        path = root / f"{name}.md"
        path.write_text("x")
        return Candidate(RepoQueue(root), path, Meta(unattended=True, profiles=("opux",)))

    now = datetime.datetime.now(datetime.timezone.utc)
    choice = choose([cand("a"), cand("b")], Settings(), usage, now, fetch=lambda fn: fn())
    assert len(calls) == 1
    assert choice.picked is not None and choice.profile == "opux"
    assert [w for _, w in choice.verdicts] == ["runnable → opux  ← next", "runnable → opux"]
