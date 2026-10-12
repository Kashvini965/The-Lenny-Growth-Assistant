"""Provider abstraction: chat + embeddings for local and cloud models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChatMessage:
    role: str  # system | user | assistant
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class ChatResult:
    content: str
    provider: str
    model: str
    latency_ms: int
    usage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbeddingResult:
    vectors: list[list[float]]
    provider: str
    model: str
    dim: int


class LLMProvider(ABC):
    """Common interface implemented by every provider adapter."""

    name: str
    kind: str  # "local" | "cloud"

    @property
    @abstractmethod
    def chat_model(self) -> str:
        """Default chat model identifier for this provider."""

    @property
    def embed_model(self) -> str | None:
        return None

    @abstractmethod
    def is_configured(self) -> bool:
        """True when the provider has everything it needs to be called."""

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> ChatResult:
        """Run a chat completion."""

    async def embed(self, texts: list[str], *, model: str | None = None) -> EmbeddingResult:
        raise NotImplementedError(f"{self.name} does not implement embeddings")

    async def health(self) -> tuple[bool, str | None]:
        """Cheap liveness probe; default implementation is a no-op success."""
        return True, None
