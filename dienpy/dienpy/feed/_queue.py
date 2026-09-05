"""A repo's prompt queue: authored metadata in each prompt's frontmatter, repo defaults in
`.cril/feed.toml`, run history in `.cril/prompts/state.toml` (machine-written), and the
eligibility rules that turn those into a verdict per prompt.
"""

import datetime
import re
import statistics
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .. import ai
from .._toml import fmt_value
from ..ai import _prompt_file
from ..claude import _gate
from ..claude.usage import Window

MODES = ("once", "repeat")
DEFAULT_PROFILES = ("fabx", "opux")
DEFAULT_HUNKS = ("opus", "normal", "explore")
DEFAULT_NEED = 35.0
DEFAULT_EVERY_H = 12.0
_COSTS_KEPT = 3
_DURATION = re.compile(r"^(\d+(?:\.\d+)?)\s*([mhd])$")
_UNIT_HOURS = {"m": 1 / 60, "h": 1.0, "d": 24.0}

UsageFn = Callable[[], list[Window]]


@dataclass(frozen=True)
class Meta:
    mode: str = "once"
    unattended: bool = False
    commit: bool = False
    profiles: tuple[str, ...] = ()
    priority: int = 3
    need: float = DEFAULT_NEED
    every_h: float | None = None


@dataclass(frozen=True)
class RepoQueue:
    root: Path
    hunks: tuple[str, ...] = DEFAULT_HUNKS
    profiles: tuple[str, ...] = DEFAULT_PROFILES
    env: str = ""
    # a wrapper's identity: its own usage windows and a shell template around `{cmd}`
    usage: UsageFn | None = None
    wrap: str = ""

    @property
    def name(self) -> str:
        return self.root.name

    @property
    def prompts(self) -> Path:
        return self.root / ".cril" / "prompts"


@dataclass(frozen=True)
class State:
    last: datetime.datetime | None = None
    outcome: str = ""
    attempts: int = 0
    costs: tuple[float, ...] = ()
    report: str = ""


@dataclass(frozen=True)
class Candidate:
    repo: RepoQueue
    path: Path
    meta: Meta
    state: State = field(default_factory=State)

    @property
    def name(self) -> str:
        return self.path.stem

    @property
    def profiles(self) -> tuple[str, ...]:
        return self.meta.profiles or self.repo.profiles

    @property
    def need(self) -> float:
        return statistics.fmean(self.state.costs) if self.state.costs else self.meta.need

    @property
    def edited_since_run(self) -> bool:
        if self.state.last is None:
            return True
        mtime = datetime.datetime.fromtimestamp(self.path.stat().st_mtime, datetime.timezone.utc)
        return mtime > self.state.last


def parse_every(value: str) -> float:
    m = _DURATION.match(value.strip())
    if not m:
        raise ValueError(f"every: expected e.g. 90m, 24h, 2d — got {value!r}")
    return float(m.group(1)) * _UNIT_HOURS[m.group(2)]


def parse_meta(raw: dict[str, str], where: Path) -> Meta:
    try:
        meta = Meta(
            mode=raw.get("mode", "once"),
            unattended=_prompt_file.as_bool(raw.get("unattended", "")),
            commit=_prompt_file.as_bool(raw.get("commit", "")),
            profiles=_prompt_file.as_list(raw.get("profiles", "")),
            priority=int(raw.get("priority", 3)),
            need=float(raw.get("need", DEFAULT_NEED)),
            every_h=parse_every(raw["every"]) if raw.get("every") else None,
        )
    except ValueError as e:
        raise SystemExit(f"{where}: {e}")
    if meta.mode not in MODES:
        raise SystemExit(f"{where}: mode must be one of {', '.join(MODES)}")
    if not 1 <= meta.priority <= 5:
        raise SystemExit(f"{where}: priority must be 1..5")
    return meta


def load_repo(root: Path) -> RepoQueue:
    path = root / ".cril" / "feed.toml"
    if not path.exists():
        return RepoQueue(root=root)
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as e:
        raise SystemExit(f"{path}: {e}")
    return RepoQueue(
        root=root,
        hunks=tuple(data.get("hunks", DEFAULT_HUNKS)),
        profiles=tuple(data.get("profiles", DEFAULT_PROFILES)),
        env=str(data.get("env", "")),
    )


def _state_path(repo: RepoQueue) -> Path:
    return repo.prompts / "state.toml"


def load_state(repo: RepoQueue) -> dict[str, State]:
    path = _state_path(repo)
    if not path.exists():
        return {}
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as e:
        raise SystemExit(f"{path}: {e}")
    out = {}
    for name, d in data.items():
        last = d.get("last")
        if isinstance(last, datetime.datetime) and last.tzinfo is None:
            last = last.replace(tzinfo=datetime.timezone.utc)
        out[name] = State(
            last=last,
            outcome=str(d.get("outcome", "")),
            attempts=int(d.get("attempts", 0)),
            costs=tuple(float(c) for c in d.get("costs", [])),
            report=str(d.get("report", "")),
        )
    return out


def save_state(repo: RepoQueue, states: dict[str, State]) -> None:
    """Write every entry whose prompt still exists; entries for deleted prompts drop out."""
    live = {p.stem for p in repo.prompts.glob("*.md")}
    lines = []
    for name in sorted(states):
        s = states[name]
        if name not in live:
            continue
        lines += [f"[{name}]"]
        if s.last:
            lines.append(f"last = {s.last.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
        lines.append(f"outcome = {fmt_value(s.outcome)}")
        lines.append(f"attempts = {s.attempts}")
        lines.append(f"costs = {fmt_value([round(c, 1) for c in s.costs])}")
        if s.report:
            lines.append(f"report = {fmt_value(s.report)}")
        lines.append("")
    _state_path(repo).write_text("\n".join(lines))


def record(state: State, *, now: datetime.datetime, outcome: str, cost: float | None, report: str) -> State:
    costs = state.costs + ((cost,) if cost is not None and cost >= 0 else ())
    return State(
        last=now, outcome=outcome, attempts=state.attempts + 1, costs=costs[-_COSTS_KEPT:], report=report
    )


def collect(repos: list[RepoQueue]) -> list[Candidate]:
    out: list[Candidate] = []
    for repo in repos:
        if not repo.prompts.is_dir():
            continue
        states = load_state(repo)
        for path in sorted(repo.prompts.glob("*.md")):
            raw, _ = _prompt_file.split(path.read_text())
            if not raw:
                continue
            out.append(Candidate(repo, path, parse_meta(raw, path), states.get(path.stem, State())))
    return out


def lifecycle(c: Candidate, now: datetime.datetime) -> str:
    """The reason a prompt is not runnable by its own history, or "" when it is."""
    if not c.meta.unattended:
        return "not unattended"
    s = c.state
    if s.outcome == "failed" and not c.edited_since_run:
        return f"failed {s.last:%m-%d %H:%M} (edit to retry)"
    if s.last is None or s.outcome != "ok":
        return ""
    every = c.meta.every_h if c.meta.every_h is not None else (DEFAULT_EVERY_H if c.meta.mode == "repeat" else None)
    if every is None:
        return "landed? (ran ok, file still here)"
    due = s.last + datetime.timedelta(hours=every)
    return "" if now >= due else f"cooldown until {due.astimezone():%a %H:%M}"


def _models(profiles: tuple[str, ...]) -> list[str]:
    out = []
    for name in profiles:
        b = ai.resolve("feed", ai.Need(), profile=name)
        out.append(b.model if isinstance(b, ai.Cli) else "")
    return out


def headroom(profiles: tuple[str, ...], need: float, ws: list[Window], t: _gate.Thresholds) -> tuple[str, str]:
    """(profile, "") when some profile fits now, else ("", reason)."""
    models = _models(profiles)
    verdict = _gate.pick(ws, models, t, need=need)
    if verdict.model:
        return profiles[models.index(verdict.model)], ""
    wake = verdict.wake_at
    when = f"; resets {wake.astimezone():%a %H:%M}" if wake else ""
    session = next((w for w in verdict.blockers if w.kind == "session"), None)
    if session is not None:
        return "", f"needs {need:.0f} / have {max(0.0, t.session - session.percent):.0f}{when}"
    return "", "blocked by " + ", ".join(f"{w.label} {w.percent:.0f}%" for w in verdict.blockers) + when


def order(cands: list[Candidate], last_run: dict[str, datetime.datetime]) -> list[Candidate]:
    """Priority first, then the repo that has waited longest, then name."""
    floor = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
    return sorted(cands, key=lambda c: (c.meta.priority, last_run.get(c.repo.name, floor), c.name))
