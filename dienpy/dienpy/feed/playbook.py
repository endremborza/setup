"""Run a playbook: a repo's prompts in a fixed order, then a guide to what the run left behind."""

import datetime
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from protocli import FILES

from .. import _git
from .._out import table
from ..ai import _prompt_file, launch
from ..ai import run as _airun
from ..claude import _gate
from ..claude.usage import windows
from ..constants import LOGS_DIR
from . import _log, _queue
from ._loop import Job, Result, Settings, _peek, label, prompt_job, strict, work

# an `until` value -> the usage window whose reset ends the run
UNTIL = {"weekly-reset": "weekly_all"}
_GUIDE_NEED = 10.0
_GUIDE_DECISIONS = 8
_GUIDE_SYSTEM = f"""A playbook run has just ended: it finished, hit its deadline, or its owner stopped it. The owner reviews its changes as patches; the guide lists only what they must decide, so the review starts from a few answers instead of a read.
- Read the playbook for intent, then the job reports and the diff. Open what you need; edit nothing.
- At most {_GUIDE_DECISIONS} decisions, most consequential first: a change a job made on a judgment the owner may reverse, a claim no job verified, an action proposed outside the run's reach, a question a job could not settle. Leave out what the diff shows plainly and anything the owner cannot act on.
- Each decision is one numbered line: the question, its options as a), b), ... with the recommended one first, and the file:line it concerns.
- Then one line per job that failed, was interrupted or did not run, with why.
- No reading order, no summary of the changes, no run facts (they are appended below the guide). Markdown read raw in nvim; your final message is the guide itself."""


@dataclass(frozen=True)
class Playbook:
    path: Path
    jobs: tuple[str, ...]  # prompt names under the repo's `.cril/prompts/`
    until: str
    body: str


def load(path: Path) -> Playbook:
    """The playbook file; a leading shebang line (to run the file itself) is skipped."""
    text = path.read_text()
    if text.startswith("#!"):
        text = text.partition("\n")[2]
    raw, body = _prompt_file.split(text)
    jobs = _prompt_file.as_list(raw.get("jobs", ""))
    if not jobs:
        raise SystemExit(f"{path}: frontmatter names no jobs")
    until = raw.get("until", "")
    if until and until not in UNTIL:
        raise SystemExit(f"{path}: until must be one of {', '.join(UNTIL)}")
    return Playbook(_logical(path), jobs, until, body)


def _logical(path: Path) -> Path:
    """`path` made absolute against the shell's `$PWD`, which keeps the `.cril` link a `cd`
    went through (`os.getcwd()` is the physical PKM path), with `..` folded away."""
    pwd = os.environ.get("PWD", "")
    base = (
        pwd if os.path.isdir(pwd) and os.path.samefile(pwd, os.curdir) else os.getcwd()
    )
    return Path(os.path.normpath(os.path.join(base, path)))


def repo_root(path: Path) -> Path:
    """The repo whose `.cril/` holds the playbook, judged on its logical path (`.cril` links
    into the PKM); the repo around the cwd when the path has no `.cril`."""
    cril = next((p for p in path.parents if p.name == ".cril"), None)
    return cril.parent if cril else Path(_git.find_root())


def deadline(until: str) -> datetime.datetime | None:
    if not until:
        return None
    kind = UNTIL[until]
    w = next((w for w in strict(windows) if w.kind == kind), None)
    if w is None or w.resets_at is None:
        raise SystemExit(f"until {until}: no {kind} window with a reset time")
    return w.resets_at


def status(root: Path) -> dict[str, str]:
    """`git status` as path -> XY code, untracked files one by one, a rename as its two sides."""
    out = _git.Repo(root).raw("status", "--porcelain", "-z", "-uall", "--no-renames")
    return {t[3:]: t[:2] for t in out.split("\0") if t}


def touched(root: Path, before: dict[str, str], since: float) -> list[str]:
    """Paths whose status changed during the run, or which were written during it."""

    def fresh(rel: str) -> bool:
        p = root / rel
        return p.exists() and p.stat().st_mtime >= since

    after = status(root)
    return sorted(p for p, code in after.items() if before.get(p) != code or fresh(p))


def facts(
    book: Playbook,
    root: Path,
    jobs: list[Job],
    done: list[tuple[Job, Result]],
    changed: list[str],
    logs: list[Path],
) -> str:
    rows = [
        f"| {j.name} | {label(r.outcome)} | {r.outcome.turns} | {'' if r.cost is None else f'{r.cost:.0f}'} | {r.report or ''} |"
        for j, r in done
    ]
    lines = [
        f"Playbook: {book.path}",
        f"Repo: {root}",
        "",
        "| job | outcome | turns | session % | report |",
        "| --- | --- | --- | --- | --- |",
        *rows,
    ]
    rest = jobs[len(done) :]
    if rest:
        lines += [
            "",
            f"Not run or interrupted: {', '.join(j.name for j in rest)}",
            "Run the rest: `dienpy feed run "
            + " ".join(str(j.prompt) for j in rest)
            + "`",
        ]
    lines += ["", "Repo files touched:", *(f"- {p}" for p in changed or ["(none)"])]
    lines += ["", "Run logs:", *(f"- {p}" for p in logs or ["(none)"])]
    return "\n".join(lines)


def guide(book: Playbook, root: Path, profiles: tuple[str, ...], known: str) -> str:
    """The guide session's final message; "" when it failed."""
    fit, _ = _queue.headroom(profiles, _GUIDE_NEED, _peek(windows), _gate.Thresholds())
    backend = _airun.backend(fit or profiles[0], tool="feed")
    prompt = f"# Playbook\n\n{book.body}\n\n# This run\n\n{known}\n"
    log = _log.RunLog(LOGS_DIR / "feed" / root.name, f"guide-{book.path.stem}")
    with log.stream() as stream:
        outcome = launch(
            backend, prompt, system=_GUIDE_SYSTEM, log=stream, cwd=str(root)
        )
    return outcome.result.strip() if outcome.ok else ""


def main(playbook: Annotated[str, FILES], *, dry_run: bool = False) -> None:
    """Run the playbook's jobs (`jobs:` names prompts in the repo's `.cril/prompts/`) in
    order, gated like `feed run`, starting none after its `until:`. When the jobs end, the
    deadline passes or you press Ctrl-C, it prints what ran and writes a guide to the
    results beside the run logs. A playbook whose first line is
    `#!/usr/bin/env -S dienpy feed playbook` runs as `./<file>`.
    """
    book = load(Path(playbook))
    root = repo_root(book.path)
    repo = _queue.load_repo(root)
    jobs = [prompt_job(repo, repo.prompts / f"{name}.md") for name in book.jobs]
    settings = Settings(log_base=LOGS_DIR / "feed", until=deadline(book.until))
    if dry_run:
        rows = [
            ("repo", root),
            (
                "until",
                f"{settings.until.astimezone():%a %H:%M}" if settings.until else "-",
            ),
        ]
        rows += [
            (f"job {i}", f"{j.name}  profiles={','.join(j.profiles)} need={j.need:.0f}")
            for i, j in enumerate(jobs, 1)
        ]
        print(table(rows))
        return
    started = time.time()
    before = status(root)
    done: list[tuple[Job, Result]] = []
    try:
        for pair in work(repo, jobs, settings):
            done.append(pair)
    except KeyboardInterrupt:
        print("\nstopped; writing the guide (Ctrl-C again skips it)", flush=True)
    log_dir = settings.log_base / repo.name
    logs = sorted(
        p
        for p in log_dir.glob("*")
        if p.name != "runs.md" and p.stat().st_mtime >= started
    )
    known = facts(book, root, jobs, done, touched(root, before, started), logs)
    out = _log.RunLog(log_dir, f"playbook-{book.path.stem}")
    path = Path(f"{out.base}.md")
    path.write_text(f"# {book.path.stem}\n\n{known}\n")
    print(f"\n{known}\n", flush=True)
    try:
        text = guide(book, root, repo.profiles, known)
    except KeyboardInterrupt:
        text = ""
    if text:
        path.write_text(f"# {book.path.stem}\n\n{text}\n\n## Run facts\n\n{known}\n")
        print(f"\n{text}\n")
    print(f"guide: {path}")
