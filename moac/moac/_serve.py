"""What serves a profile: the systemd user unit its `serve` field names (a llama-server on
this machine, a tunnel to one elsewhere), which `moac up` starts and `moac down` stops."""

import subprocess
from typing import Any

FIELD = "serve"
# how long a model may take to load before `up` gives up
READY = 300
_POLL = 0.5


def unit(name: str, spec: dict[str, Any]) -> str:
    served = str(spec.get(FIELD, ""))
    if not served:
        raise SystemExit(f"profile '{name}' names no `{FIELD}` unit in moac.toml")
    return served


def active(served: str) -> bool:
    done = subprocess.run(["systemctl", "--user", "is-active", "--quiet", served])
    return done.returncode == 0


def systemctl(verb: str, served: str) -> None:
    done = subprocess.run(
        ["systemctl", "--user", verb, served], capture_output=True, text=True
    )
    if done.returncode:
        raise SystemExit(f"systemctl --user {verb} {served}: {done.stderr.strip()}")


def reports(spec: dict[str, Any], timeout: float = 1.0) -> dict[str, Any]:
    """What an openai endpoint says of itself, as llama-server's /props does: the context it
    was started with and whether it takes images; empty when it does not answer."""
    import requests

    url = str(spec.get("url", "")).replace("/v1/chat/completions", "/props")
    try:
        r = requests.get(url, timeout=timeout)
    except requests.RequestException:
        return {}
    if not r.ok:
        return {}
    props = r.json()
    settings = props.get("default_generation_settings") or {}
    return {
        "ctx": settings.get("n_ctx"),
        "vision": bool((props.get("modalities") or {}).get("vision")),
    }


def wait_ready(name: str, spec: dict[str, Any], served: str) -> dict[str, Any]:
    """Polls until the endpoint answers; the unit dying or `READY` passing is a failure."""
    import time

    end = time.monotonic() + READY
    while time.monotonic() < end:
        if found := reports(spec):
            return found
        if not active(served):
            raise SystemExit(f"profile '{name}': {served} stopped before it answered")
        time.sleep(_POLL)
    raise SystemExit(f"profile '{name}': {served} did not answer within {READY}s")
