"""Make a cached run the current one — the run `patch` commands, `run` without dims and nvim act on."""

from . import _cache, _config, _hunks, _patches


def main(*dims: _config.Dim) -> None:
    root = _hunks.git_root()
    hunks = _hunks.parse(root)
    _cache.prune(root, hunks)
    config = _config.resolve(dims, _cache.last_config(root))
    entry = _cache.entry(root, config)
    if not entry:
        raise SystemExit(f"no cached run for [{config.key}]")
    _cache.touch_last(root, config)
    print(f"[{config.key}]")
    _patches.print_patches(entry["patches"], {h.id for h in hunks})
