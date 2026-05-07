"""Manage the background TTS server (keeps model in memory between calls)."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import time

from dienpy.cli import Dispatcher

from ._core import (
    DEFAULT_VOICE,
    LOG_PATH,
    PID_PATH,
    SOCKET_PATH,
    STATE_DIR,
    ensure_models,
    load_kokoro,
    server_is_running,
    speak_async,
)


async def _handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    kokoro,
    lock: asyncio.Lock,
) -> None:
    try:
        line = await reader.readline()
        req = json.loads(line.strip())
        async with lock:
            await speak_async(
                kokoro,
                req["text"],
                req.get("voice", DEFAULT_VOICE),
                req.get("speed", 1.0),
            )
        writer.write(json.dumps({"ok": True}).encode() + b"\n")
        await writer.drain()
    except Exception as e:
        try:
            writer.write(json.dumps({"ok": False, "error": str(e)}).encode() + b"\n")
            await writer.drain()
        except Exception:
            pass
    finally:
        writer.close()


async def _serve() -> None:
    kokoro = load_kokoro()
    lock = asyncio.Lock()

    if SOCKET_PATH.exists():
        SOCKET_PATH.unlink()
    PID_PATH.write_text(str(os.getpid()))

    server = await asyncio.start_unix_server(
        lambda r, w: _handle_client(r, w, kokoro, lock),
        path=str(SOCKET_PATH),
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _shutdown() -> None:
        SOCKET_PATH.unlink(missing_ok=True)
        PID_PATH.unlink(missing_ok=True)
        stop.set()

    loop.add_signal_handler(signal.SIGTERM, _shutdown)
    loop.add_signal_handler(signal.SIGINT, _shutdown)

    async with server:
        await stop.wait()


def _start() -> None:
    """Start the background TTS server."""
    if server_is_running():
        print("TTS server already running")
        return

    ensure_models()
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    if (pid := os.fork()) > 0:
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            time.sleep(0.2)
            if server_is_running():
                print(f"TTS server started (PID {PID_PATH.read_text().strip()})")
                return
        raise SystemExit("TTS server failed to start (timeout)")

    os.setsid()
    if os.fork() > 0:
        os._exit(0)

    null = os.open(os.devnull, os.O_RDONLY)
    os.dup2(null, sys.stdin.fileno())
    os.close(null)
    log = os.open(str(LOG_PATH), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    os.dup2(log, sys.stdout.fileno())
    os.dup2(log, sys.stderr.fileno())
    os.close(log)

    asyncio.run(_serve())
    os._exit(0)


def _stop() -> None:
    """Stop the background TTS server."""
    if not server_is_running():
        print("TTS server not running")
        return
    pid = int(PID_PATH.read_text().strip())
    os.kill(pid, signal.SIGTERM)
    time.sleep(0.3)
    print(f"TTS server stopped (PID {pid})")


def _status() -> None:
    """Show TTS server status."""
    if server_is_running():
        print(f"TTS server running (PID {PID_PATH.read_text().strip()})")
    else:
        print("TTS server not running")


_dispatcher = Dispatcher(
    "dienpy tts server",
    {"start": _start, "stop": _stop, "status": _status},
)
