from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import httpx
import pytest

from app.api import _safe_health_url
from app.config import Settings
from app.errors import ProviderTimeoutError, ProviderUnavailableError
from app.logging_config import JsonFormatter
from app.providers import ollama_provider
from app.providers.http import get_json
from app.providers.ollama_provider import OllamaProvider


def test_embed_batch_falls_back_when_batch_endpoint_is_missing(monkeypatch) -> None:
    calls: list[str] = []

    async def fake_post_json(_client, path, _payload, *, provider, timeout=None):
        calls.append(path)
        if path == "/api/embed":
            raise ProviderUnavailableError("Not found", details={"status": 404})
        return {"embedding": [0.1, 0.2]}

    monkeypatch.setattr(ollama_provider, "post_json", fake_post_json)

    provider = OllamaProvider(Settings(_env_file=None))
    vectors = asyncio.run(provider._embed_batch(None, "embed-model", ["text"]))

    assert vectors == [[0.1, 0.2]]
    assert calls == ["/api/embed", "/api/embeddings"]


def test_embed_batch_does_not_retry_legacy_endpoint_after_timeout(monkeypatch) -> None:
    calls: list[str] = []

    async def fake_post_json(_client, path, _payload, *, provider, timeout=None):
        calls.append(path)
        raise ProviderTimeoutError("Ollama timed out")

    monkeypatch.setattr(ollama_provider, "post_json", fake_post_json)
    monkeypatch.setattr(ollama_provider.asyncio, "sleep", AsyncMock())
    provider = OllamaProvider(Settings(_env_file=None))

    async def run() -> None:
        await provider._embed_batch(None, "embed-model", ["text"])

    with pytest.raises(ProviderTimeoutError, match="Ollama is taking too long"):
        asyncio.run(run())

    assert calls == ["/api/embed", "/api/embed"]


def test_embed_retries_once_after_timeout(monkeypatch) -> None:
    calls = 0

    async def fake_post_json(_client, _path, _payload, *, provider, timeout=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ProviderTimeoutError("request timed out")
        return {"embeddings": [[0.1, 0.2]]}

    monkeypatch.setattr(ollama_provider, "post_json", fake_post_json)
    monkeypatch.setattr(ollama_provider.asyncio, "sleep", AsyncMock())
    provider = OllamaProvider(Settings(_env_file=None))

    vectors = asyncio.run(provider._embed_batch(None, "embed-model", ["text"]))

    assert vectors == [[0.1, 0.2]]
    assert calls == 2
    ollama_provider.asyncio.sleep.assert_awaited_once_with(0.5)


def test_embed_second_timeout_uses_friendly_message(monkeypatch) -> None:
    async def fake_post_json(_client, _path, _payload, *, provider, timeout=None):
        raise ProviderTimeoutError("Raw transport timeout details")

    monkeypatch.setattr(ollama_provider, "post_json", fake_post_json)
    monkeypatch.setattr(ollama_provider.asyncio, "sleep", AsyncMock())
    provider = OllamaProvider(Settings(_env_file=None))

    with pytest.raises(ProviderTimeoutError, match="Ollama is taking too long. Please try again.") as raised:
        asyncio.run(provider._embed_batch(None, "embed-model", ["text"]))

    assert "Raw transport timeout details" not in str(raised.value)
    assert raised.value.details["attempts"] == 2


def test_embed_batch_keeps_model_warm_for_both_endpoints(monkeypatch) -> None:
    payloads: list[tuple[str, dict]] = []

    async def fake_post_json(_client, path, payload, *, provider, timeout=None):
        payloads.append((path, payload))
        if path == "/api/embed":
            return {}
        return {"embedding": [0.1, 0.2]}

    monkeypatch.setattr(ollama_provider, "post_json", fake_post_json)
    provider = OllamaProvider(Settings(_env_file=None))

    vectors = asyncio.run(provider._embed_batch(None, "embed-model", ["text"]))

    assert vectors == [[0.1, 0.2]]
    assert payloads == [
        ("/api/embed", {"model": "embed-model", "input": ["text"], "keep_alive": "30m"}),
        ("/api/embeddings", {"model": "embed-model", "prompt": "text", "keep_alive": "30m"}),
    ]


def test_chat_stream_sends_keep_alive_context_limit_and_yields_tokens(monkeypatch) -> None:
    request_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        request_payloads.append(json.loads(request.content))
        return httpx.Response(
            200,
            content=(
                b'{"message":{"content":"A grounded"}}\n'
                b'{"message":{"content":" answer [1]"},"done":true}\n'
            ),
        )

    client = httpx.AsyncClient(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr(ollama_provider, "get_shared_client", lambda *_args: client)
    provider = OllamaProvider(Settings(_env_file=None))

    async def collect() -> list[str]:
        try:
            return [
                token
                async for token in provider.chat_stream(
                    [ollama_provider.ChatMessage(role="user", content="Question")],
                    model="llama3.2",
                    max_tokens=400,
                )
            ]
        finally:
            await client.aclose()

    assert asyncio.run(collect()) == ["A grounded", " answer [1]"]
    assert request_payloads[0]["stream"] is True
    assert request_payloads[0]["keep_alive"] == "30m"
    assert request_payloads[0]["options"]["num_ctx"] == 4096
    assert request_payloads[0]["options"]["num_predict"] == 400


def test_embed_caches_repeated_identical_texts(monkeypatch) -> None:
    calls: list[list[str]] = []

    @asynccontextmanager
    async def fake_build_client(*_args, **_kwargs):
        yield object()

    async def fake_embed_batch(_client, _model, texts):
        calls.append(texts)
        return [[float(len(calls)), 0.2] for _ in texts]

    monkeypatch.setattr(ollama_provider, "build_client", fake_build_client)
    provider = OllamaProvider(Settings(_env_file=None))
    monkeypatch.setattr(provider, "_embed_batch", fake_embed_batch)

    async def run():
        first = await provider.embed(["same question", "other question"])
        second = await provider.embed(["same question"])
        return first, second

    first, second = asyncio.run(run())

    assert first.vectors == [[1.0, 0.2], [1.0, 0.2]]
    assert second.vectors == [[1.0, 0.2]]
    assert calls == [["same question", "other question"]]


def test_ollama_timeouts_are_configurable(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_EMBED_TIMEOUT_SECONDS", "75")
    monkeypatch.setenv("OLLAMA_CHAT_TIMEOUT_SECONDS", "210")

    settings = Settings(_env_file=None)

    assert settings.ollama_embed_timeout_seconds == 75
    assert settings.ollama_chat_timeout_seconds == 210


def test_ollama_timeout_defaults(monkeypatch) -> None:
    monkeypatch.delenv("OLLAMA_EMBED_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("OLLAMA_CHAT_TIMEOUT_SECONDS", raising=False)

    settings = Settings(_env_file=None)

    assert settings.ollama_embed_timeout_seconds == 60
    assert settings.ollama_chat_timeout_seconds == 180


@pytest.mark.parametrize(
    ("installed", "missing"),
    [
        ([{"name": "nomic-embed-text:latest"}], "llama3.2"),
        ([{"name": "llama3.2:latest"}], "nomic-embed-text"),
        ([], "llama3.2, nomic-embed-text"),
    ],
)
def test_health_reports_missing_required_models(monkeypatch, installed, missing) -> None:
    @asynccontextmanager
    async def fake_build_client(*_args, **_kwargs):
        yield object()

    async def fake_get_json(*_args, **_kwargs):
        return {"models": installed}

    monkeypatch.setattr(ollama_provider, "build_client", fake_build_client)
    monkeypatch.setattr(ollama_provider, "get_json", fake_get_json)
    provider = OllamaProvider(Settings(_env_file=None))

    available, detail = asyncio.run(provider.health())

    assert available is False
    assert detail is not None
    assert missing in detail
    assert f"ollama pull {missing.split(', ')[0]}" in detail


def test_health_reports_ready_when_chat_and_embedding_models_are_installed(monkeypatch) -> None:
    @asynccontextmanager
    async def fake_build_client(*_args, **_kwargs):
        yield object()

    async def fake_get_json(*_args, **_kwargs):
        return {"models": [{"name": "llama3.2:latest"}, {"name": "nomic-embed-text:latest"}]}

    monkeypatch.setattr(ollama_provider, "build_client", fake_build_client)
    monkeypatch.setattr(ollama_provider, "get_json", fake_get_json)
    provider = OllamaProvider(Settings(_env_file=None))

    available, detail = asyncio.run(provider.health())

    assert available is True
    assert detail is None


def test_health_details_distinguishes_installed_from_loaded_models(monkeypatch) -> None:
    async def fake_get_json(_client, path, *, provider, timeout=None):
        if path == "/api/tags":
            return {"models": [{"name": "llama3.2:latest"}, {"name": "nomic-embed-text:latest"}]}
        return {"models": [{"name": "nomic-embed-text:latest"}]}

    monkeypatch.setattr(ollama_provider, "get_json", fake_get_json)
    provider = OllamaProvider(Settings(_env_file=None))

    ok, detail, models = asyncio.run(provider.health_details())

    assert not ok
    assert detail == "Required Ollama model(s) are not loaded: llama3.2."
    assert models == [
        {"name": "llama3.2", "installed": True, "loaded": False, "pull_command": None},
        {"name": "nomic-embed-text", "installed": True, "loaded": True, "pull_command": None},
    ]


def test_health_reports_friendly_message_when_ollama_is_unreachable(monkeypatch) -> None:
    @asynccontextmanager
    async def fake_build_client(*_args, **_kwargs):
        yield object()

    async def fake_get_json(*_args, **_kwargs):
        raise ProviderUnavailableError(
            "Could not reach Ollama.",
            details={"reason": "All connection attempts failed"},
        )

    monkeypatch.setattr(ollama_provider, "build_client", fake_build_client)
    monkeypatch.setattr(ollama_provider, "get_json", fake_get_json)
    provider = OllamaProvider(Settings(_env_file=None))

    available, detail = asyncio.run(provider.health())

    assert available is False
    assert detail == "Ollama isn't running. Start Ollama and try again."


def test_ollama_connection_failure_is_structured_in_logs(caplog) -> None:
    async def run() -> None:
        def fail_request(_request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("All connection attempts failed", request=_request)

        async with httpx.AsyncClient(
            base_url="http://localhost:11434",
            transport=httpx.MockTransport(fail_request),
        ) as client:
            await get_json(client, "/api/tags", provider="Ollama")

    with caplog.at_level(logging.ERROR, logger="app.providers.http"):
        with pytest.raises(ProviderUnavailableError, match="Ollama isn't running"):
            asyncio.run(run())

    record = next(record for record in caplog.records if record.name == "app.providers.http")
    payload = JsonFormatter().format(record)
    assert record.provider == "ollama"
    assert record.url == "http://localhost:11434"
    assert record.reason == "All connection attempts failed"
    assert record.error_type == "ConnectError"
    assert "All connection attempts failed" in payload


def test_health_url_hides_credentials_and_query_parameters() -> None:
    assert (
        _safe_health_url("http://user:password@localhost:11434/api?token=secret#fragment")
        == "http://localhost:11434/api"
    )


def test_http_provider_errors_identify_invalid_credentials_and_missing_models() -> None:
    async def check(status_code: int) -> ProviderUnavailableError:
        response = httpx.Response(status_code, json={"error": "provider error"})

        class FakeClient:
            async def post(self, *_args, **_kwargs):
                return response

        with pytest.raises(ProviderUnavailableError) as raised:
            await ollama_provider.post_json(
                FakeClient(),
                "/chat/completions",
                {},
                provider="Cloud",
            )
        return raised.value

    unauthorized = asyncio.run(check(401))
    assert unauthorized.code == "provider_auth_error"
    assert unauthorized.details["status"] == 401

    missing_model = asyncio.run(check(404))
    assert "endpoint/model not found" in str(missing_model)
    assert missing_model.details["status"] == 404


def test_http_provider_timeouts_are_structured() -> None:
    class TimedOutClient:
        async def post(self, *_args, **_kwargs):
            raise httpx.ReadTimeout("timed out")

    async def run() -> None:
        with pytest.raises(ProviderTimeoutError, match="timed out"):
            await ollama_provider.post_json(
                TimedOutClient(),
                "/chat/completions",
                {},
                provider="Cloud",
            )

    asyncio.run(run())
