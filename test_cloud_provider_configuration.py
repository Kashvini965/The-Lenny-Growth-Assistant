from __future__ import annotations

import asyncio

import httpx

from app.config import Settings
from app.providers.openai_provider import OpenAIProvider


def test_openai_requests_preserve_versioned_base_url(monkeypatch) -> None:
    requested_paths: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path.endswith("/chat/completions"):
            return httpx.Response(
                200,
                json={
                    "model": "test-chat-model",
                    "choices": [{"message": {"content": "A useful answer."}}],
                },
            )
        return httpx.Response(
            200,
            json={"data": [{"embedding": [0.1, 0.2]}]},
        )

    def mock_build_client(base_url: str, timeout: float, headers: dict[str, str]):
        return httpx.AsyncClient(
            base_url=f"{base_url.rstrip('/')}/",
            timeout=timeout,
            headers=headers,
            transport=httpx.MockTransport(respond),
        )

    monkeypatch.setattr("app.providers.openai_provider.build_client", mock_build_client)
    provider = OpenAIProvider(
        Settings(
            _env_file=None,
            openai_api_key="test-key",
            openai_base_url="https://api.example.test/v1",
        )
    )

    async def run() -> None:
        from app.providers.base import ChatMessage

        result = await provider.chat([ChatMessage(role="user", content="hello")])
        embeddings = await provider.embed(["hello"])
        assert result.content == "A useful answer."
        assert embeddings.vectors == [[0.1, 0.2]]

    asyncio.run(run())
    assert requested_paths == ["/v1/chat/completions", "/v1/embeddings"]


def test_openai_health_rejects_invalid_credentials(monkeypatch) -> None:
    def respond(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "invalid key"}})

    def mock_build_client(base_url: str, timeout: float, headers: dict[str, str]):
        return httpx.AsyncClient(
            base_url=f"{base_url.rstrip('/')}/",
            timeout=timeout,
            headers=headers,
            transport=httpx.MockTransport(respond),
        )

    monkeypatch.setattr("app.providers.openai_provider.build_client", mock_build_client)
    provider = OpenAIProvider(Settings(_env_file=None, openai_api_key="invalid-test-key"))

    available, detail = asyncio.run(provider.health())

    assert available is False
    assert detail is not None
    assert "auth" in detail.lower()


def test_openai_health_rejects_missing_chat_model(monkeypatch) -> None:
    requested_paths: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        return httpx.Response(404, json={"error": {"message": "model not found"}})

    def mock_build_client(base_url: str, timeout: float, headers: dict[str, str]):
        return httpx.AsyncClient(
            base_url=f"{base_url.rstrip('/')}/",
            timeout=timeout,
            headers=headers,
            transport=httpx.MockTransport(respond),
        )

    monkeypatch.setattr("app.providers.openai_provider.build_client", mock_build_client)
    provider = OpenAIProvider(Settings(_env_file=None, openai_api_key="test-key"))

    available, detail = asyncio.run(provider.health())

    assert available is False
    assert requested_paths == ["/v1/models/gpt-4o-mini"]
    assert detail is not None
    assert "endpoint/model not found" in detail.lower()


def test_openai_health_reports_missing_credentials_without_network_call(monkeypatch) -> None:
    def unexpected_build_client(*_args, **_kwargs):
        raise AssertionError("A provider without credentials must not make a network request.")

    monkeypatch.setattr("app.providers.openai_provider.build_client", unexpected_build_client)
    provider = OpenAIProvider(Settings(_env_file=None, openai_api_key=""))

    available, detail = asyncio.run(provider.health())

    assert available is False
    assert detail == "OPENAI_API_KEY not set"
