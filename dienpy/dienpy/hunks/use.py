"""Make a cached run the current one — the run `patch` commands, `run` without dims and nvim act on."""

from . import _cache, _config, _patches
from .patch import _current


def main(*dims: _config.Dim) -> None:
    cur = _current.load(dims)
    _cache.touch_last(cur.root, cur.config)
    print(f"[{cur.config.key}]")
    _patches.print_patches(cur.patches, cur.live)
