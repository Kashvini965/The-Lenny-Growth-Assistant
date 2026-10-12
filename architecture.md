# Architecture

## Components

- `frontend/`: Vite + React + TypeScript SPA. `src/api.ts` owns API transport/types and reads `VITE_API_BASE_URL`. `src/App.tsx` binds The Lenny Growth Assistant chat, searchable/collapsible session navigation, prompt starters, message actions, provider settings, citations, and writing/artifact flows to the existing API. `src/WorkspaceBackground.tsx` is a decorative inline-SVG scene mounted behind the main workspace; it makes no API calls and uses no external image assets. `src/styles.css` owns visual layering, responsive behavior, and reduced-motion behavior.
- `backend/app/main.py`: FastAPI app, CORS, error handlers, lifespan, and router setup.
- `backend/app/api.py`: HTTP endpoints and Pydantic contracts.
- `backend/app/services/chat.py`: session CRUD and persisted chat turns.
- `backend/app/services/knowledge.py`: GitHub/public-URL ingestion, chunking, embeddings, cosine retrieval, citations, and corpus statistics.
- `backend/app/services/agent.py`: Claude Agent SDK orchestration with one read-only transcript-search MCP tool.
- `backend/app/services/skills.py`: source-grounded Ship 30 for 30 essay workflow.
- `backend/app/services/artifacts.py`: artifact generation and HTML/CSS sanitization/preview preparation.
- `backend/app/providers/`: provider adapters and central router for Ollama, OpenAI, and Anthropic.
- `backend/app/models.py` and `backend/migrations/versions/0001_initial.py`: SQLAlchemy entities and initial Alembic schema.

## Persistence model

`chat_sessions` has a one-to-many relationship with `messages` and `artifacts`. Each chat session has its own provider, model, RAG setting, metadata, count, and timestamps. `messages` stores role, body, model/provider, latency, citations, metadata, and timestamp. `artifacts` are attached to sessions. `transcript_docs` store source URL/title/hash and ingestion metadata; `transcript_chunks` store ordered text and JSON embeddings; `ingest_runs` record ingestion summaries.

JSON columns keep the schema portable between SQLite fallback and PostgreSQL. PostgreSQL is the Compose/default handoff target. Schema changes must be made through Alembic migrations; `Base.metadata.create_all` is used only in isolated tests.

## API and request flow

Application routes are prefixed with `/api`. See the route table in the root README and generated OpenAPI at `/docs`.

1. `POST /chat` validates the request, resolves the session/provider, embeds the user question, searches indexed chunks, and filters by `RAG_MIN_SCORE`. Retrieved passage text is passed to generation up to `MAX_CONTEXT_CHARS` (default 6,000); citations retain compact source previews and chunk IDs.
2. With no sufficiently relevant evidence, the service stores and returns an explicit no-evidence response without calling a chat model.
3. With evidence, it builds a transcript-only prompt, passes prior messages from this session only, calls the selected provider, then commits both messages and session metadata.
4. Anthropic chat can run through the Claude Agent SDK; its only allowed MCP tool searches transcript passages. Ollama/OpenAI use the shared provider router directly.
5. Every assistant turn returns retrieval metadata and citations. Provider errors are mapped into the common API error envelope.

The standalone health response combines database connectivity and Ollama readiness; it can report `degraded` while the HTTP API itself remains usable. `/api/models` reports provider configuration/readiness independently. Ollama readiness checks the configured chat and embedding models. OpenAI and Anthropic readiness probes verify the configured chat model through their model APIs without running generation. These probes contact providers and can add several seconds to health/model endpoints when Ollama is unavailable. Actual chat, embedding, and agent calls can still fail later with structured authentication, not-found, timeout, or unavailable errors.

## Ingestion and retrieval

The configured source defaults to `ChatPRD/lennys-podcast-transcripts`. Ingestion reads the repository's Markdown/text tree, or one explicit URL; documents are normalized, hashed, split into overlapping word chunks, embedded in batches, and stored with their origin URLs. Existing unchanged URLs are skipped unless forced. The URL path validates public addresses/redirects and caps the response size.

Retrieval embeds each query, computes cosine similarity over stored vectors, and returns top-k results. This is a portable baseline for the demo, not a large-scale vector database; move to PostgreSQL pgvector or a managed vector index if corpus size/latency requires it. Re-ingest data when changing embedding models.

## Agent layer architecture and provider routing

The application implements a dual-mode agent layer:
1. **Claude Agent SDK (`claude_agent_sdk`)**: When `ANTHROPIC_API_KEY` is provided and `AGENT_SDK_ENABLED=true`, requests are routed to the Claude Agent SDK in `backend/app/services/agent.py`. The agent is given an in-process MCP tool (`search_transcripts`) to retrieve and cite transcript passages autonomously.
2. **Local Ollama Provider Router**: Local Ollama runs without cloud credentials. Because the Claude Agent SDK requires active Anthropic API credentials and cannot communicate directly with local Ollama, the application routes local requests through its dedicated `ProviderRouter` in `backend/app/services/chat.py`. The router provides identical behavioral guarantees: it executes vector retrieval, enforces strict transcript grounding, attaches structured episode/chunk citations, and declines unsupported questions with the exact same refusal logic.

`DEFAULT_PROVIDER` chooses the default chat provider; request/session provider/model fields can override it. Ollama is local and does not need an API key. OpenAI/Anthropic require backend environment keys. The UI presents the provider-reported configured/available status and the selected provider/model. Chat does not switch providers implicitly after an inference error. `EMBEDDING_PROVIDER` chooses embeddings; Anthropic is explicitly routed to Ollama because its provider adapter does not implement embeddings, and an unconfigured embedding selection falls back to Ollama. Provider keys are never returned by `/models` or sent to the frontend.

## Artifact security

Generated HTML/CSS is untrusted. Preview sanitization uses Bleach's tag/attribute/protocol allowlists plus TinyCSS2 parsing to retain only qualified CSS rules and allowed declarations. An iframe sandbox with no permissions and a CSP deny scripts, forms, embeds, external resources, and network connections. The front end must not render artifact HTML in its own DOM.

## Deployment topology

`docker-compose.yml` starts PostgreSQL, Ollama, a model-pull initializer, FastAPI, and the built frontend. Named volumes persist PostgreSQL and Ollama data. The backend waits for PostgreSQL and successful model pulls; the frontend waits for backend health. Local development can instead leave `DATABASE_URL` blank for SQLite, apply the Alembic migration, and run Uvicorn and Vite separately. Compose credentials are local-development defaults, not production secrets.

## Operational boundaries

The demo has no authentication, user identity, rate limiting, background worker, or production secret manager. Add authentication and tenant-aware queries before shared deployment. Public URL ingestion should be paired with egress controls in a hosted environment. Provider status reflects configured/readiness probes and does not guarantee inference success, groundedness, or response quality. Automated tests use controlled data and mocked provider calls; they do not prove that external services, credentials, transcript repository ingestion, or live model quality are available in a given runtime.

## Latest local verification (October 10, 2026)

The app was started locally with Uvicorn on `127.0.0.1:8000`; the already-running Vite frontend responded on `127.0.0.1:5173`. API health, provider models, knowledge statistics, and session listing returned HTTP 200. SQLite was healthy and the initial Alembic migration was already at head. Ollama was unreachable, neither cloud provider was configured, and the knowledge index held zero documents/chunks. A session create/read/delete lifecycle succeeded. A grounded chat request failed with HTTP 503 because the configured local provider was unavailable; no real model generation, transcript citations, writing generation, artifact generation, PostgreSQL, or Compose workflow was verified.

Backend `python -m pytest -q` passed all 25 tests. Frontend `npm run typecheck` and `npm run build` passed. The frontend package defines no separate test/lint commands. These test results include controlled provider and transcript fixtures and do not demonstrate runtime access to an AI provider or live transcript corpus.
