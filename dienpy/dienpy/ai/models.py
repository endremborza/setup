"""List and refresh the cached model ids per API provider; the anthropic ids complete `ai run`."""

import sys
from typing import Annotated, Literal

from protocli import Complete

from . import _cache, _profiles, _transport

PROVIDERS = ("anthropic", "google")
Provider = Literal["anthropic", "google"]


def choices() -> list[str]:
    """What `ai run` accepts: a profile name, or a bare claude model id for the cli."""
    return _profiles.names() + _cache.ids("anthropic")


Target = Annotated[str, Complete(choices)]


def update(
    providers: tuple[str, ...] = PROVIDERS, *, force: bool = False, quiet: bool = False
) -> None:
    """Re-fetch a provider's list once it is older than a day (or on `force`); a failed
    fetch is reported, never raised, so a scheduler can call this every cycle."""
    for prov in providers:
        if not force and not _cache.needs_refresh(prov):
            continue
        try:
            models = _transport.fetch_models(prov)
        except SystemExit as e:
            if not quiet:
                print(f"[{prov}] skipped: {e}", file=sys.stderr)
            continue
        except Exception as e:
            if not quiet:
                print(
                    f"[{prov}] fetch failed: {type(e).__name__}: {e}", file=sys.stderr
                )
            continue
        _cache.save(prov, models)
        if not quiet:
            print(f"[{prov}] {len(models)} models cached.", file=sys.stderr)


def main(*, refresh: bool = False, provider: Provider | None = None) -> None:
    """List cached model ids, refreshing lists older than a day; --refresh re-fetches now."""
    wanted = (provider,) if provider else PROVIDERS
    update(wanted, force=refresh)
    for prov, models in _cache.load().items():
        if prov not in wanted:
            continue
        print(f"\n{prov}:")
        for m in models:
            print(f"  {m}")
