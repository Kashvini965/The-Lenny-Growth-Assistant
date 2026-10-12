from __future__ import annotations

import json
import logging
import sys

from app.logging_config import JsonFormatter


def test_json_formatter_includes_database_error_context_and_traceback() -> None:
    try:
        raise RuntimeError("database offline")
    except RuntimeError:
        record = logging.LogRecord(
            name="app.database",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="Database request failed.",
            args=(),
            exc_info=sys.exc_info(),
        )
        record.database = "postgresql"
        record.database_driver = "psycopg"
        record.error_type = "OperationalError"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "Database request failed."
    assert payload["database"] == "postgresql"
    assert payload["database_driver"] == "psycopg"
    assert payload["error_type"] == "OperationalError"
    assert "database offline" in payload["exception"]
