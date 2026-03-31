"""dienpy ai commit — suggest a commit message for staged changes."""

import argparse
import subprocess
from pathlib import Path

from . import _cache, _client

_DEFAULT_MODEL = "gemini-flash-latest"
_DEFAULT_FILES = ["README.md", "AGENTS.md", "CLAUDE.md"]

_SYSTEM_PROMPT = """\
Generate a git commit message for the staged changes shown below.

Rules:
- Output ONLY the commit message — no preamble, explanation, or quotes
- Simple single-concern change: one subject line (≤72 chars)
- Complex or multi-concern change: one summary line + blank line + `- ` bullet points
- Use conventional commit tags (feat:, fix:, refactor:, etc.) ONLY if the repository \
context (CLAUDE.md, AGENTS.md, README.md) shows this convention is already in use
- Be specific: describe what changed and why, not just "updated X"
"""


def _build_context(files: list[str]) -> str:
    parts: list[str] = []
    for name in files:
        path = Path(name)
        if path.exists():
            parts.append(f'<file name="{name}">\n{path.read_text()}\n</file>')

    diff = subprocess.run(["git", "diff", "--staged"], capture_output=True, text=True)
    if diff.returncode != 0:
        raise SystemExit(f"git diff --staged failed: {diff.stderr.strip()}")
    if not diff.stdout.strip():
        raise SystemExit("No staged changes.")

    parts.append(f"<staged_changes>\n{diff.stdout}\n</staged_changes>")
    return "\n\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Suggest a commit message for staged changes."
    )
    parser.add_argument("--model", default=_DEFAULT_MODEL, help="Model to use.")
    parser.add_argument(
        "--effort",
        choices=list(_client.EFFORT_BUDGETS),
        default="none",
        help="Extended thinking effort (default: none).",
    )
    parser.add_argument(
        "--files",
        nargs="*",
        default=_DEFAULT_FILES,
        metavar="FILE",
        help=f"Context files to include (default: {' '.join(_DEFAULT_FILES)}).",
    )
    args = parser.parse_args()

    context = _build_context(args.files)
    print(_client.send(args.model, _SYSTEM_PROMPT, context, effort=args.effort))


def get_completions(args: list[str]) -> list[str]:
    if args and args[-1] == "--model":
        return _cache.all_models()
    if args and args[-1] == "--effort":
        return list(_client.EFFORT_BUDGETS)
    return ["--model", "--effort", "--files"]
