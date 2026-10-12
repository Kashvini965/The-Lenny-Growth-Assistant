"""Anthropic provider adapter (optional cloud provider).

Anthropic has no public embeddings endpoint, so `embed()` intentionally
raises - the embedding router falls back to Ollama/OpenAI for retrieval.
"""

from __future__ import annotations

import time

from app.config import Settings
from app.errors import ProviderConfigError, ProviderUnavailableError
from app.providers.base import ChatMessage, ChatResult, LLMProvider
from app.providers.http import build_client, get_json, post_json

ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    kind = "cloud"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def chat_model(self) -> str:
        return self._settings.anthropic_chat_model

    def is_configured(self) -> bool:
        return bool(self._settings.anthropic_api_key.strip())

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._settings.anthropic_api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> ChatResult:
        if not self.is_configured():
            raise ProviderConfigError(
                "Anthropic is not configured. Set ANTHROPIC_API_KEY in backend/.env.",
                details={"provider": self.name},
            )
        target = model or self.chat_model
        system_prompt = "\n\n".join(m.content for m in messages if m.role == "system")
        turns = [m.to_dict() for m in messages if m.role != "system"]

        payload: dict = {
            "model": target,
            "messages": turns,
            "max_tokens": max_tokens or 2048,
            "temperature": temperature,
        }
        if system_prompt:
            payload["system"] = system_prompt

        started = time.perf_counter()
        async with build_client(
            self._settings.anthropic_base_url, self._settings.chat_request_timeout_seconds, self._headers()
        ) as client:
            data = await post_json(client, "/v1/messages", payload, provider="Anthropic")

        blocks = data.get("content") or []
        text = "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
        if not text:
            raise ProviderUnavailableError("Anthropic returned an empty response.", details={"provider": self.name})
        return ChatResult(
            content=text,
            provider=self.name,
            model=data.get("model", target),
            latency_ms=int((time.perf_counter() - started) * 1000),
            usage=data.get("usage") or {},
        )

    async def health(self) -> tuple[bool, str | None]:
        if not self.is_configured():
            return False, "ANTHROPIC_API_KEY not set"
        try:
            async with build_client(
                self._settings.anthropic_base_url,
                self._settings.chat_request_timeout_seconds,
                self._headers(),
            ) as client:
                await get_json(client, f"/v1/models/{self.chat_model}", provider="Anthropic")
        except Exception as exc:
            return False, str(exc)
        return True, None
