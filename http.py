"""Shared HTTP helpers for provider adapters."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

import httpx

from app.errors import ProviderTimeoutError, ProviderUnavailableError
from app.logging_config import get_logger

logger = get_logger(__name__)
_shared_clients: dict[str, httpx.AsyncClient] = {}


def _safe_base_url(client: httpx.AsyncClient) -> str | None:
    base_url = getattr(client, "base_url", None)
    if base_url is None:
        return None
    parsed = urlsplit(str(base_url))
    netloc = parsed.netloc.rsplit("@", 1)[-1]
    return urlunsplit((parsed.scheme, netloc, parsed.path.rstrip("/"), "", ""))


def _log_connection_failure(
    client: httpx.AsyncClient,
    path: str,
    provider: str,
    exc: httpx.HTTPError,
) -> None:
    logger.error(
        "Provider connection failed.",
        exc_info=(type(exc), exc, exc.__traceback__),
        extra={
            "provider": provider.lower(),
            "path": path,
            "url": _safe_base_url(client),
            "reason": str(exc),
            "error_type": type(exc).__name__,
        },
    )


def _unreachable_message(provider: str) -> str:
    if provider.lower() == "ollama":
        return "Ollama isn't running. Start Ollama and try again."
    return f"Could not reach {provider}. Is it running?"


def _timeout_message(provider: str) -> str:
    if provider.lower() == "ollama":
        return "Ollama didn't respond in time. Start Ollama and try again."
    return f"{provider} request timed out."


def build_client(base_url: str, timeout: float, headers: dict[str, str] | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=base_url.rstrip("/"),
        timeout=httpx.Timeout(timeout, connect=min(10.0, timeout)),
        headers=headers or {},
    )


def start_shared_client(base_url: str, timeout: float) -> None:
    key = base_url.rstrip("/")
    if key not in _shared_clients:
        _shared_clients[key] = httpx.AsyncClient(
            base_url=key,
            timeout=httpx.Timeout(timeout, connect=min(10.0, timeout)),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )


def get_shared_client(base_url: str, timeout: float) -> httpx.AsyncClient:
    key = base_url.rstrip("/")
    return _shared_clients.get(key) or build_client(key, timeout)


async def close_shared_clients() -> None:
    clients = list(_shared_clients.values())
    _shared_clients.clear()
    for client in clients:
        await client.aclose()


async def post_json(
    client: httpx.AsyncClient,
    path: str,
    payload: dict,
    *,
    provider: str,
    timeout: float | None = None,
) -> dict:
    """POST JSON with normalised error handling.

    Every provider failure is mapped onto the app's structured error types so
    the API layer can return a consistent envelope.
    """
    try:
        response = await client.post(path, json=payload, timeout=timeout)
    except httpx.TimeoutException as exc:
        _log_connection_failure(client, path, provider, exc)
        raise ProviderTimeoutError(
            _timeout_message(provider),
            details={"provider": provider, "path": path},
        ) from exc
    except httpx.HTTPError as exc:
        _log_connection_failure(client, path, provider, exc)
        raise ProviderUnavailableError(
            _unreachable_message(provider),
            details={"provider": provider, "reason": str(exc)},
        ) from exc

    if response.status_code >= 400:
        body = _safe_body(response)
        logger.warning("%s returned %s: %s", provider, response.status_code, body[:400])
        if response.status_code in (401, 403):
            raise ProviderUnavailableError(
                f"{provider} rejected the request (auth). Check your API key.",
                code="provider_auth_error",
                details={"provider": provider, "status": response.status_code},
            )
        if response.status_code == 404:
            raise ProviderUnavailableError(
                f"{provider} endpoint/model not found.",
                details={"provider": provider, "status": 404, "body": body[:300]},
            )
        raise ProviderUnavailableError(
            f"{provider} returned an error ({response.status_code}).",
            details={"provider": provider, "status": response.status_code, "body": body[:300]},
        )

    try:
        return response.json()
    except ValueError as exc:
        raise ProviderUnavailableError(
            f"{provider} returned a non-JSON response.",
            details={"provider": provider},
        ) from exc


async def get_json(client: httpx.AsyncClient, path: str, *, provider: str, timeout: float | None = None) -> dict:
    try:
        response = await client.get(path, timeout=timeout)
    except httpx.TimeoutException as exc:
        _log_connection_failure(client, path, provider, exc)
        raise ProviderTimeoutError(
            _timeout_message(provider),
            details={"provider": provider, "path": path},
        ) from exc
    except httpx.HTTPError as exc:
        _log_connection_failure(client, path, provider, exc)
        raise ProviderUnavailableError(
            _unreachable_message(provider),
            details={"provider": provider, "reason": str(exc)},
        ) from exc
    if response.status_code >= 400:
        body = _safe_body(response)
        logger.warning("%s returned %s: %s", provider, response.status_code, body[:400])
        if response.status_code in (401, 403):
            raise ProviderUnavailableError(
                f"{provider} rejected the request (auth). Check your API key.",
                code="provider_auth_error",
                details={"provider": provider, "status": response.status_code},
            )
        if response.status_code == 404:
            raise ProviderUnavailableError(
                f"{provider} endpoint/model not found.",
                details={"provider": provider, "status": 404, "body": body[:300]},
            )
        raise ProviderUnavailableError(
            f"{provider} returned an error ({response.status_code}).",
            details={"provider": provider, "status": response.status_code, "body": body[:300]},
        )
    try:
        return response.json()
    except ValueError as exc:
        raise ProviderUnavailableError(
            f"{provider} returned a non-JSON response.",
            details={"provider": provider},
        ) from exc


def _safe_body(response: httpx.Response) -> str:
    try:
        return response.text
    except Exception:  # pragma: no cover - defensive
        return "<unreadable body>"
