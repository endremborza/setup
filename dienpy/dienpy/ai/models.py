"""dienpy ai models — list and refresh cached AI model IDs across providers."""

import argparse
import sys

from . import _cache, _client

_PROVIDERS: dict[str, _client.Client] = {
    "anthropic": _client.AnthropicClient(),
    "google": _client.GoogleClient(),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="List available AI models.")
    parser.add_argument(
        "--refresh", action="store_true", help="Force refresh all providers."
    )
    parser.add_argument(
        "--provider", choices=list(_PROVIDERS), help="Limit to one provider."
    )
    args = parser.parse_args()

    targets = [args.provider] if args.provider else list(_PROVIDERS)

    for provider in targets:
        if args.refresh or _cache.needs_refresh(provider):
            try:
                models = _PROVIDERS[provider].fetch_models()
                _cache.save(provider, models)
                print(f"[{provider}] {len(models)} models cached.", file=sys.stderr)
            except SystemExit as e:
                print(f"[{provider}] skipped: {e}", file=sys.stderr)
            except Exception as e:
                print(f"[{provider}] fetch failed: {e}", file=sys.stderr)

    for provider, models in _cache.load().items():
        if args.provider and provider != args.provider:
            continue
        print(f"\n{provider}:")
        for m in models:
            print(f"  {m}")


def get_completions(args: list[str]) -> list[str]:
    if args and args[-1] == "--provider":
        return list(_PROVIDERS)
    return ["--refresh", "--provider"]
