"""HTTP API routes for chat, transcript knowledge, skills, and artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import check_database, get_db
from app.errors import NotFoundError, ProviderConfigError
from app.models import Artifact
from app.providers.router import get_router
from app.schemas import (
    ArtifactOut,
    ChatRequest,
    ChatResponse,
    CreateSessionRequest,
    GenerateArtifactRequest,
    GenerateArtifactResponse,
    HealthComponent,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    KnowledgeBaseStats,
    ModelListResponse,
    PreviewResponse,
    SearchRequest,
    SearchResponse,
    SessionDetailOut,
    SessionOut,
    SkillRunRequest,
    SkillRunResponse,
    UpdateSessionRequest,
)
from app.services import artifacts, chat, knowledge, skills

api = APIRouter()


@api.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    database_ok, database_detail = check_database()
    ollama_ok, ollama_detail = await get_router().ollama_health()
    components = [
        HealthComponent(name="database", ok=database_ok, detail=database_detail),
        HealthComponent(
            name="ollama",
            ok=ollama_ok,
            detail=ollama_detail,
            url=_safe_health_url(settings.ollama_base_url),
        ),
    ]
    status = "ok" if all(component.ok for component in components) else "degraded"
    return HealthResponse(
        status=status,
        app=settings.app_name,
        version="1.0.0",
        environment=settings.environment,
        database="sqlite" if settings.is_sqlite else "postgresql",
        components=components,
        timestamp=datetime.now(timezone.utc),
    )


def _safe_health_url(value: str) -> str:
    parsed = urlsplit(value)
    netloc = parsed.netloc.rsplit("@", 1)[-1]
    return urlunsplit((parsed.scheme, netloc, parsed.path.rstrip("/"), "", ""))


@api.get("/models", response_model=ModelListResponse)
async def models() -> ModelListResponse:
    settings = get_settings()
    router = get_router()
    return ModelListResponse(
        default_provider=router.default_provider,
        embedding_provider=settings.embedding_provider,
        providers=await router.provider_infos(),
    )


@api.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[SessionOut]:
    return chat.list_sessions(db, limit, offset)


@api.post("/sessions", response_model=SessionOut, status_code=201)
def create_session(payload: CreateSessionRequest, db: Session = Depends(get_db)) -> SessionOut:
    return chat.create_session(db, payload)


@api.get("/sessions/{session_id}", response_model=SessionDetailOut)
def get_session(session_id: str, db: Session = Depends(get_db)) -> SessionDetailOut:
    return chat.get_session(db, session_id)


@api.patch("/sessions/{session_id}", response_model=SessionOut)
def update_session(
    session_id: str,
    payload: UpdateSessionRequest,
    db: Session = Depends(get_db),
) -> SessionOut:
    return chat.update_session(db, session_id, payload)


@api.delete("/sessions/{session_id}", status_code=204, response_class=Response)
def delete_session(session_id: str, db: Session = Depends(get_db)) -> Response:
    chat.delete_session(db, session_id)
    return Response(status_code=204)


@api.post("/chat", response_model=ChatResponse)
async def post_chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    return await chat.chat(db, get_settings(), get_router(), payload)


@api.post("/knowledge/ingest", response_model=IngestResponse)
async def ingest(
    payload: IngestRequest,
    db: Session = Depends(get_db),
) -> IngestResponse:
    result = await knowledge.ingest(
        db,
        get_settings(),
        get_router(),
        source=payload.source,
        url=payload.url,
        limit=payload.limit,
        force=payload.force,
    )
    return IngestResponse(**result)


@api.post("/knowledge/search", response_model=SearchResponse)
async def search(
    payload: SearchRequest,
    db: Session = Depends(get_db),
) -> SearchResponse:
    results, model = await knowledge.search(db, get_router(), payload.query, payload.top_k)
    return SearchResponse(
        query=payload.query,
        results=results,
        embedding_model=model,
        note=None if results else "No indexed transcript passages were found.",
    )


@api.get("/knowledge/stats", response_model=KnowledgeBaseStats)
def knowledge_stats(db: Session = Depends(get_db)) -> KnowledgeBaseStats:
    return knowledge.knowledge_stats(db, get_settings())


@api.post("/skills/ship-30-for-30", response_model=SkillRunResponse)
async def run_ship_30_for_30(
    payload: SkillRunRequest,
    db: Session = Depends(get_db),
) -> SkillRunResponse:
    settings = get_settings()
    if not settings.agent_skills_enabled:
        raise ProviderConfigError("The writing skill is disabled by configuration.")
    return await skills.run_ship_30_for_30(db, settings, get_router(), payload)


@api.post("/artifacts", response_model=GenerateArtifactResponse, status_code=201)
async def generate_artifact(
    payload: GenerateArtifactRequest,
    db: Session = Depends(get_db),
) -> GenerateArtifactResponse:
    return await artifacts.generate(db, get_settings(), get_router(), payload)


@api.get("/artifacts/{artifact_id}", response_model=ArtifactOut)
def get_artifact(artifact_id: str, db: Session = Depends(get_db)) -> ArtifactOut:
    artifact = db.scalar(select(Artifact).where(Artifact.id == artifact_id))
    if artifact is None:
        raise NotFoundError(f"Artifact '{artifact_id}' was not found.")
    return artifacts.artifact_out(artifact)


@api.get("/artifacts/{artifact_id}/preview", response_model=PreviewResponse)
def preview_artifact(artifact_id: str, db: Session = Depends(get_db)) -> PreviewResponse:
    return artifacts.preview(db, artifact_id)
