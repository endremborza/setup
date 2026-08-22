"""Rewrite a past commit's message with AI (prints; does not amend)."""

from typing import Literal

from .. import ai
from . import _hunks, _prompt

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
    profile: ai.ProfileName = "",
    effort: Literal["none", "low", "medium", "high"] = "none",
    max_diff_chars: int = 0,
) -> None:
    root = _hunks.git_root()
    backend = ai.resolve("commit", ai.Need(effort=effort), profile=profile)
    user = (
        f"{_prompt.message_context(root)}\n\n"
        f"{_prompt.commit_entry(root, hash, max_diff_chars)}"
    )
    print(ai.send(backend, _SYSTEM, user, temperature=0.2, cwd=root))
