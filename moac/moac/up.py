"""Start what serves a profile (the `serve` unit in moac.toml) and wait until it answers."""

from . import _profiles, _serve
from ._profiles import ProfileName


def main(profile: ProfileName) -> None:
    spec = _profiles.get(profile)
    served = _serve.unit(profile, spec)
    _serve.systemctl("start", served)
    found = _serve.wait_ready(profile, spec, served)
    print(f"{profile} up ({served}): " + " ".join(f"{k}={v}" for k, v in found.items()))
