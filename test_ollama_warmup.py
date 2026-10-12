from __future__ import annotations

import asyncio

from app.config import Settings
from app.main import _warm_ollama_models
from app.providers.base import ChatMessage, ChatResult, EmbeddingResult
from app.providers.ollama_provider import OllamaProvider


def test_startup_warms_configured_ollama_models(monkeypatch) -> None:
    embedded: list[tuple[list[str], str | None]] = []
    chats: list[tuple[list[ChatMessage], str | None, int | None]] = []

    async def fake_embed(self, texts, *, model=None):
        embedded.append((texts, model))
        return EmbeddingResult(vectors=[[0.1]], provider="ollama", model=model or "", dim=1)

    async def fake_chat(self, messages, *, model=None, temperature=0.2, max_tokens=None):
        chats.append((messages, model, max_tokens))
        return ChatResult(content="OK", provider="ollama", model=model or "", latency_ms=1)

    monkeypatch.setattr(OllamaProvider, "embed", fake_embed)
    monkeypatch.setattr(OllamaProvider, "chat", fake_chat)

    asyncio.run(_warm_ollama_models(Settings(_env_file=None)))

    assert embedded == [(["warm up"], "nomic-embed-text")]
    assert len(chats) == 1
    assert chats[0][0] == [ChatMessage(role="user", content="Reply OK.")]
    assert chats[0][1:] == ("llama3.2", 4)
