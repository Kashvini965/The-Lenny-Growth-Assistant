"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from time import perf_counter

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api
from app.config import get_settings
from app.database import dispose_engine, get_engine
from app.errors import register_exception_handlers
from app.logging_config import configure_logging, get_logger
from app.providers.base import ChatMessage
from app.providers.ollama_provider import OllamaProvider
from app.providers.http import close_shared_clients, start_shared_client

logger = get_logger(__name__)


async def _warm_ollama_models(settings) -> None:
    provider = OllamaProvider(settings)
    async def run_warmup(name: str, operation, model: str) -> None:
        started = perf_counter()
        try:
            await operation
        except Exception as exc:
            logger.exception(
                "Ollama startup warmup failed.",
                extra={
                    "provider": "ollama",
                    "model": model,
                    "warmup": name,
                    "reason": str(exc),
                    "error_type": type(exc).__name__,
                },
            )
        else:
            logger.info(
                "Ollama startup warmup completed.",
                extra={
                    "provider": "ollama",
                    "model": model,
                    "warmup": name,
                    "duration_ms": int((perf_counter() - started) * 1000),
                },
            )

    await run_warmup(
        "embedding",
        provider.embed(["warm up"], model=settings.ollama_embed_model),
        settings.ollama_embed_model,
    )
    await run_warmup(
        "chat",
        provider.chat(
            [ChatMessage(role="user", content="Reply OK.")],
            model=settings.ollama_chat_model,
            temperature=0,
            max_tokens=4,
        ),
        settings.ollama_chat_model,
    )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.log_json)
    get_engine()
    start_shared_client(settings.ollama_base_url, settings.ollama_chat_timeout_seconds)
    warmup_task = asyncio.create_task(_warm_ollama_models(settings), name="ollama-model-warmup")
    try:
        yield
    finally:
        warmup_task.cancel()
        try:
            await warmup_task
        except asyncio.CancelledError:
            pass
        await close_shared_clients()
        dispose_engine()


settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
register_exception_handlers(app)
app.include_router(api, prefix=settings.api_prefix)


@app.get("/health", include_in_schema=False)
async def root_health():
    from app.api import health

    return await health()
