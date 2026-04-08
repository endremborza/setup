import os
from abc import ABC, abstractmethod

_ANTHROPIC_THINKING_BETA = "interleaved-thinking-2025-05-14"

EFFORT_BUDGETS: dict[str, int | None] = {
    "none": None,
    "low": 2048,
    "medium": 8192,
    "high": 32768,
}

LOCAL_URL = "http://localhost:8081/v1/chat/completions"


class Client(ABC):
    @abstractmethod
    def send(
        self,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 1024,
        budget: int | None = None,
        temperature: float = 1.0,
        top_p: float | None = None,
        top_k: int | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
    ) -> str: ...

    @abstractmethod
    def fetch_models(self) -> list[str]: ...


class AnthropicClient(Client):
    def send(
        self,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 1024,
        budget: int | None = None,
        temperature: float = 1.0,
        top_p: float | None = None,
        top_k: int | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
    ) -> str:
        import anthropic

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit("ANTHROPIC_API_KEY is not set.")
        kwargs: dict = {
            "model": model,
            "max_tokens": max(max_tokens, budget + 1024) if budget else max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "temperature": temperature,
        }
        if top_p is not None:
            kwargs["top_p"] = top_p
        if top_k is not None:
            kwargs["top_k"] = top_k
        if budget:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget}
            kwargs["extra_headers"] = {"anthropic-beta": _ANTHROPIC_THINKING_BETA}
        msg = anthropic.Anthropic().messages.create(**kwargs)
        for block in msg.content:
            if block.type == "text":
                return block.text.strip()
        raise SystemExit("No text content in model response.")

    def fetch_models(self) -> list[str]:
        import anthropic

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit("ANTHROPIC_API_KEY is not set.")
        return sorted(m.id for m in anthropic.Anthropic().models.list())


class GoogleClient(Client):
    def __init__(self) -> None:
        self._client = None

    def _sdk_client(self):
        if self._client is not None:
            return self._client
        from google import genai

        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            self._client = genai.Client(api_key=api_key)
        else:
            try:
                self._client = genai.Client()
            except Exception:
                raise SystemExit(
                    "Google auth not configured. Set GEMINI_API_KEY or run: "
                    "gcloud auth application-default login"
                )
        return self._client

    def send(
        self,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 1024,
        budget: int | None = None,
        temperature: float = 1.0,
        top_p: float | None = None,
        top_k: int | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
    ) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            thinking_config=types.ThinkingConfig(thinking_budget=budget)
            if budget
            else None,
        )
        response = self._sdk_client().models.generate_content(
            model=model, contents=user, config=config
        )
        return response.text.strip()

    def fetch_models(self) -> list[str]:
        return sorted(
            m.name.removeprefix("models/")
            for m in self._sdk_client().models.list()
            if "generateContent" in (m.supported_actions or [])
        )


class LocalClient(Client):
    def send(
        self,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 1024,
        budget: int | None = None,
        temperature: float = 1.0,
        top_p: float | None = None,
        top_k: int | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
    ) -> str:
        import requests

        body: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if top_p is not None:
            body["top_p"] = top_p
        if frequency_penalty is not None:
            body["repeat_penalty"] = frequency_penalty
        if presence_penalty is not None:
            body["presence_penalty"] = presence_penalty
        r = requests.post(LOCAL_URL, json=body)
        if not r.ok:
            try:
                detail = r.json().get("error", {})
                msg = (
                    detail.get("message") or detail
                    if isinstance(detail, str)
                    else str(detail)
                )
            except Exception:
                msg = r.text
            raise SystemExit(f"Local model error {r.status_code}: {msg}")
        return r.json()["choices"][0]["message"]["content"].strip()

    def fetch_models(self) -> list[str]:
        raise SystemExit("Local provider does not support model listing.")


def for_model(model: str) -> Client:
    if model.startswith("claude"):
        return AnthropicClient()
    if model.startswith("gemini"):
        return GoogleClient()
    if model.startswith("local"):
        return LocalClient()
    raise SystemExit(
        f"Cannot determine provider for model '{model}'. "
        "Supported prefixes: claude-, gemini-, local-"
    )


def send(
    model: str,
    system: str,
    user: str,
    max_tokens: int = 1024,
    effort: str = "none",
    temperature: float = 1.0,
    top_p: float | None = None,
    top_k: int | None = None,
    frequency_penalty: float | None = None,
    presence_penalty: float | None = None,
) -> str:
    return for_model(model).send(
        model,
        system,
        user,
        max_tokens,
        EFFORT_BUDGETS.get(effort),
        temperature,
        top_p,
        top_k,
        frequency_penalty,
        presence_penalty,
    )
