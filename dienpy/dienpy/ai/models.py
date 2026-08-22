"""List and refresh cached AI model IDs across API providers."""

import sys
from typing import Literal

from . import _cache, _transport

_PROVIDERS = ("anthropic", "google")


def main(
    *, refresh: bool = False, provider: Literal["anthropic", "google"] | None = None
) -> None:
    """List available AI models; --refresh forces a re-fetch."""
    for prov in [provider] if provider else list(_PROVIDERS):
        if refresh or _cache.needs_refresh(prov):
            try:
                models = _transport.fetch_models(prov)
                _cache.save(prov, models)
                print(f"[{prov}] {len(models)} models cached.", file=sys.stderr)
            except SystemExit as e:
                print(f"[{prov}] skipped: {e}", file=sys.stderr)
            except Exception as e:
                print(f"[{prov}] fetch failed: {e}", file=sys.stderr)

    for prov, models in _cache.load().items():
        if provider and prov != provider:
            continue
        print(f"\n{prov}:")
        for m in models:
            print(f"  {m}")
