"""Shared paths, voice constants, and synthesis primitives."""

from __future__ import annotations

import json
import os
import socket
import subprocess
from pathlib import Path

MODEL_DIR = Path.home() / ".local" / "share" / "kokoro"
MODEL_PATH = MODEL_DIR / "kokoro-v1.0.onnx"
VOICES_PATH = MODEL_DIR / "voices-v1.0.bin"
STATE_DIR = Path.home() / ".local" / "state" / "dienpy"
SOCKET_PATH = STATE_DIR / "tts.sock"
PID_PATH = STATE_DIR / "tts.pid"
LOG_PATH = STATE_DIR / "tts.log"

MODEL_BASE_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
)
DEFAULT_VOICE = "af_heart"

AF_VOICES = [
    "af_heart",
    "af_alloy",
    "af_aoede",
    "af_bella",
    "af_jessica",
    "af_kore",
    "af_nicole",
    "af_nova",
    "af_river",
    "af_sarah",
    "af_sky",
]
AM_VOICES = [
    "am_adam",
    "am_echo",
    "am_eric",
    "am_fenrir",
    "am_liam",
    "am_michael",
    "am_onyx",
    "am_puck",
    "am_santa",
]
BF_VOICES = ["bf_alice", "bf_emma", "bf_isabella", "bf_lily"]
BM_VOICES = ["bm_daniel", "bm_fable", "bm_george", "bm_lewis"]
ALL_VOICES = AF_VOICES + AM_VOICES + BF_VOICES + BM_VOICES


def ensure_models() -> None:
    if not (MODEL_PATH.exists() and VOICES_PATH.exists()):
        raise SystemExit(
            f"Model files not found in {MODEL_DIR}. Run: dienpy tts download"
        )


def load_kokoro():
    from kokoro_onnx import Kokoro

    ensure_models()
    return Kokoro(str(MODEL_PATH), str(VOICES_PATH))


def to_plain(text: str) -> str:
    try:
        r = subprocess.run(
            ["pandoc", "-f", "markdown", "-t", "plain"],
            input=text,
            capture_output=True,
            text=True,
            check=True,
        )
        return r.stdout
    except FileNotFoundError:
        return text


async def speak_async(kokoro, text: str, voice: str, speed: float) -> None:
    import sounddevice as sd

    stream: sd.OutputStream | None = None
    async for samples, sr in kokoro.create_stream(
        text, voice=voice, speed=speed, lang="en-us"
    ):
        if stream is None:
            stream = sd.OutputStream(samplerate=sr, channels=1, dtype="float32")
            stream.start()
        stream.write(samples)
    if stream is not None:
        stream.stop()
        stream.close()


def server_is_running() -> bool:
    if not PID_PATH.exists():
        return False
    try:
        pid = int(PID_PATH.read_text().strip())
        os.kill(pid, 0)
        return SOCKET_PATH.exists()
    except (ValueError, ProcessLookupError, PermissionError, OSError):
        return False


def server_send(text: str, voice: str, speed: float) -> None:
    req = json.dumps({"text": text, "voice": voice, "speed": speed}).encode() + b"\n"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.connect(str(SOCKET_PATH))
        s.sendall(req)
        buf = b""
        while b"\n" not in buf:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
    data = json.loads(buf.strip())
    if not data.get("ok"):
        raise SystemExit(f"TTS server error: {data.get('error', 'unknown')}")
