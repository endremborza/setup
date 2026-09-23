"""The run every patch command acts on: the last-used config's cached entry, sanitized
against the live diff — the one listing `use` prints and `patch <position>` selects from."""

from dataclasses import dataclass, field
from functools import cached_property

from dienpy._git import find_root

from .. import _cache, _config, _hunks, _patches
from .._hunks import Hunk


@dataclass
class Current:
    root: str
    config: _config.Config
    hunks: list[Hunk]
    patches: list[dict]
    live: set[str] = field(init=False)

    def __post_init__(self) -> None:
        self.live = {h.id for h in self.hunks}

    @cached_property
    def index(self) -> list[Hunk]:
        return _hunks.parse(self.root, staged=True)

    def ids(self, tokens: tuple[str, ...], *, live_only: bool = False) -> list[str]:
        """Hunk ids the tokens name; a bare id may also be one only the index holds."""
        known = self.live if live_only else self.live | {h.id for h in self.index}
        ids = _patches.hunk_ids(self.patches, tokens, self.live, known)
        if not ids:
            raise SystemExit("no live hunks selected")
        return ids

    def reparse(self) -> None:
        """After a write that moved hunks between the views."""
        self.hunks = _hunks.parse(self.root)
        self.live = {h.id for h in self.hunks}
        self.__dict__.pop("index", None)

    def save(self) -> None:
        _cache.set_entry(self.root, self.config, self.hunks, self.patches)


def load(dims: tuple[str, ...] = ()) -> Current:
    root = find_root()
    hunks = _hunks.parse(root)
    _cache.prune(root, hunks)
    config = _config.resolve(dims, _cache.last_config(root))
    entry = _cache.entry(root, config)
    if not entry:
        raise _cache.missing(root, config)
    live = {h.id for h in hunks}
    return Current(root, config, hunks, _patches.sanitize(entry["patches"], live))
