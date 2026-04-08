"""dienpy ai commit — commit message tools."""

import argparse
import re
import subprocess
from datetime import datetime
from pathlib import Path

from . import _cache, _client

_DEFAULT_MODEL = "local"
_DEFAULT_FILES = ["README.md", "AGENTS.md"]
_BATCH_CHAR_LIMIT = 1500
_DEFAULT_MAX_DIFF_CHARS = 0  # 0 = no truncation

_SUGGEST_SYSTEM = """\
Generate a git commit message for the staged changes shown below.

Rules:
- Output ONLY the commit message — no preamble, explanation, or quotes
- Simple single-concern change: one subject line (≤72 chars)
- Complex or multi-concern change: one summary line + blank line + `- ` bullet points
- Use conventional commit tags (feat:, fix:, refactor:, etc.) ONLY if the repository \
context (AGENTS.md, README.md) shows this convention is already in use
- Be specific: describe what changed and why, not just "updated X"
"""

_IMPROVE_SYSTEM = """\
Improve the git commit message for the changes shown below.

Rules:
- Output ONLY the improved commit message — no preamble, explanation, or quotes
- Keep the same structural format (single line, or summary + bullets)
- Make it more specific if the original was vague — describe what changed and why
- Use conventional commit tags ONLY if the repository context shows this convention
"""

_DESCRIBE_BATCH_SYSTEM = """\
Describe a series of git commits as a cohesive summary.

Rules:
- Output ONLY the summary — no preamble, explanation, or quotes
- 1-3 sentences or bullet points covering the key changes across the series
- Focus on what changed and why, not on individual commit hashes
"""


def _run_git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _context_files(files: list[str]) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for name in files:
        path = Path(name)
        if path.exists():
            text = path.read_text()
            if text not in seen:
                seen.add(text)
                parts.append(f'<file name="{name}">\n{text}\n</file>')
    return "\n\n".join(parts)


def _commit_entry(hash: str, max_diff_chars: int = 0) -> str:
    msg = _run_git("log", "-1", "--format=%B", hash).strip()
    diff = _run_git("show", hash)
    if max_diff_chars and len(diff) > max_diff_chars:
        diff = diff[:max_diff_chars] + "\n... [truncated]"
    return (
        f'<commit hash="{hash}">\n'
        f"<message>\n{msg}\n</message>\n"
        f"<diff>\n{diff}\n</diff>\n"
        f"</commit>"
    )


def _make_batches(entries: list[str]) -> list[list[str]]:
    batches: list[list[str]] = []
    current: list[str] = []
    current_len = 0
    for entry in entries:
        entry_len = len(entry)
        if current and current_len + entry_len > _BATCH_CHAR_LIMIT:
            batches.append(current)
            current = [entry]
            current_len = entry_len
        else:
            current.append(entry)
            current_len += entry_len
    if current:
        batches.append(current)
    return batches


def _parse_since(since: str) -> str:
    m = re.fullmatch(r"(\d+)([Dh])", since, re.IGNORECASE)
    if not m:
        raise SystemExit(f"Invalid --since format '{since}'. Use e.g. 7D or 50h.")
    n, unit = int(m.group(1)), m.group(2).lower()
    return f"{n} days ago" if unit == "d" else f"{n} hours ago"


def _add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--model", default=_DEFAULT_MODEL, help="Model to use.")
    p.add_argument(
        "--effort",
        choices=list(_client.EFFORT_BUDGETS),
        default="none",
        help="Extended thinking effort (default: none).",
    )
    p.add_argument(
        "--files",
        nargs="*",
        default=_DEFAULT_FILES,
        metavar="FILE",
        help=f"Context files to include (default: {' '.join(_DEFAULT_FILES)}).",
    )


def _add_diff_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--max-diff-chars",
        type=int,
        default=_DEFAULT_MAX_DIFF_CHARS,
        metavar="N",
        help="Truncate each commit diff to N chars (0 = no limit). Useful for local models.",
    )


def _cmd_suggest(args: argparse.Namespace) -> None:
    diff = _run_git("diff", "--staged")
    if not diff.strip():
        raise SystemExit("No staged changes.")
    file_ctx = _context_files(args.files)
    staged = f"<staged_changes>\n{diff}\n</staged_changes>"
    context = f"{file_ctx}\n\n{staged}" if file_ctx else staged
    print(
        _client.send(
            args.model, _SUGGEST_SYSTEM, context, temperature=0.2, effort=args.effort
        )
    )


def _cmd_improve(args: argparse.Namespace) -> None:
    file_ctx = _context_files(args.files)
    entry = _commit_entry(args.hash, getattr(args, "max_diff_chars", 0))
    context = f"{file_ctx}\n\n{entry}" if file_ctx else entry
    print(
        _client.send(
            args.model, _IMPROVE_SYSTEM, context, temperature=0.2, effort=args.effort
        )
    )


def _cmd_describe_batch(args: argparse.Namespace) -> None:
    file_ctx = _context_files(args.files)
    entries = "\n\n".join(_commit_entry(h, args.max_diff_chars) for h in args.hashes)
    context = f"{file_ctx}\n\n{entries}" if file_ctx else entries
    print(
        _client.send(
            args.model,
            _DESCRIBE_BATCH_SYSTEM,
            context,
            max_tokens=1024,
            temperature=0.3,
            effort=args.effort,
        )
    )


def _cmd_history(args: argparse.Namespace) -> None:
    since = _parse_since(args.since)
    hashes = _run_git("log", f"--since={since}", "--format=%H").split()
    if not hashes:
        raise SystemExit(f"No commits found since {args.since}.")
    hashes.reverse()  # oldest first

    file_ctx = _context_files(args.files)
    entries = [_commit_entry(h, args.max_diff_chars) for h in hashes]
    batches = _make_batches(entries)

    descriptions: list[str] = []
    for batch in batches:
        combined = "\n\n".join(batch)
        context = f"{file_ctx}\n\n{combined}" if file_ctx else combined
        desc = _client.send(
            args.model,
            _DESCRIBE_BATCH_SYSTEM,
            context,
            max_tokens=1024,
            temperature=0.3,
            effort=args.effort,
        )
        print(desc)
        descriptions.append(desc)

    header = f"## {args.since} history — {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    body = "\n\n---\n\n".join(descriptions)
    output = f"{header}\n\n{body}"

    history_path = Path("history.md")
    if history_path.exists():
        history_path.write_text(history_path.read_text() + "\n\n" + output + "\n")
    else:
        history_path.write_text(output + "\n")

    print(output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Commit message tools.")
    sub = parser.add_subparsers(dest="cmd")

    p_suggest = sub.add_parser(
        "suggest", help="Suggest a commit message for staged changes."
    )
    _add_common_args(p_suggest)

    p_improve = sub.add_parser("improve", help="Improve a past commit's message.")
    p_improve.add_argument("hash", help="Commit hash.")
    _add_common_args(p_improve)
    _add_diff_args(p_improve)

    p_batch = sub.add_parser("describe-batch", help="Describe a series of commits.")
    p_batch.add_argument("hashes", nargs="+", metavar="HASH")
    _add_common_args(p_batch)
    _add_diff_args(p_batch)

    p_hist = sub.add_parser("history", help="Summarize commit history over a timespan.")
    p_hist.add_argument(
        "--since", required=True, metavar="TIMESPAN", help="e.g. 7D or 50h"
    )
    _add_common_args(p_hist)
    _add_diff_args(p_hist)

    args = parser.parse_args()

    if args.cmd is None:
        # backward-compat: no subcommand → suggest with defaults
        p_suggest.parse_args([], namespace=args)
        _cmd_suggest(args)
    elif args.cmd == "suggest":
        _cmd_suggest(args)
    elif args.cmd == "improve":
        _cmd_improve(args)
    elif args.cmd == "describe-batch":
        _cmd_describe_batch(args)
    elif args.cmd == "history":
        _cmd_history(args)


def get_completions(args: list[str]) -> list[str]:
    subcommands = ["suggest", "improve", "describe-batch", "history"]
    if not args or args[0] not in subcommands:
        return subcommands
    subcmd = args[0]
    rest = args[1:]
    if rest and rest[-1] == "--model":
        return _cache.all_models()
    if rest and rest[-1] == "--effort":
        return list(_client.EFFORT_BUDGETS)
    opts = ["--model", "--effort", "--files"]
    if subcmd in ("improve", "describe-batch", "history"):
        opts.append("--max-diff-chars")
    if subcmd == "history":
        opts.append("--since")
    return opts
