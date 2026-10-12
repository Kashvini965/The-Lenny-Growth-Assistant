from __future__ import annotations

from app.config import Settings
from app.providers.router import ProviderRouter


def test_embedding_provider_uses_local_provider_when_anthropic_is_selected() -> None:
    settings = Settings(
        _env_file=None,
        embedding_provider="anthropic",
        anthropic_api_key="configured",
    )

    assert ProviderRouter(settings).embedding_provider().name == "ollama"
