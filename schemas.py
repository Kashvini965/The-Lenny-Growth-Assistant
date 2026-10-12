"""Pydantic schemas shared by the API layer."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProviderName = Literal["ollama", "openai", "anthropic"]
MessageRole = Literal["user", "assistant", "system"]
ArtifactKind = Literal["report", "essay", "html", "code"]
ArtifactFormat = Literal["markdown", "html"]


# --------------------------------------------------------------------------- #
# Chat
# --------------------------------------------------------------------------- #
class Citation(BaseModel):
    """A retrieved transcript passage backing part of an answer."""

    index: int = Field(description="1-based citation number used in the answer [1], [2]...")
    doc_id: str
    chunk_id: str
    title: str
    url: str
    source: str
    guest: str | None = None
    youtube_url: str | None = None
    chunk_index: int | None = None
    timestamp: str | None = None
    published_at: str | None = None
    snippet: str
    score: float


class CreateSessionRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    provider: ProviderName | None = None
    model: str | None = Field(default=None, max_length=128)
    use_rag: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateSessionRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    provider: ProviderName | None = None
    model: str | None = Field(default=None, max_length=128)
    use_rag: bool | None = None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    role: MessageRole
    content: str
    provider: str | None = None
    model: str | None = None
    latency_ms: int | None = None
    citations: list[Citation] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict, alias="message_metadata")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class SessionOut(BaseModel):
    id: str
    title: str
    provider: str
    model: str | None
    use_rag: bool
    message_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    last_message_preview: str | None = None


class SessionDetailOut(SessionOut):
    messages: list[MessageOut] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    session_id: str | None = Field(default=None, description="Existing session, else a new one is created.")
    provider: ProviderName | None = None
    model: str | None = Field(default=None, max_length=128)
    use_rag: bool | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    stream: bool = False

    @field_validator("message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value.strip()


class ChatResponse(BaseModel):
    session: SessionOut
    user_message: MessageOut
    assistant_message: MessageOut
    citations: list[Citation] = Field(default_factory=list)
    retrieval: RetrievalInfo
    provider: str
    model: str


class RetrievalInfo(BaseModel):
    used: bool
    top_k: int
    results: int
    best_score: float | None = None
    sufficient: bool = True
    note: str | None = None
    embedding_model: str | None = None


# --------------------------------------------------------------------------- #
# Models / providers
# --------------------------------------------------------------------------- #
class ProviderInfo(BaseModel):
    name: str
    configured: bool
    available: bool
    kind: Literal["local", "cloud"]
    chat_model: str
    embed_model: str | None = None
    detail: str | None = None


class ModelListResponse(BaseModel):
    default_provider: str
    embedding_provider: str
    providers: list[ProviderInfo]


# --------------------------------------------------------------------------- #
# Artifacts
# --------------------------------------------------------------------------- #
class GenerateArtifactRequest(BaseModel):
    session_id: str | None = None
    kind: ArtifactKind = "report"
    format: ArtifactFormat = "markdown"
    topic: str | None = Field(default=None, max_length=400)
    prompt: str | None = Field(default=None, max_length=8000)
    provider: ProviderName | None = None
    model: str | None = Field(default=None, max_length=128)
    use_rag: bool = True
    word_target: int | None = Field(default=None, ge=200, le=4000)

    @field_validator("topic", "prompt")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return value.strip() if value else value


class ArtifactOut(BaseModel):
    id: str
    session_id: str
    message_id: str | None = None
    kind: str
    title: str
    format: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    word_count: int = 0


class GenerateArtifactResponse(BaseModel):
    artifact: ArtifactOut
    citations: list[Citation] = Field(default_factory=list)
    retrieval: RetrievalInfo
    provider: str
    model: str


class PreviewResponse(BaseModel):
    """Sanitised HTML preview payload for the sandboxed iframe."""

    artifact_id: str
    title: str
    html: str
    sandbox: str
    csp: str
    warnings: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Knowledge base
# --------------------------------------------------------------------------- #
class IngestRequest(BaseModel):
    source: Literal["seed", "lenny-podcast", "lenny-newsletter", "url"] = "seed"
    url: str | None = None
    limit: int = Field(default=5, ge=1, le=50)
    force: bool = False


class IngestResponse(BaseModel):
    status: str
    documents_ingested: int
    chunks_created: int
    skipped: int
    embedding_model: str | None
    duration_ms: int
    errors: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchHit(BaseModel):
    chunk_id: str
    doc_id: str
    title: str
    url: str
    source: str
    guest: str | None = None
    youtube_url: str | None = None
    chunk_index: int | None = None
    timestamp: str | None = None
    score: float
    content: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchHit]
    embedding_model: str | None = None
    note: str | None = None


class KnowledgeBaseStats(BaseModel):
    documents: int
    chunks: int
    embedded_chunks: int
    sources: dict[str, int]
    embedding_model: str | None = None
    last_ingest_at: datetime | None = None
    ready: bool = False


# --------------------------------------------------------------------------- #
# Skills
# --------------------------------------------------------------------------- #
class SkillInfo(BaseModel):
    name: str
    title: str
    description: str
    word_target: int
    version: str
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    source_grounded: bool = True


class SkillRunRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=400)
    session_id: str | None = None
    audience: str = Field(default="product leaders", max_length=200)
    key_points: list[str] = Field(default_factory=list)
    provider: ProviderName | None = None
    model: str | None = Field(default=None, max_length=128)
    word_target: int = Field(default=1250, ge=600, le=2500)
    use_rag: bool = True


class SkillRunResponse(BaseModel):
    skill: str
    title: str
    markdown: str
    word_count: int
    outline: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    retrieval: RetrievalInfo
    provider: str
    model: str
    grounded: bool


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #
class HealthComponent(BaseModel):
    name: str
    ok: bool
    detail: str | None = None
    url: str | None = None
    latency_ms: int | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "error"]
    app: str
    version: str
    environment: str
    database: str
    components: list[HealthComponent]
    timestamp: datetime
