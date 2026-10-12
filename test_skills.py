from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.config import Settings
from app.providers.base import ChatResult
from app.schemas import SearchHit, SkillRunRequest
from app.services import skills


def test_essay_skill_uses_retrieved_evidence_and_reports_citations(monkeypatch) -> None:
    source = SearchHit(
        chunk_id="chunk-1",
        doc_id="doc-1",
        title="Activation interview",
        url="https://example.org/transcript",
        source="lenny-podcast",
        score=0.9,
        content="Shortening onboarding helps users reach the first value moment.",
    )
    captured: dict[str, list] = {}

    async def fake_retrieve(*_args, **_kwargs):
        return [source], "test-embed"

    class FakeRouter:
        default_provider = "ollama"

        def get(self, _provider):
            return SimpleNamespace(chat_model="test-model")

        async def chat(self, messages, *, provider, model, max_tokens):
            captured["messages"] = messages
            return ChatResult(
                content="# Activation Starts with Value\n\n[1] Make the first step useful.",
                provider=provider,
                model=model,
                latency_ms=1,
            )

    monkeypatch.setattr(skills, "retrieve_context", fake_retrieve)
    settings = Settings(_env_file=None)
    result = asyncio.run(
        skills.run_ship_30_for_30(
            None,
            settings,
            FakeRouter(),
            SkillRunRequest(topic="Improve activation", word_target=1250),
        )
    )

    assert result.grounded is True
    assert result.citations[0].url == source.url
    assert result.word_count > 0
    prompt = captured["messages"][1].content
    assert "approximately" in prompt or "1250 words" in prompt
    assert "Shortening onboarding" in prompt
    assert "over-editing" in prompt
