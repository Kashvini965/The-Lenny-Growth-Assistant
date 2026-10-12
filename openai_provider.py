"""OpenAI provider adapter (optional cloud provider)."""

from __future__ import annotations

import time

from app.config import Settings
from app.errors import ProviderConfigError, ProviderUnavailableError
from app.providers.base import ChatMessage, ChatResult, EmbeddingResult, LLMProvider
from app.providers.http import build_client, get_json, post_json


class OpenAIProvider(LLMProvider):
    name = "openai"
    kind = "cloud"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def chat_model(self) -> str:
        return self._settings.openai_chat_model

    @property
    def embed_model(self) -> str:
        return self._settings.openai_embed_model

    def is_configured(self) -> bool:
        return bool(self._settings.openai_api_key.strip())

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._settings.openai_api_key}", "Content-Type": "application/json"}

    def _client(self):
        return build_client(self._settings.openai_base_url, self._settings.chat_request_timeout_seconds, self._headers())

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
                "OpenAI is not configured. Set OPENAI_API_KEY in backend/.env.",
                details={"provider": self.name},
            )
        target = model or self.chat_model
        started = time.perf_counter()
        payload = {
            "model": target,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        async with self._client() as client:
            data = await post_json(client, "chat/completions", payload, provider="OpenAI")

        choices = data.get("choices") or []
        if not choices:
            raise ProviderUnavailableError("OpenAI returned no choices.", details={"provider": self.name})
        content = (choices[0].get("message") or {}).get("content", "").strip()
        return ChatResult(
            content=content,
            provider=self.name,
            model=data.get("model", target),
            latency_ms=int((time.perf_counter() - started) * 1000),
            usage=data.get("usage") or {},
        )

    async def embed(self, texts: list[str], *, model: str | None = None) -> EmbeddingResult:
        if not self.is_configured():
            raise ProviderConfigError(
                "OpenAI is not configured. Set OPENAI_API_KEY in backend/.env.",
                details={"provider": self.name},
            )
        if not texts:
            return EmbeddingResult(vectors=[], provider=self.name, model=model or self.embed_model, dim=0)
        target = model or self.embed_model
        async with self._client() as client:
            data = await post_json(client, "embeddings", {"model": target, "input": texts}, provider="OpenAI")
        vectors = [item.get("embedding", []) for item in data.get("data", [])]
        dim = len(vectors[0]) if vectors and vectors[0] else 0
        return EmbeddingResult(vectors=vectors, provider=self.name, model=target, dim=dim)

    async def health(self) -> tuple[bool, str | None]:
        if not self.is_configured():
            return False, "OPENAI_API_KEY not set"
        try:
            async with self._client() as client:
                await get_json(client, f"models/{self.chat_model}", provider="OpenAI")
        except Exception as exc:
            return False, str(exc)
        return True, None
