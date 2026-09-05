"""The unattended loop: gate on usage, run one job, close the regroup cache, record, repeat.

Two front doors share one job runner: `run` takes an explicit list of jobs for the
current repo; `schedule` picks the best eligible prompt across repo queues each cycle.
One job at a time; a repo is locked (`.git/feed.lock`) while its job runs. A job is a
prompt file (a claude session with the unattended suffix, streamed to a log, resumed
once after a usage limit) or a shell command (run as is, the chosen profile in
FEED_PROFILE/FEED_MODEL); a repo with a wrapper runs its prompts as commands inside it.
"""

import datetime
import os
import re
import shlex
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .. import ai
from ..ai import _prompt_file
from ..ai import run as _airun
from ..claude import _gate
from ..claude.usage import Window, windows
from . import _log, _queue
from ._queue import Candidate, RepoQueue, UsageFn

_RESUME_PROMPT = (
    "The session was interrupted by a usage limit and has been resumed. "
    "Continue where you left off: finish the task and its closing steps, then give the final report."
)
_LIMIT_HINT = re.compile(r"usage limit|limit reached", re.IGNORECASE)
_MIN_SLEEP = 30
_DRIFT = {0: "clean", 1: "DRIFTED", 2: "no run"}


@dataclass(frozen=True)
class Settings:
    thresholds: _gate.Thresholds = _gate.Thresholds()
    log_base: Path = Path(".")  # per-repo subdirectory underneath
    poll: int = 600
    timeout: int = 10800
    repeat: bool = False  # explicit mode: cycle the job list, `poll` seconds between cycles
    once: bool = False  # scheduler: stop after one job


@dataclass(frozen=True)
class Job:
    prompt: Path | None = None
    cmd: str = ""
    profiles: tuple[str, ...] = _queue.DEFAULT_PROFILES
    need: float = _queue.DEFAULT_NEED
    commit: bool = False

    @property
    def name(self) -> str:
        if self.prompt is not None:
            return self.prompt.stem
        return re.sub(r"[^A-Za-z0-9]+", "-", self.cmd).strip("-")[:40]

    def __str__(self) -> str:
        return str(self.prompt) if self.prompt is not None else self.cmd


@dataclass(frozen=True)
class Result:
    outcome: ai.Outcome
    cost: float | None  # session-% consumed, None when a reset fell inside the run
    drift: str
    report: Path | None
    limited: bool  # the failure was a usage limit: a full applicable window, or the cli said so


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _say(msg: str) -> None:
    print(f"[{datetime.datetime.now():%H:%M:%S}] {msg}", flush=True)


def _local(when: datetime.datetime | None) -> str:
    return when.astimezone().strftime("%a %H:%M") if when else "?"


def _describe(ws: list[Window]) -> str:
    return "  ".join(f"{w.label} {w.percent:.0f}%" for w in ws)


def _session(ws: list[Window]) -> Window | None:
    return next((w for w in ws if w.kind == "session"), None)


def _sleep_until(wake: datetime.datetime | None, poll: int) -> None:
    delay = float(poll)
    if wake:
        delay = min(delay, (wake - _now()).total_seconds() + _MIN_SLEEP)
    time.sleep(max(_MIN_SLEEP, delay))


def _usage(fn: UsageFn, poll: int) -> list[Window]:
    while True:
        try:
            return fn()
        except Exception as e:
            _say(f"usage check failed ({type(e).__name__}: {e}); retrying in {poll}s")
            time.sleep(poll)


def _hunks(root: Path, *args: str) -> int:
    return subprocess.run([sys.executable, "-m", "dienpy", "hunks", *args], cwd=root).returncode


def _close(root: Path, dims: tuple[str, ...], describe: bool) -> str:
    """Bring the regroup cache up to date for `dims`; returns the final drift state."""
    if not dims:
        return "skipped"
    rc = _hunks(root, "drift", *dims)
    if rc == 2:
        _hunks(root, "run", *dims)
    elif rc == 1 and _hunks(root, "run", "--extend", *dims):
        _hunks(root, "run", *dims)
    if describe:
        _hunks(root, "messages", *dims)
    return _DRIFT.get(_hunks(root, "drift", *dims), "error")


def _limit_hit(outcome: ai.Outcome, usage: UsageFn, model: str) -> Window | None:
    if outcome.ok:
        return None
    try:
        ws = usage()
    except Exception:
        return None
    full = [w for w in ws if _gate.applies(w, model) and w.percent >= 100]
    if full:
        return full[0]
    if _LIMIT_HINT.search(outcome.result):
        return _session(ws)
    return None


def _run_prompt(
    root: Path, job: Job, s: Settings, profile: str, backend: ai.Cli, usage: UsageFn, log: _log.RunLog
) -> ai.Outcome:
    assert job.prompt is not None
    system = _airun.unattended_suffix(commit=job.commit)
    body = _prompt_file.split(job.prompt.read_text())[1]
    with log.stream() as stream:
        outcome = ai.launch(backend, body, system=system, log=stream, cwd=str(root))
    hit = _limit_hit(outcome, usage, backend.model)
    if hit and outcome.session_id:
        _say(f"usage limit hit ({hit.label} {hit.percent:.0f}%); resuming after {_local(hit.resets_at)}")
        _sleep_until(hit.resets_at, s.poll)
        while _gate.blockers(_usage(usage, s.poll), backend.model, s.thresholds):
            _sleep_until(None, s.poll)
        with log.stream("-resumed") as stream:
            outcome = ai.launch(
                backend, _RESUME_PROMPT, system=system, resume=outcome.session_id, log=stream, cwd=str(root)
            )
    return outcome


def _run_cmd(root: Path, cmd: str, profile: str, backend: ai.Cli, log: _log.RunLog, timeout: int) -> ai.Outcome:
    env = {**os.environ, "FEED_PROFILE": profile, "FEED_MODEL": backend.model}
    with log.console() as out:
        proc = subprocess.Popen(
            cmd, shell=True, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        assert proc.stdout is not None
        timed_out = threading.Event()

        def _expire() -> None:
            # flag before kill, so wait() cannot return with the flag still unset
            timed_out.set()
            proc.kill()

        timer = threading.Timer(timeout, _expire)
        timer.start()
        try:
            for line in proc.stdout:
                sys.stdout.write(line)
                out.write(line)
            rc = proc.wait()
        except BaseException:
            proc.kill()
            proc.wait()
            raise
        finally:
            timer.cancel()
    if timed_out.is_set() and rc != 0:
        return ai.Outcome(returncode=rc, is_error=True, result=f"timed out after {timeout}s")
    return ai.Outcome(returncode=rc, is_error=rc != 0)


def _wrapped_prompt(job: Job, profile: str, wrap: str, timeout: int) -> str:
    assert job.prompt is not None
    inner = (
        f"dienpy ai run --unattended{' --commit' if job.commit else ''} --timeout {timeout} "
        f"{shlex.quote(profile)} {shlex.quote(str(job.prompt))}"
    )
    return wrap.format(cmd=shlex.quote(inner))


# extra time a wrapper gets past the inner session's own --timeout: the inner timer must
# fire first — killing the wrapper (the docker client) would orphan the container
_WRAP_GRACE = 300


def run_job(repo: RepoQueue, job: Job, s: Settings, profile: str, usage: UsageFn, before: list[Window]) -> Result:
    backend = _airun.backend(profile, tool="feed", timeout=s.timeout)
    _say(f"▶ {job.name} on {profile} ({backend.model})  [{_describe(before)}]")
    _close(repo.root, repo.hunks, describe=False)
    log = _log.RunLog(s.log_base / repo.name, job.name)
    started = time.monotonic()
    if job.prompt is not None and not repo.wrap:
        outcome = _run_prompt(repo.root, job, s, profile, backend, usage, log)
    elif job.prompt is not None:
        wrapped = _wrapped_prompt(job, profile, repo.wrap, s.timeout)
        outcome = _run_cmd(repo.root, wrapped, profile, backend, log, s.timeout + _WRAP_GRACE)
    else:
        outcome = _run_cmd(repo.root, job.cmd, profile, backend, log, s.timeout)
    minutes = (time.monotonic() - started) / 60
    drift = _close(repo.root, repo.hunks, describe=True)
    state = "ok" if outcome.ok else f"failed ({outcome.subtype or outcome.returncode})"
    report = log.report(outcome, f"{job.name} — {profile} — {state}") if outcome.result.strip() else None
    try:
        after = usage()
    except Exception:
        after = []
    b, a = _session(before), _session(after)
    cost = a.percent - b.percent if a and b and a.resets_at == b.resets_at else None
    limited = not outcome.ok and (
        any(w.percent >= 100 for w in after if _gate.applies(w, backend.model))
        or bool(_LIMIT_HINT.search(outcome.result))
    )
    _say(f"■ {job.name}: {state}, {outcome.turns} turns, {minutes:.0f} min, hunks {drift}  [{_describe(after) or '?'}]")
    _log.append_run(
        s.log_base / repo.name,
        f"| {_log.stamp()} | {job.name} | {profile} | {state} | hunks {drift} "
        f"| {outcome.turns} | {minutes:.0f} | {f'{cost:.0f}' if cost is not None else ''} | {_describe(after) or '?'} "
        f"| {report.name if report else ''} |",
    )
    return Result(outcome, cost, drift, report, limited)


class _Lock:
    def __init__(self, root: Path):
        self.path = root / ".git" / "feed.lock"

    def held(self) -> bool:
        if not self.path.exists():
            return False
        try:
            os.kill(int(self.path.read_text().strip() or 0), 0)
        except (ProcessLookupError, ValueError):
            return False
        return True

    def acquire(self) -> bool:
        if self.held():
            return False
        self.path.write_text(str(os.getpid()))
        return True

    def release(self) -> None:
        self.path.unlink(missing_ok=True)

    def __enter__(self) -> "_Lock":
        if not self.acquire():
            raise SystemExit(f"another feed loop is running on {self.path.parent.parent}")
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()


def run(repo: RepoQueue, jobs: list[Job], s: Settings, usage: UsageFn = windows) -> None:
    """Explicit queue on one repo, in order; `s.repeat` cycles it."""
    with _Lock(repo.root):
        cycle = 0
        while True:
            cycle += 1
            for i, job in enumerate(jobs, 1):
                _say(f"job {i}/{len(jobs)}{f' (cycle {cycle})' if s.repeat else ''}: {job}")
                while True:
                    ws = _usage(usage, s.poll)
                    profile, why = _queue.headroom(job.profiles, job.need, ws, s.thresholds)
                    if profile:
                        break
                    _say(f"{why}; next look in {s.poll // 60} min")
                    _sleep_until(None, s.poll)
                run_job(repo, job, s, profile, usage, ws)
            if not s.repeat:
                break
            _say(f"cycle {cycle} done; next in {s.poll // 60} min")
            time.sleep(s.poll)
        _say(f"queue done: {len(jobs)} job(s); logs in {s.log_base / repo.name}")


@dataclass(frozen=True)
class Choice:
    picked: Candidate | None
    profile: str
    windows: list[Window]
    verdicts: list[tuple[Candidate, str]]  # every candidate in pick order, with why it does or does not run


Fetch = Callable[[UsageFn], list[Window]]


def strict(fn: UsageFn) -> list[Window]:
    """One attempt; a listing must not sit in the scheduler's retry loop."""
    try:
        return fn()
    except Exception as e:
        raise SystemExit(f"usage fetch failed ({type(e).__name__}: {e}); use --offline for lifecycle only")


def choose(
    cands: list[Candidate], s: Settings, host: UsageFn, now: datetime.datetime, fetch: Fetch | None = None
) -> Choice:
    """Judge every candidate; the first runnable one in priority order is the pick."""
    fetch = fetch or (lambda fn: _usage(fn, s.poll))
    cache: dict[int, list[Window]] = {}
    floor = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
    last_run: dict[str, datetime.datetime] = {}
    for c in cands:
        if c.state.last and c.state.last > last_run.get(c.repo.name, floor):
            last_run[c.repo.name] = c.state.last
    picked: Candidate | None = None
    profile, ws = "", []
    verdicts: list[tuple[Candidate, str]] = []
    for c in _queue.order(cands, last_run):
        why = _queue.lifecycle(c, now)
        if not why and _Lock(c.repo.root).held():
            why = "repo busy"
        if not why:
            fn = c.repo.usage or host
            if id(fn) not in cache:
                cache[id(fn)] = fetch(fn)
            judged = cache[id(fn)]
            fit, why = _queue.headroom(c.profiles, c.need, judged, s.thresholds)
            if fit:
                why = f"runnable → {fit}"
                if picked is None:
                    picked, profile, ws = c, fit, judged
                    why += "  ← next"
        verdicts.append((c, why))
    return Choice(picked, profile, ws, verdicts)


def schedule(repos: list[RepoQueue], s: Settings, usage: UsageFn = windows) -> None:
    """Pick and run the best eligible prompt across the queues until stopped (or once)."""
    while True:
        now = _now()
        choice = choose(_queue.collect(repos), s, usage, now)
        cand, profile, ws = choice.picked, choice.profile, choice.windows
        if cand is None:
            blocked = [w for _, w in choice.verdicts if w.startswith(("needs", "blocked"))]
            _say(f"nothing runnable ({len(choice.verdicts)} waiting{': ' + blocked[0] if blocked else ''}); next look in {s.poll // 60} min")
            _sleep_until(None, s.poll)
            continue
        job = Job(prompt=cand.path, profiles=cand.profiles, need=cand.need, commit=cand.meta.commit)
        _say(f"picked {cand.repo.name}/{cand.name} (priority {cand.meta.priority}, need {cand.need:.0f})")
        lock = _Lock(cand.repo.root)
        if not lock.acquire():
            _say(f"{cand.repo.name} became busy; picking again")
            continue
        try:
            res = run_job(cand.repo, job, s, profile, cand.repo.usage or usage, ws)
        finally:
            lock.release()
        states = _queue.load_state(cand.repo)
        outcome = "ok" if res.outcome.ok else ("limit" if res.limited else "failed")
        report = str(res.report.relative_to(s.log_base)) if res.report else ""
        states[cand.name] = _queue.record(cand.state, now=_now(), outcome=outcome, cost=res.cost, report=report)
        _queue.save_state(cand.repo, states)
        if s.once:
            return
