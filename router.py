"""Provider registry + routing.

`ProviderRouter` is the single place the rest of the app talks to about
models. It resolves provider names (explicit request value -> session value ->
`DEFAULT_PROVIDER`), validates that the chosen provider is usable, and exposes
a unified interface for chat and embeddings.

Swapping providers requires **no application code changes** - only `.env` or a
per-request/per-session `provider` field.
"""

from __future__ import annotations

from functools import lru_cache

from app.config import Settings, get_settings
from app.errors import ProviderConfigError, ProviderUnavailableError
from app.logging_config import get_logger
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.base import ChatMessage, ChatResult, EmbeddingResult, LLMProvider
from app.providers.ollama_provider import OllamaProvider
from app.providers.openai_provider import OpenAIProvider

logger = get_logger(__name__)

PROVIDER_NAMES = ("ollama", "openai", "anthropic")


class ProviderRouter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._providers: dict[str, LLMProvider] = {
            "ollama": OllamaProvider(settings),
            "openai": OpenAIProvider(settings),
            "anthropic": AnthropicProvider(settings),
        }

    # ------------------------------------------------------------- resolution
    @property
    def default_provider(self) -> str:
        configured_default = self._settings.default_provider.strip().lower()
        if configured_default not in self._providers:
            logger.warning(
                "DEFAULT_PROVIDER=%r is unknown; falling back to 'ollama'.", configured_default
            )
            return "ollama"
        return configured_default

    def get(self, name: str | None = None) -> LLMProvider:
        """Resolve a provider by name, validating configuration."""
        resolved = (name or self.default_provider).strip().lower()
        provider = self._providers.get(resolved)
        if provider is None:
            raise ProviderConfigError(
                f"Unknown provider '{resolved}'. Choose one of: {', '.join(PROVIDER_NAMES)}.",
                details={"provider": resolved, "available": list(PROVIDER_NAMES)},
            )
        if not provider.is_configured():
            raise ProviderConfigError(
                f"Provider '{resolved}' is not configured.",
                details={
                    "provider": resolved,
                    "hint": "Set OPENAI_API_KEY / ANTHROPIC_API_KEY in backend/.env, or use 'ollama'.",
                },
            )
        return provider

    def resolve_name(self, *candidates: str | None) -> str:
        """First non-empty candidate wins, else the configured default."""
        for candidate in candidates:
            if candidate and candidate.strip():
                return candidate.strip().lower()
        return self.default_provider

    # ------------------------------------------------------------------ chat
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> ChatResult:
        impl = self.get(provider)
        logger.info(
            "chat -> provider=%s model=%s messages=%d",
            impl.name,
            model or impl.chat_model,
            len(messages),
        )
        return await impl.chat(messages, model=model, temperature=temperature, max_tokens=max_tokens)

    # ------------------------------------------------------------ embeddings
    def embedding_provider(self) -> LLMProvider:
        """Provider used for retrieval embeddings.

        Configurable via `EMBEDDING_PROVIDER`; unavailable providers degrade to
        Ollama so local-only installs keep working.
        """
        requested = (self._settings.embedding_provider or "ollama").strip().lower()
        provider = self._providers.get(requested)
        if requested == "anthropic":
            logger.warning("Anthropic does not provide embeddings; falling back to Ollama.")
            return self._providers["ollama"]
        if provider is None or not provider.is_configured():
            if requested not in ("ollama", ""):
                logger.warning(
                    "Embedding provider %r unavailable; falling back to Ollama.", requested
                )
            return self._providers["ollama"]
        return provider

    async def embed(self, texts: list[str], *, model: str | None = None) -> EmbeddingResult:
        impl = self.embedding_provider()
        return await impl.embed(texts, model=model)

    async def embed_one(self, text: str, *, model: str | None = None) -> list[float]:
        result = await self.embed([text], model=model)
        if not result.vectors:
            raise ProviderUnavailableError(
                "Embedding model returned no vector.", details={"provider": result.provider}
            )
        return result.vectors[0]

    # ---------------------------------------------------------------- health
    async def provider_infos(self) -> list[dict]:
        infos: list[dict] = []
        for name in PROVIDER_NAMES:
            impl = self._providers[name]
            configured = impl.is_configured()
            available = False
            detail: str | None = None
            if configured:
                try:
                    available, detail = await impl.health()
                except Exception as exc:  # noqa: BLE001 - health must never raise
                    available, detail = False, str(exc)
            else:
                detail = "No API key configured."
            infos.append(
                {
                    "name": name,
                    "configured": configured,
                    "available": available,
                    "kind": impl.kind,
                    "chat_model": impl.chat_model,
                    "embed_model": impl.embed_model,
                    "detail": detail,
                }
            )
        return infos

    async def ollama_health(self) -> tuple[bool, str | None]:
        return await self._providers["ollama"].health()


@lru_cache
def get_router() -> ProviderRouter:
    return ProviderRouter(get_settings())


def reset_router_cache() -> None:
    get_router.cache_clear()
