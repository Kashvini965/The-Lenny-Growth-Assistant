"""Application settings, loaded from environment variables / .env.

Every value here has a safe local default so that the app boots with no
configuration at all (SQLite fallback + Ollama on localhost). Cloud provider
keys are optional; when absent the provider is reported as `unconfigured`
rather than crashing.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
SKILLS_DIR = PROJECT_ROOT / "skills"


class Settings(BaseSettings):
    """Runtime configuration for the backend."""

    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Core ---------------------------------------------------------------
    app_name: str = "The Lenny Growth Assistant"
    environment: str = "development"
    log_level: str = "INFO"
    log_json: bool = True
    api_prefix: str = "/api"

    # --- Database -----------------------------------------------------------
    # Empty string => automatic SQLite fallback (see `sqlalchemy_url`).
    database_url: str = ""
    sqlite_fallback_path: str = "./data/lenny_growth.db"

    # --- CORS ---------------------------------------------------------------
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Providers ----------------------------------------------------------
    default_provider: str = "ollama"

    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.2"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_embed_timeout_seconds: float = 60.0
    ollama_chat_timeout_seconds: float = 180.0
    ollama_keep_alive: str = "30m"


    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_chat_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"

    anthropic_api_key: str = ""
    anthropic_chat_model: str = "claude-3-5-sonnet-latest"
    anthropic_base_url: str = "https://api.anthropic.com"

    # --- RAG ----------------------------------------------------------------
    embedding_provider: str = "ollama"
    embedding_dim: int = 768
    rag_top_k: int = 3
    rag_min_score: float = 0.15
    chunk_size: int = 900
    chunk_overlap: int = 150
    max_context_chars: int = 2700
    max_history_messages: int = 4
    lenny_transcripts_repo: str = "ChatPRD/lennys-podcast-transcripts"

    # --- Generation ---------------------------------------------------------
    chat_request_timeout_seconds: float = 180.0
    max_chat_message_chars: int = 8000

    # --- Agent skills -------------------------------------------------------
    agent_skills_enabled: bool = True
    agent_sdk_enabled: bool = True

    # ------------------------------------------------------------------ utils
    @field_validator("cors_origins")
    @classmethod
    def _strip_origins(cls, value: str) -> str:
        return value.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        """Resolved SQLAlchemy URL.

        * `DATABASE_URL` set and non-empty -> used verbatim (PostgreSQL).
        * otherwise -> SQLite file next to the backend, so the demo runs
          without Docker/Postgres.
        """
        url = (self.database_url or "").strip()
        if url:
            return url
        path = Path(self.sqlite_fallback_path)
        if not path.is_absolute():
            path = (BACKEND_DIR / path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path.as_posix()}"

    @property
    def is_sqlite(self) -> bool:
        return self.sqlalchemy_url.startswith("sqlite")

    @property
    def database_is_explicit(self) -> bool:
        """True when the operator explicitly configured PostgreSQL."""
        return bool((self.database_url or "").strip())

    def provider_status(self) -> dict[str, bool]:
        """Which providers are configured (key present / local always on)."""
        return {
            "ollama": True,  # local, availability probed at runtime
            "openai": bool(self.openai_api_key.strip()),
            "anthropic": bool(self.anthropic_api_key.strip()),
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """Used by tests that monkeypatch the environment."""
    get_settings.cache_clear()


# Convenience for scripts executed from the backend directory.
if os.name == "nt":  # pragma: no cover - Windows-only import sanitisation
    os.environ.setdefault("PYTHONUTF8", "1")
