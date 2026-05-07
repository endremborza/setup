"""Speak text piped via stdin."""

from __future__ import annotations

import argparse
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--voice", default=DEFAULT_VOICE, choices=ALL_VOICES)
    parser.add_argument("--speed", type=float, default=1.0, metavar="N")
    parser.add_argument("--no-markdown", action="store_true")
    args = parser.parse_args()

    raw = sys.stdin.read()
    text = raw if args.no_markdown else to_plain(raw)
    if not text.strip():
        raise SystemExit("No text to speak")

    if server_is_running():
        server_send(text, args.voice, args.speed)
    else:
        asyncio.run(speak_async(load_kokoro(), text, args.voice, args.speed))
