"""dienpy ai models — list and refresh cached AI model IDs across providers."""

import sys
from typing import Literal

from . import _cache, _client

_PROVIDERS: dict[str, _client.Client] = {
    "anthropic": _client.AnthropicClient(),
    "google": _client.GoogleClient(),
}


def main(
    *, refresh: bool = False, provider: Literal["anthropic", "google"] | None = None
) -> None:
    """List available AI models; --refresh forces a re-fetch."""
    targets = [provider] if provider else list(_PROVIDERS)

    for prov in targets:
        if refresh or _cache.needs_refresh(prov):
            try:
                models = _PROVIDERS[prov].fetch_models()
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
