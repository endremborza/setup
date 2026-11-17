"""Open a detached tmux session with one interactive claude window per prompt file."""

import os
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from protocli import FILES, Complete

from . import _account, _prompt_file, run
from ._account import AccountName

# the interpreter running this moac, so every window runs the same install; -P keeps a
# window's cwd off sys.path
MOAC = (sys.executable, "-P", "-m", "moac")
# every session moac opens carries it, so `moac attach` lists and completes only those
PREFIX = "moac-"
# tmux reads these as the separators of a target (session:window.pane)
_TARGET_SEPARATORS = re.compile(r"[.:]")


@dataclass(frozen=True)
class Window:
    name: str
    cwd: Path
    argv: tuple[str, ...]


def window(file: Path, *, account: str = "", auto: bool = False) -> Window:
    """The window `file` opens, its frontmatter read as `main` describes."""
    path = file.resolve()
    if not path.is_file():
        raise SystemExit(f"prompt file not found: {file}")
    meta, _ = _prompt_file.split(path.read_text(errors="replace"))
    raw = meta.get("cwd")
    cwd = Path(os.path.expandvars(raw)).expanduser().resolve() if raw else Path.cwd()
    if not cwd.is_dir():
        raise SystemExit(f"{file}: cwd {cwd} is not a directory")
    profile = run.backend(meta.get("profile", ""), account=account).profile
    argv = [*MOAC, "run", profile, str(path), "--interactive"]
    if account:
        argv += ["--account", account]
    if auto:
        argv.append("--auto")
    return Window(meta.get("name") or path.stem, cwd, tuple(argv))


def session_name(files: Sequence[Path], session: str = "") -> str:
    """`session`, else the name of the files' common parent directory, made a tmux target
    under `PREFIX`."""
    parent = Path(os.path.commonpath([f.resolve().parent for f in files]))
    name = session or parent.name
    if not name:
        raise SystemExit("the files share no named parent directory; pass --session")
    return PREFIX + _TARGET_SEPARATORS.sub("_", name.removeprefix(PREFIX))


def sessions() -> list[str]:
    """The live sessions moac opened, `PREFIX` stripped; none when no tmux server runs."""
    if shutil.which("tmux") is None:
        return []
    listed = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}"],
        capture_output=True,
        text=True,
    )
    if listed.returncode != 0:
        return []
    return [
        line.removeprefix(PREFIX)
        for line in listed.stdout.splitlines()
        if line.startswith(PREFIX)
    ]


Session = Annotated[str, Complete(sessions)]


def commands(session: str, windows: Sequence[Window]) -> list[list[str]]:
    """The tmux calls that open `session` with `windows` in order, the first one current."""
    first, *rest = windows

    def opened(w: Window) -> list[str]:
        return ["-n", w.name, "-c", str(w.cwd), "--", *w.argv]

    return [
        ["tmux", "new-session", "-d", "-s", session, *opened(first)],
        *(["tmux", "new-window", "-d", "-t", f"={session}:", *opened(w)] for w in rest),
    ]


def main(
    *files: Annotated[str, FILES],
    session: str = "",
    account: AccountName = "",
    auto: bool = False,
) -> None:
    """Open a detached tmux session with one interactive claude window per prompt file.

    A file's frontmatter sets its window: `name` (default the file stem), `cwd` (`~` and
    env vars expanded, default the current directory) and `profile` (default what
    `moac run` picks without one); its body is the session's first message. The tmux
    session is --session, else the name of the files' common parent directory, under
    `PREFIX`; `moac attach` gets there. --account
    (default: MOAC_ACCOUNT) and --auto pass through to every window's `moac run`.
    """
    if not files:
        raise SystemExit("moac tmux needs at least one prompt file")
    if shutil.which("tmux") is None:
        raise SystemExit("tmux not found on PATH")
    paths = [Path(f) for f in files]
    name = session_name(paths, session)
    exists = subprocess.run(
        ["tmux", "has-session", "-t", f"={name}"], capture_output=True
    )
    if exists.returncode == 0:
        raise SystemExit(f"tmux session '{name}' already exists")
    account = account or os.environ.get(_account.ENV_VAR, "")
    built = [window(p, account=account, auto=auto) for p in paths]
    for cmd in commands(name, built):
        subprocess.run(cmd, check=True)
    print(f"moac attach {name.removeprefix(PREFIX)}")
