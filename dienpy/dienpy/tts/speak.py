"""Speak text piped via stdin."""

from __future__ import annotations

import asyncio
import sys

from ._core import (
    ALL_VOICES,
    DEFAULT_VOICE,
    load_kokoro,
    server_is_running,
    server_send,
    speak_async,
    to_plain,
)


def get_completions(args: list[str]) -> list[str]:
    if args and args[-1] == "--voice":
        return ALL_VOICES
    return ["--voice", "--speed", "--no-markdown"]


def main(
    *, voice: str = DEFAULT_VOICE, speed: float = 1.0, no_markdown: bool = False
) -> None:
    """Speak text piped via stdin."""
    if voice not in ALL_VOICES:
        raise SystemExit(f"Unknown voice {voice!r}; available: {', '.join(ALL_VOICES)}")
    raw = sys.stdin.read()
    text = raw if no_markdown else to_plain(raw)
    if not text.strip():
        raise SystemExit("No text to speak")

    if server_is_running():
        server_send(text, voice, speed)
    else:
        asyncio.run(speak_async(load_kokoro(), text, voice, speed))
