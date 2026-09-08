"""The run every patch command acts on: the last-used config's cached entry."""

from dataclasses import dataclass

from .. import _cache, _config, _hunks, _patches
from .._hunks import Hunk


@dataclass
class Current:
    root: str
    config: _config.Config
    hunks: list[Hunk]
    patches: list[dict]

    @property
    def live(self) -> set[str]:
        return {h.id for h in self.hunks}

    def ids(self, tokens: tuple[str, ...]) -> list[str]:
        ids = _patches.hunk_ids(self.patches, tokens, self.live)
        if not ids:
            raise SystemExit("no live hunks selected")
        return ids

    def save(self) -> None:
        _cache.set_entry(self.root, self.config, self.hunks, self.patches)


def load() -> Current:
    root = _hunks.git_root()
    hunks = _hunks.parse(root)
    _cache.prune(root, hunks)
    config = _config.resolve((), _cache.last_config(root))
    entry = _cache.entry(root, config)
    if not entry:
        raise _cache.missing(root, config)
    live = {h.id for h in hunks}
    return Current(root, config, hunks, _patches.sanitize(entry["patches"], live))
