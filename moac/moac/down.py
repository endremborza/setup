"""Stop what serves a profile (the `serve` unit in moac.toml), freeing its memory."""

from . import _profiles, _serve
from ._profiles import ProfileName


def main(profile: ProfileName) -> None:
    served = _serve.unit(profile, _profiles.get(profile))
    _serve.systemctl("stop", served)
    print(f"{profile} down ({served})")
