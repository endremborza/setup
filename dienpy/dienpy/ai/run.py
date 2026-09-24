"""Start a claude session on a profile: pipe a prompt (file, --raw, stdin) or go interactive."""

import dataclasses
import sys
from pathlib import Path
from typing import Annotated

from protocli import FILES

from . import _profiles, _prompt_file
from ._backend import Cli, Need, resolve
from ._transport import launch
from .models import Target

_UNATTENDED_TIMEOUT = 10800

_UNATTENDED_RULES = (
    "You are running unattended inside an automated queue: no human is present, and nothing you print is read until later.",
    "- There is no one to ask and AskUserQuestion is unavailable. For every decision take the option you would have recommended, and record the choice where the task says decisions go (the plan section, or your final report).",
    "- Never stop early to wait for input. If you are truly blocked, write what blocked you and what you tried into your final report, then stop.",
    "- End with a final report: what landed, what was measured, what remains and why.",
)
_NO_COMMIT = "- Never commit, push or amend: the human reviews and commits from the patches you leave behind."


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
        return _prompt_file.split(path.read_text(errors="replace"))[1]
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return None


def backend(
    profile: str = "",
    *,
    tool: str = "run",
    timeout: int | None = None,
    auto: bool = False,
) -> Cli:
    """The cli backend for `profile` (empty: the tool's binding, then the default);
    an explicit `timeout` overrides the profile's, which overrides the unattended default."""
    resolved = resolve(tool, Need(timeout=_UNATTENDED_TIMEOUT), profile=profile)
    if not isinstance(resolved, Cli):
        name = profile or _profiles.for_tool(tool)
        raise SystemExit(f"profile '{name}' is not a claude cli profile")
    if timeout is not None:
        resolved = dataclasses.replace(resolved, timeout=timeout)
    if auto:
        resolved = dataclasses.replace(resolved, permission_mode="auto")
    return resolved


def main(
    profile: Target | None = None,
    file: Annotated[str, FILES] = "",
    *,
    interactive: bool = False,
    safe: bool = False,
    raw: str = "",
    auto: bool = False,
    unattended: bool = False,
    commit: bool = False,
    timeout: int | None = None,
) -> None:
    """Run a prompt through claude non-interactively (default) or open a session.

    The profile defaults to the `[tool] run` binding, then `default`; a name that is no
    profile is passed to claude as its model. Non-interactive runs force
    --permission-mode auto and time out after --timeout seconds (default: the profile's,
    else 3 h); --auto opts an interactive session into auto mode too. --safe starts
    claude with every customization (CLAUDE.md, skills) off. --unattended appends the
    queue rules (no questions, take the recommended default, never commit, final
    report); --commit lifts the never-commit rule from them.
    """
    if commit and not unattended:
        raise SystemExit("--commit adjusts the --unattended rules; pass both")
    outcome = launch(
        backend(profile or "", timeout=timeout, auto=auto),
        read_prompt(file, raw),
        interactive=interactive,
        safe=safe,
        system=unattended_suffix(commit) if unattended else "",
    )
    if outcome.is_error and outcome.result:
        print(outcome.result, file=sys.stderr)
    if not outcome.ok:
        raise SystemExit(outcome.returncode or 1)
