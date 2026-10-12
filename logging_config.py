"""Structured application logging.

A single `configure_logging()` call sets up the root logger, and `get_logger`
is used everywhere else. Logs are human-readable in development and can be
emitted as JSON by setting `LOG_JSON=1` (structured logging for deployments).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    """Minimal structured formatter - one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D102
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in (
            "request_id",
            "session_id",
            "provider",
            "model",
            "path",
            "url",
            "reason",
            "error_type",
            "status",
            "attempt",
            "warmup",
            "duration_ms",
            "database",
            "database_driver",
            "pull_command",
            "installed",
            "loaded",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO", *, json_logs: bool | None = None) -> None:
    """Idempotently configure the root logger."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(stream=sys.stdout)
    use_json = (
        json_logs
        if json_logs is not None
        else os.getenv("LOG_JSON", "").strip().lower() in {"1", "true"}
    )
    if use_json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Quiet noisy third-party loggers.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module logger. Logging is configured at app startup."""
    return logging.getLogger(name)
