from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.database import get_db
from app.errors import ProviderConfigError
from app.main import app
from app.models import Base
from app.schemas import SearchHit


class OfflineRouter:
    default_provider = "ollama"

    def __init__(self) -> None:
        self.chat_calls: list[list] = []

    def resolve_name(self, *candidates: str | None) -> str:
        return next((candidate for candidate in candidates if candidate), "ollama")

    def get(self, _name: str | None = None) -> SimpleNamespace:
        return SimpleNamespace(name="ollama", chat_model="test-model")

    async def embed(self, _texts: list[str]) -> SimpleNamespace:
        return SimpleNamespace(vectors=[[1.0, 0.0]], model="test-embed", provider="ollama")

    async def chat(
        self,
        messages: list,
        *,
        provider: str,
        model: str,
        max_tokens: int | None = None,
    ) -> SimpleNamespace:
        self.chat_calls.append(messages)
        return SimpleNamespace(
            content="Improve activation by reducing first-session friction [1].",
            provider=provider,
            model=model,
            latency_ms=3,
        )


def test_chat_endpoint_persists_independent_session_and_explicit_no_context_answer(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    settings = Settings(_env_file=None, sqlite_fallback_path=":memory:")
    router = OfflineRouter()
    monkeypatch.setattr("app.api.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.get_router", lambda: router)
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            response = client.post("/api/chat", json={"message": "How should we improve activation?"})
            assert response.status_code == 200
            data = response.json()
            first_session_id = UUID(data["session"]["id"])
            assert data["assistant_message"]["content"].startswith(
                "I can't answer that from the transcript knowledge base"
            )
            assert data["session"]["message_count"] == 2
            assert data["citations"] == []
            assert data["retrieval"]["results"] == 0
            assert router.chat_calls == []

            detail = client.get(f"/api/sessions/{data['session']['id']}")
            assert detail.status_code == 200
            assert [message["role"] for message in detail.json()["messages"]] == ["user", "assistant"]

            essay = client.post(
                "/api/skills/ship-30-for-30",
                json={"topic": "A topic without indexed evidence", "word_target": 600},
            )
            assert essay.status_code == 503
            assert essay.json()["error"]["code"] == "insufficient_transcript_evidence"
            assert router.chat_calls == []

            second = client.post("/api/sessions", json={"title": "Separate conversation"})
            assert second.status_code == 201
            second_session_id = UUID(second.json()["id"])
            assert second_session_id != first_session_id

            second_chat = client.post(
                "/api/chat",
                json={
                    "message": "Keep this in the other conversation",
                    "session_id": str(second_session_id),
                    "use_rag": False,
                },
            )
            assert second_chat.status_code == 200
            sessions = client.get("/api/sessions").json()
            assert len(sessions) == 2
            assert len({session["id"] for session in sessions}) == 2

            reopened_first = client.get(f"/api/sessions/{first_session_id}").json()
            reopened_second = client.get(f"/api/sessions/{second_session_id}").json()
            first_messages = reopened_first["messages"]
            second_messages = reopened_second["messages"]
            assert [message["content"] for message in first_messages] == [
                "How should we improve activation?",
                data["assistant_message"]["content"],
            ]
            assert [message["content"] for message in second_messages] == [
                "Keep this in the other conversation",
                second_chat.json()["assistant_message"]["content"],
            ]
            assert {message["session_id"] for message in first_messages} == {str(first_session_id)}
            assert {message["session_id"] for message in second_messages} == {str(second_session_id)}
            for messages in (first_messages, second_messages):
                timestamps = [
                    datetime.fromisoformat(message["created_at"].replace("Z", "+00:00"))
                    for message in messages
                ]
                assert len(timestamps) == 2
                assert timestamps[0] < timestamps[1]

            streamed = client.post(
                "/api/chat/stream",
                json={
                    "message": "A streamed follow-up",
                    "session_id": str(second_session_id),
                    "use_rag": False,
                },
            )
            assert streamed.status_code == 200
            assert streamed.headers["content-type"].startswith("text/event-stream")
            events = [
                json.loads(line.removeprefix("data: "))
                for line in streamed.text.splitlines()
                if line.startswith("data: ")
            ]
            complete = next(event for event in events if event["type"] == "complete")
            assert complete["response"]["assistant_message"]["content"].startswith(
                "Transcript-only answers are enabled"
            )
            reopened_streamed = client.get(f"/api/sessions/{second_session_id}").json()
            assert [message["content"] for message in reopened_streamed["messages"]][-2:] == [
                "A streamed follow-up",
                complete["response"]["assistant_message"]["content"],
            ]
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_ingest_search_and_chat_use_transcript_citations(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    settings = Settings(_env_file=None, sqlite_fallback_path=":memory:")
    router = OfflineRouter()
    monkeypatch.setattr("app.api.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.get_router", lambda: router)
    monkeypatch.setattr(
        "app.services.knowledge._load_github_transcripts",
        lambda _repo, _limit: _return_transcript(),
    )
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            ingest = client.post("/api/knowledge/ingest", json={"source": "seed", "limit": 1})
            assert ingest.status_code == 200
            assert ingest.json()["documents_ingested"] == 1
            assert ingest.json()["chunks_created"] == 1

            search = client.post(
                "/api/knowledge/search",
                json={"query": "activation onboarding", "top_k": 3},
            )
            assert search.status_code == 200
            assert search.json()["results"][0]["url"] == "https://example.org/transcript"

            chat_response = client.post(
                "/api/chat",
                json={"message": "How can we improve activation?"},
            )
            assert chat_response.status_code == 200
            chat_data = chat_response.json()
            assert "[1]" in chat_data["assistant_message"]["content"]
            assert "What the transcripts don't cover:" in chat_data["assistant_message"]["content"]
            assert chat_data["citations"][0]["title"] == "Activation interview"
            assert chat_data["citations"][0]["guest"] == "Dana Lee"
            assert chat_data["citations"][0]["timestamp"] == "00:12:23"
            assert chat_data["citations"][0]["youtube_url"] == "https://youtube.com/watch?v=abc"
            assert chat_data["retrieval"]["sufficient"] is False
            assert "teams improve product activation" in chat_data["assistant_message"]["content"]
            assert "single relevant transcript source" in chat_data["assistant_message"]["content"]
            assert (
                "Only 1 relevant transcript chunk was cited from 1 independent transcript source"
                in chat_data["assistant_message"]["content"]
            )
            assert router.chat_calls == []

            follow_up = client.post(
                "/api/chat",
                json={
                    "message": "Can you make that more concrete?",
                    "session_id": chat_data["session"]["id"],
                },
            )
            assert follow_up.status_code == 200
            assert "teams improve product activation" in follow_up.json()["assistant_message"]["content"]
            assert router.chat_calls == []

            updated = client.get(f"/api/sessions/{chat_data['session']['id']}")
            assert updated.json()["message_count"] == 4
            assert [message["role"] for message in updated.json()["messages"]] == [
                "user", "assistant", "user", "assistant"
            ]

            essay = client.post(
                "/api/skills/ship-30-for-30",
                json={
                    "topic": "Improve activation",
                    "session_id": chat_data["session"]["id"],
                    "word_target": 600,
                },
            )
            assert essay.status_code == 200
            assert essay.json()["grounded"] is True
            assert essay.json()["citations"][0]["title"] == "Activation interview"
            skill_prompt = router.chat_calls[-1][1].content
            assert "Can you make that more concrete?" in skill_prompt
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_unsupported_generated_claims_are_replaced_with_cited_transcript_quotes(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    settings = Settings(_env_file=None, sqlite_fallback_path=":memory:")
    router = OfflineRouter()
    hits = [
        SearchHit(
            chunk_id="chunk-1",
            doc_id="episode-1",
            title="PMF Interview One",
            url="https://example.org/one",
            source="lenny-podcast",
            score=0.9,
            content="Teams define product-market fit by looking for repeat use.",
        ),
        SearchHit(
            chunk_id="chunk-2",
            doc_id="episode-2",
            title="PMF Interview Two",
            url="https://example.org/two",
            source="lenny-podcast",
            score=0.8,
            content="Product-market fit is indicated when customers recommend the product to peers.",
        ),
    ]

    async def retrieve_two_sources(*_args, **_kwargs):
        return hits, "test-embed"

    monkeypatch.setattr("app.api.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.get_router", lambda: router)
    monkeypatch.setattr("app.services.chat.retrieve_context", retrieve_two_sources)
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/chat",
                json={"message": "How do teams find product-market fit?"},
            )

        assert response.status_code == 200
        data = response.json()
        answer = data["assistant_message"]["content"]
        assert "Improve activation by reducing first-session friction" not in answer
        assert "> Teams define product-market fit by looking for repeat use. [1]" in answer
        assert "- Product-market fit is indicated when customers recommend the product to peers. [2]" in answer
        assert "What the transcripts don't cover:" in answer
        assert [citation["title"] for citation in data["citations"]] == [
            "PMF Interview One",
            "PMF Interview Two",
        ]
        assert data["retrieval"]["sufficient"] is True
        assert len(router.chat_calls) == 1
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_database_errors_use_structured_unavailable_response(monkeypatch) -> None:
    class BrokenSession:
        def scalars(self, *_args, **_kwargs):
            raise OperationalError("SELECT", {}, RuntimeError("database offline"))

        def get_bind(self) -> SimpleNamespace:
            return SimpleNamespace(dialect=SimpleNamespace(name="sqlite", driver="pysqlite"))

        def rollback(self) -> None:
            pass

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        "app.database.get_session_factory",
        lambda: lambda: BrokenSession(),
    )
    with TestClient(app) as client:
        response = client.get("/api/sessions")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
    assert "database request failed" in response.json()["error"]["message"].lower()


def test_provider_failure_returns_clear_error_without_saving_partial_session(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    class UnconfiguredRouter:
        default_provider = "ollama"

        def resolve_name(self, *candidates: str | None) -> str:
            return next((candidate for candidate in candidates if candidate), "ollama")

        def get(self, _name: str | None = None) -> SimpleNamespace:
            raise ProviderConfigError("Provider 'openai' is not configured.")

    monkeypatch.setattr(
        "app.api.get_settings",
        lambda: Settings(_env_file=None, sqlite_fallback_path=":memory:"),
    )
    monkeypatch.setattr("app.api.get_router", UnconfiguredRouter)
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/chat",
                json={"message": "Try an unavailable model", "provider": "openai", "use_rag": False},
            )
            sessions = client.get("/api/sessions")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "provider_not_configured"
        assert sessions.status_code == 200
        assert sessions.json() == []
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_markdown_artifact_endpoint_persists_viewer_response(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    settings = Settings(_env_file=None, sqlite_fallback_path=":memory:")
    router = OfflineRouter()
    monkeypatch.setattr("app.api.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.get_router", lambda: router)
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            generated = client.post(
                "/api/artifacts",
                json={"kind": "essay", "format": "markdown", "topic": "Activation", "use_rag": False},
            )
            assert generated.status_code == 201
            result = generated.json()
            artifact_id = result["artifact"]["id"]

            saved = client.get(f"/api/artifacts/{artifact_id}")
            sessions = client.get("/api/sessions")
        assert saved.status_code == 200
        assert saved.json() == result["artifact"]
        assert saved.json()["format"] == "markdown"
        assert saved.json()["content"] == "Improve activation by reducing first-session friction [1]."
        assert len(sessions.json()) == 1
        assert sessions.json()[0]["id"] == saved.json()["session_id"]
        assert router.chat_calls
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


async def _return_transcript() -> list[tuple[str, str, str]]:
    return [
        (
            "transcript.md",
            "https://example.org/transcript",
            "---\ntitle: Activation interview\nguest: Dana Lee\n"
            "youtube_url: https://youtube.com/watch?v=abc\npublish_date: 2024-01-05\n---\n"
            "Dana Lee explains that teams improve product activation by shortening onboarding "
            "and clarifying the first value moment. (00:12:23)",
        )
    ]
