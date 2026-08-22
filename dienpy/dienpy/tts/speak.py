"""Speak text piped via stdin."""

from __future__ import annotations

import asyncio
import sys
from typing import Annotated

from protocli import Complete

from ._core import (
    ALL_VOICES,
    DEFAULT_VOICE,
    load_kokoro,
    server_is_running,
    server_send,
    speak_async,
    to_plain,
)

Voice = Annotated[str, Complete(ALL_VOICES)]


def main(
    *, voice: Voice = DEFAULT_VOICE, speed: float = 1.0, no_markdown: bool = False
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
