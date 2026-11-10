"""Rewrite a past commit's message with AI (prints; does not amend)."""

import moac

from dienpy._git import find_root

from . import _prompt

_SYSTEM = """\
Improve the git commit message for the commit shown below.

Rules:
- Output ONLY the improved commit message — no preamble, explanation, or quotes
- Keep the structural format (single subject line, or subject + blank line + body)
- Make it more specific if the original was vague — what changed and why
- Match the style of the recent commit subjects in the context
"""


def main(
    hash: str,
    *,
    profile: moac.ProfileName = "",
    effort: moac.Effort = "",
    max_diff_chars: int = 0,
) -> None:
    root = find_root()
    backend = moac.resolve("commit", moac.Need(effort=effort), profile=profile)
    user = (
        f"{_prompt.message_context(root)}\n\n"
        f"{_prompt.commit_entry(root, hash, max_diff_chars)}"
    )
    print(moac.send(backend, _SYSTEM, user, temperature=0.2, cwd=root).value)
