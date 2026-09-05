"""Start a claude session on a profile: pipe a prompt (file, --raw, stdin) or go interactive."""

import dataclasses
import sys
from pathlib import Path
from typing import Annotated

from protocli import FILES

from . import _profiles, _prompt_file
from ._backend import Cli, Need, resolve
from ._profiles import ProfileName
from ._transport import launch

_UNATTENDED_TIMEOUT = 10800

_UNATTENDED_RULES = (
    "You are running unattended inside an automated queue: no human is present, and nothing you print is read until later.",
    "- There is no one to ask and AskUserQuestion is unavailable. For every decision take the option you would have recommended, and record the choice where the task says decisions go (the plan section, or your final report).",
    "- Never stop early to wait for input. If you are truly blocked, write what blocked you and what you tried into your final report, then stop.",
    "- End with a final report: what landed, what was measured, what remains and why.",
)
_NO_COMMIT = "- Never commit, push or amend: the human reviews and commits from the change groups you leave behind."


def unattended_suffix(commit: bool = False) -> str:
    rules = list(_UNATTENDED_RULES)
    if not commit:
        rules.insert(3, _NO_COMMIT)
    return "\n".join(rules)


def read_prompt(file: str, raw: str) -> str | None:
    """--raw text, else the file's body (frontmatter stripped), else piped stdin; None on a terminal."""
    if raw:
        return raw
    if file:
        path = Path(file)
        if not path.is_file():
            raise SystemExit(f"prompt file not found: {file}")
        return _prompt_file.split(path.read_text())[1]
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return None


def backend(profile: str, *, tool: str = "run", timeout: int = _UNATTENDED_TIMEOUT, auto: bool = False) -> Cli:
    resolved = resolve(tool, Need(timeout=timeout), profile=profile or _profiles.default_name())
    if not isinstance(resolved, Cli):
        raise SystemExit(f"profile '{profile}' is not a claude cli profile")
    if auto:
        return dataclasses.replace(resolved, permission_mode="auto")
    return resolved


def main(
    profile: ProfileName,
    file: Annotated[str, FILES] = "",
    *,
    interactive: bool = False,
    safe: bool = False,
    raw: str = "",
    auto: bool = False,
    unattended: bool = False,
    commit: bool = False,
    timeout: int = _UNATTENDED_TIMEOUT,
) -> None:
    """Run a prompt through claude non-interactively (default) or open a session.

    Non-interactive runs force --permission-mode auto and time out after --timeout
    seconds; --auto opts an interactive session into auto mode too. --safe starts
    claude with every customization (CLAUDE.md, skills) off. --unattended appends the
    queue rules (no questions, take the recommended default, never commit, final
    report); --commit lifts the never-commit rule from them.
    """
    if commit and not unattended:
        raise SystemExit("--commit adjusts the --unattended rules; pass both")
    outcome = launch(
        backend(profile, timeout=timeout, auto=auto),
        read_prompt(file, raw),
        interactive=interactive,
        safe=safe,
        system=unattended_suffix(commit) if unattended else "",
    )
    if outcome.returncode:
        raise SystemExit(outcome.returncode)
