"""Provider routing for AI inference and model listing.

Provider detection is by model ID prefix:
  claude-*  → Anthropic  (requires ANTHROPIC_API_KEY)
  gemini-*  → Google     (requires GEMINI_API_KEY or application default credentials)

To add a new provider, add a prefix check in detect_provider() and implement
_<provider>_send() / fetch_<provider>_models() functions.
"""

import os

# Beta header required for Anthropic extended thinking.
# To verify it's current: strings $(which claude) | grep interleaved-thinking
_ANTHROPIC_THINKING_BETA = "interleaved-thinking-2025-05-14"

EFFORT_BUDGETS: dict[str, int | None] = {
    "none": None,
    "low": 2048,
    "medium": 8192,
    "high": 32768,
}


def detect_provider(model: str) -> str:
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith("gemini"):
        return "google"
    raise SystemExit(
        f"Cannot determine provider for model '{model}'. "
        "Supported prefixes: claude-, gemini-"
    )


def send(
    model: str, system: str, user: str, max_tokens: int = 1024, effort: str = "none"
) -> str:
    """Route a message to the appropriate provider and return the text response."""
    budget = EFFORT_BUDGETS.get(effort)
    provider = detect_provider(model)
    if provider == "anthropic":
        return _anthropic_send(model, system, user, max_tokens, budget)
    if provider == "google":
        return _google_send(model, system, user, max_tokens, budget)
    raise SystemExit(f"Unknown provider: {provider}")


# === Anthropic ===


def _anthropic_send(
    model: str, system: str, user: str, max_tokens: int, budget: int | None
) -> str:
    import anthropic  # lazy import — zero startup cost

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY is not set.")
    client = anthropic.Anthropic()
    kwargs: dict = {
        "model": model,
        "max_tokens": max(max_tokens, budget + 1024) if budget else max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    if budget:
        kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget}
        kwargs["extra_headers"] = {"anthropic-beta": _ANTHROPIC_THINKING_BETA}

    msg = client.messages.create(**kwargs)
    for block in msg.content:
        if block.type == "text":
            return block.text.strip()
    raise SystemExit("No text content in model response.")


def fetch_anthropic_models() -> list[str]:
    import anthropic  # lazy import

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY is not set.")
    client = anthropic.Anthropic()
    return sorted(m.id for m in client.models.list())


# === Google ===


def _google_client():
    from google import genai  # lazy import

    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        return genai.Client(api_key=api_key)
    # Fall back to application default credentials (gcloud auth application-default login).
    try:
        return genai.Client()
    except Exception:
        raise SystemExit(
            "Google auth not configured. Set GEMINI_API_KEY or run: "
            "gcloud auth application-default login"
        )


def _google_send(
    model: str, system: str, user: str, max_tokens: int, budget: int | None
) -> str:
    from google.genai import types  # lazy import

    client = _google_client()
    config = types.GenerateContentConfig(
        system_instruction=system,
        max_output_tokens=max_tokens,
        thinking_config=types.ThinkingConfig(thinking_budget=budget)
        if budget
        else None,
    )
    response = client.models.generate_content(model=model, contents=user, config=config)
    return response.text.strip()


def fetch_google_models() -> list[str]:
    client = _google_client()
    return sorted(
        m.name.removeprefix("models/")
        for m in client.models.list()
        if "generateContent" in (m.supported_actions or [])
    )


# === Local ===


def _local_send(
    model: str, system: str, user: str, max_tokens: int, budget: int | None
):
    import requests

    r = requests.post(
        "http://localhost:8080/v1/chat/completions",
        json={
            "model": "local",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "repeat_penalty": 1.1,
        },
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()
