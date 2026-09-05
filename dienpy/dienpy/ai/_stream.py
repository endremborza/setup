"""Reader for `claude -p --output-format stream-json`: raw lines to a log, progress to stdout.

Event shapes: `system/init` carries the session id; `assistant` messages hold text and
tool_use blocks; the final `result` event has `is_error`, `subtype`, the reply text and
the session id again.
"""

import json
import sys
from dataclasses import dataclass
from typing import IO

_PREVIEW = 100


@dataclass(frozen=True)
class Outcome:
    session_id: str = ""
    result: str = ""
    subtype: str = ""
    is_error: bool = False
    returncode: int = 0
    turns: int = 0

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.is_error


def _one_line(text: str) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= _PREVIEW else flat[: _PREVIEW - 1] + "…"


def _tool_summary(block: dict) -> str:
    inp = block.get("input") or {}
    for key in ("command", "file_path", "pattern", "path", "query", "description"):
        if key in inp:
            return f"{block.get('name')}: {_one_line(str(inp[key]))}"
    return str(block.get("name"))


def progress(event: dict) -> str | None:
    kind = event.get("type")
    if kind == "system" and event.get("subtype") == "init":
        return f"session {event.get('session_id')} ({event.get('model')})"
    if kind == "assistant":
        parts = []
        for block in (event.get("message") or {}).get("content") or []:
            if block.get("type") == "text" and block.get("text", "").strip():
                parts.append(_one_line(block["text"]))
            elif block.get("type") == "tool_use":
                parts.append(_tool_summary(block))
        return " | ".join(parts) if parts else None
    if kind == "result":
        state = "error" if event.get("is_error") else "done"
        return f"{state} ({event.get('subtype')}) turns={event.get('num_turns')}"
    return None


def follow(stdout: IO[str], log: IO[str] | None) -> Outcome:
    outcome = Outcome()
    turns = 0
    for line in stdout:
        if log is not None:
            log.write(line)
            log.flush()
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        note = progress(event)
        if note:
            print(f"  · {note}", flush=True)
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            outcome = Outcome(session_id=str(event.get("session_id", "")))
        elif kind == "assistant":
            turns += 1
        elif kind == "result":
            outcome = Outcome(
                session_id=str(event.get("session_id") or outcome.session_id),
                result=str(event.get("result") or ""),
                subtype=str(event.get("subtype") or ""),
                is_error=bool(event.get("is_error")),
                turns=int(event.get("num_turns") or turns),
            )
    if not outcome.result and not outcome.subtype:
        print("  · stream ended without a result event", file=sys.stderr)
    return outcome
