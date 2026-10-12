"""Ollama provider adapter - the mandatory local model for the demo.

Talks to the Ollama HTTP API directly (no extra SDK) so the same code path is
used by tests with a mocked `httpx` transport.

Relevant endpoints:
    GET  /api/tags          -> installed models (health + model discovery)
    POST /api/chat          -> chat completion
    POST /api/embeddings    -> single embedding (legacy but widely available)
    POST /api/embed         -> batch embeddings (newer Ollama)
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import OrderedDict
from collections.abc import AsyncIterator

import httpx

from app.config import Settings
from app.errors import ProviderTimeoutError, ProviderUnavailableError
from app.logging_config import get_logger
from app.providers.base import ChatMessage, ChatResult, EmbeddingResult, LLMProvider
from app.providers.http import build_client, get_json, get_shared_client, post_json

logger = get_logger(__name__)


class OllamaProvider(LLMProvider):
    name = "ollama"
    kind = "local"
    _embedding_cache_limit = 512

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._embedding_cache: OrderedDict[tuple[str, str], list[float]] = OrderedDict()

    @property
    def chat_model(self) -> str:
        return self._settings.ollama_chat_model

    @property
    def embed_model(self) -> str:
        return self._settings.ollama_embed_model

    def is_configured(self) -> bool:
        # Ollama needs no API key. Availability is a runtime concern and is
        # surfaced through the /models and /health endpoints instead.
        return True

    # ------------------------------------------------------------------ chat
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> ChatResult:
        target = model or self.chat_model
        started = time.perf_counter()
        payload: dict = {
            "model": target,
            "messages": [m.to_dict() for m in messages],
            "stream": False,
            "keep_alive": self._settings.ollama_keep_alive,
            "options": {"temperature": temperature, "num_ctx": 4096},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        else:
            payload["options"]["num_predict"] = 400

        client = get_shared_client(self._settings.ollama_base_url, self._settings.ollama_chat_timeout_seconds)
        data = await post_json(
            client,
            "/api/chat",
            payload,
            provider="Ollama",
            timeout=self._settings.ollama_chat_timeout_seconds,
        )

        content = ((data.get("message") or {}).get("content") or "").strip()
        latency_ms = int((time.perf_counter() - started) * 1000)
        if not content:
            raise ProviderUnavailableError(
                "Ollama returned an empty response. Try pulling the model or a smaller one.",
                details={"provider": "ollama", "model": target},
            )
        return ChatResult(
            content=content,
            provider=self.name,
            model=data.get("model", target),
            latency_ms=latency_ms,
            usage={
                "prompt_tokens": data.get("prompt_eval_count"),
                "completion_tokens": data.get("eval_count"),
            },
        )

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        target = model or self.chat_model
        payload = {
            "model": target,
            "messages": [message.to_dict() for message in messages],
            "stream": True,
            "keep_alive": self._settings.ollama_keep_alive,
            "options": {
                "temperature": temperature,
                "num_ctx": 4096,
                "num_predict": max_tokens or 400,
            },
        }
        client = get_shared_client(self._settings.ollama_base_url, self._settings.ollama_chat_timeout_seconds)
        try:
            async with client.stream(
                "POST",
                "/api/chat",
                json=payload,
                timeout=self._settings.ollama_chat_timeout_seconds,
            ) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode("utf-8", errors="replace")
                    logger.error(
                        "Ollama streaming request failed.",
                        extra={
                            "provider": self.name,
                            "model": target,
                            "path": "/api/chat",
                            "status": response.status_code,
                            "reason": body[:1000],
                        },
                    )
                    raise ProviderUnavailableError(
                        f"Ollama returned an error ({response.status_code}).",
                        details={"provider": self.name, "model": target, "status": response.status_code},
                    )
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError as exc:
                        logger.exception(
                            "Ollama returned invalid streaming JSON.",
                            extra={"provider": self.name, "model": target, "path": "/api/chat"},
                        )
                        raise ProviderUnavailableError(
                            "Ollama returned an invalid response. Please try again.",
                            details={"provider": self.name, "model": target},
                        ) from exc
                    if event.get("error"):
                        logger.error(
                            "Ollama reported a streaming generation error.",
                            extra={
                                "provider": self.name,
                                "model": target,
                                "path": "/api/chat",
                                "reason": str(event["error"]),
                            },
                        )
                        raise ProviderUnavailableError(
                            "Ollama couldn't generate a response. Check that the model fits available memory.",
                            details={"provider": self.name, "model": target},
                        )
                    content = (event.get("message") or {}).get("content") or ""
                    if content:
                        yield content
        except httpx.TimeoutException as exc:
            logger.exception(
                "Ollama streaming request timed out.",
                extra={"provider": self.name, "model": target, "path": "/api/chat"},
            )
            raise ProviderTimeoutError(
                "Ollama is taking too long. Please try again.",
                details={
                    "provider": self.name,
                    "model": target,
                    "timeout_seconds": self._settings.ollama_chat_timeout_seconds,
                },
            ) from exc
        except httpx.HTTPError as exc:
            logger.exception(
                "Ollama streaming connection failed.",
                extra={"provider": self.name, "model": target, "path": "/api/chat"},
            )
            raise ProviderUnavailableError(
                "Ollama isn't running. Start Ollama and try again.",
                details={"provider": self.name, "model": target},
            ) from exc

    # -------------------------------------------------------------- embeddings
    async def embed(self, texts: list[str], *, model: str | None = None) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(vectors=[], provider=self.name, model=model or self.embed_model, dim=0)
        target = model or self.embed_model
        keys = [(target, text) for text in texts]
        vectors_by_key = {
            key: self._embedding_cache[key]
            for key in dict.fromkeys(keys)
            if key in self._embedding_cache
        }
        for key in vectors_by_key:
            self._embedding_cache.move_to_end(key)

        missing_texts = list(dict.fromkeys(text for key, text in zip(keys, texts) if key not in vectors_by_key))
        if missing_texts:
            client = get_shared_client(
                self._settings.ollama_base_url,
                self._settings.ollama_embed_timeout_seconds,
            )
            missing_vectors = await self._embed_batch(client, target, missing_texts)
            if len(missing_vectors) != len(missing_texts):
                raise ProviderUnavailableError(
                    "Ollama returned an unexpected number of embeddings.",
                    details={"provider": self.name, "model": target},
                )
            for text, vector in zip(missing_texts, missing_vectors):
                key = (target, text)
                self._embedding_cache[key] = vector
                self._embedding_cache.move_to_end(key)
                if len(self._embedding_cache) > self._embedding_cache_limit:
                    self._embedding_cache.popitem(last=False)
                vectors_by_key[key] = vector

        vectors = [vectors_by_key[key] for key in keys]

        dim = len(vectors[0]) if vectors and vectors[0] else 0
        return EmbeddingResult(vectors=vectors, provider=self.name, model=target, dim=dim)

    async def _embed_batch(self, client, model: str, texts: list[str]) -> list[list[float]]:
        """Prefer the modern `/api/embed` batch endpoint, fall back per-text."""
        try:
            data = await self._post_embedding(
                client,
                "/api/embed",
                {"model": model, "input": texts, "keep_alive": self._settings.ollama_keep_alive},
                model,
            )
            embeddings = data.get("embeddings")
            if embeddings and len(embeddings) == len(texts):
                return embeddings
        except ProviderUnavailableError as exc:
            if exc.details.get("status") != 404:
                raise
            logger.debug("Ollama /api/embed unavailable (%s); using /api/embeddings.", exc)

        vectors: list[list[float]] = []
        for text in texts:
            data = await self._post_embedding(
                client,
                "/api/embeddings",
                {"model": model, "prompt": text, "keep_alive": self._settings.ollama_keep_alive},
                model,
            )
            embedding = data.get("embedding")
            if not embedding:
                raise ProviderUnavailableError(
                    "Ollama returned no embedding. Is the embedding model pulled?",
                    details={"provider": "ollama", "model": model},
                )
            vectors.append(embedding)
        return vectors

    async def _post_embedding(self, client, path: str, payload: dict, model: str) -> dict:
        for attempt in range(2):
            try:
                return await post_json(
                    client,
                    path,
                    payload,
                    provider="Ollama",
                    timeout=self._settings.ollama_embed_timeout_seconds,
                )
            except ProviderTimeoutError as exc:
                logger.warning(
                    "Ollama embedding request timed out.",
                    extra={
                        "provider": self.name,
                        "model": model,
                        "path": path,
                        "attempt": attempt + 1,
                        "reason": str(exc),
                        "error_type": type(exc).__name__,
                    },
                )
                if attempt == 0:
                    await asyncio.sleep(0.5)
                    continue
                raise ProviderTimeoutError(
                    "Ollama is taking too long. Please try again.",
                    details={
                        "provider": self.name,
                        "model": model,
                        "path": path,
                        "timeout_seconds": self._settings.ollama_embed_timeout_seconds,
                        "attempts": 2,
                    },
                ) from exc
            except ProviderUnavailableError as exc:
                if not exc.details.get("reason") or attempt > 0:
                    raise
                logger.warning(
                    "Ollama embedding request failed; retrying.",
                    extra={
                        "provider": self.name,
                        "model": model,
                        "path": path,
                        "attempt": attempt + 1,
                        "reason": exc.details["reason"],
                        "error_type": type(exc).__name__,
                    },
                )
                await asyncio.sleep(0.5)
        raise RuntimeError("Embedding retry loop exited unexpectedly.")

    # ------------------------------------------------------------------ health
    async def health(self) -> tuple[bool, str | None]:
        ok, detail, _ = await self.health_details()
        return ok, detail

    def model_status(self, installed: list[str], loaded: list[str]) -> list[dict[str, str | bool | None]]:
        statuses = []
        for model in (self.chat_model, self.embed_model):
            is_installed = any(name == model or name.startswith(f"{model}:") for name in installed)
            is_loaded = any(name == model or name.startswith(f"{model}:") for name in loaded)
            statuses.append(
                {
                    "name": model,
                    "installed": is_installed,
                    "loaded": is_loaded,
                    "pull_command": None if is_installed else f"ollama pull {model}",
                }
            )
        return statuses

    async def health_details(self) -> tuple[bool, str | None, list[dict[str, str | bool | None]]]:
        try:
            client = get_shared_client(self._settings.ollama_base_url, 5.0)
            tags, running = await asyncio.gather(
                get_json(client, "/api/tags", provider="Ollama", timeout=5.0),
                get_json(client, "/api/ps", provider="Ollama", timeout=5.0),
            )
        except ProviderTimeoutError:
            return False, "Ollama didn't respond in time. Start Ollama and try again.", []
        except ProviderUnavailableError as exc:
            if exc.details.get("reason"):
                return False, "Ollama isn't running. Start Ollama and try again.", []
            return False, str(exc), []
        installed = [model.get("name", "") for model in tags.get("models", [])]
        loaded = [model.get("name", "") for model in running.get("models", [])]
        statuses = self.model_status(installed, loaded)
        missing = [model for model in statuses if not model["installed"]]
        for model in missing:
            logger.error(
                "Required Ollama model is not installed.",
                extra={
                    "provider": self.name,
                    "model": model["name"],
                    "pull_command": model["pull_command"],
                    "installed": False,
                    "loaded": False,
                },
            )
        if missing:
            commands = "; ".join(str(model["pull_command"]) for model in missing)
            names = ", ".join(str(model["name"]) for model in missing)
            return False, f"Required models missing: {names}. Install with: {commands}", statuses
        unloaded = [str(model["name"]) for model in statuses if not model["loaded"]]
        if unloaded:
            return False, f"Required Ollama model(s) are not loaded: {', '.join(unloaded)}.", statuses
        return True, None, statuses
