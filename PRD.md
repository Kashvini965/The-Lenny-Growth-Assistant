# Product requirements: The Lenny Growth Assistant

## Discovery brief

**User and problem.** Product and growth practitioners need to turn a large collection of Lenny's Podcast/Newsletter transcripts into trustworthy, actionable answers and reusable written materials. Manually searching transcripts and assembling artifacts is slow; ordinary chat can answer without showing its evidence.

**Success measures.**

- **Target Metric**: **>= 90%** of evaluation test queries receive a factually supported answer with valid, resolvable transcript citations, or an explicit rejection when the knowledge base has insufficient evidence.
- For questions with relevant indexed passages, the response includes source citations that resolve to the ingested document.
- For empty or insufficient retrieval, the application explicitly declines to make a transcript-grounded claim.
- A reviewer can start an independent chat, refresh the page, and recover its messages from persistent storage.
- An HTML artifact preview cannot execute scripts or submit forms and does not load external resources.
- The evaluator can start the local stack using one documented Compose command.

**Assumptions.**

- Users can access the public `ChatPRD/lennys-podcast-transcripts` repository or provide a public HTTP(S) transcript URL.
- Ollama is the default local model runtime; cloud providers are optional.
- Local Compose credentials are development-only. Production deployment requires managed secrets, authentication/authorization, TLS, backups, and network policies.
- There is no user identity provider in the supplied scaffold; session metadata is stored, but sessions are not user-authenticated or isolated by account.
- The linked Ship 30 for 30 guide informs high-level editorial principles. The implementation summarizes those principles rather than copying the guide.

**Included.** Responsive chat, persistent sessions/messages/artifacts, local/cloud provider routing, transcript ingestion/search/citations, the dedicated writing skill, sanitized sandboxed HTML preview, structured errors, operational documentation, and targeted automated tests.

**Excluded.** Authentication/multi-tenant access control, streaming tokens, background ingestion jobs, production deployment to a cloud provider, billing, transcript licensing enforcement, and automated evaluation of factual correctness.

## Chat workspace experience

The frontend presents the assistant as **The Lenny Growth Assistant**, a focused growth-research workspace rather than a generic chat template. Its compact searchable session rail, collapsible desktop navigation, responsive mobile drawer, actionable empty-state prompt starters, persistent provider/RAG controls, message copy/ask-again actions, and floating composer all use the existing session and chat API. Prompt starters only populate the composer; they are not example conversation data. “Ask again” creates a new chat turn and does not claim to regenerate an existing assistant message. Suggested prompts and visible controls must not imply unavailable backend capabilities.

The main workspace includes a non-interactive inline-SVG podcast/growth illustration behind the working UI. It provides a blue-white gradient, microphone, AI hub, translucent capability callouts, audio/growth motifs, and desk accessories without altering navigation, feature controls, chat state, or backend behavior. The background is decorative, hidden from assistive technology, and must not capture pointer input or create horizontal overflow at mobile widths.

## Main user flows

1. Start a chat; select an available provider; ask a question; review cited transcript passages or the explicit no-evidence response.
2. Continue in the same session; create a separate session without sharing history; return to older sessions.
3. Generate a Ship 30 for 30 essay from retrieved source passages.
4. Generate Markdown or HTML/CSS from the current conversation; view it in-app, with HTML isolated in a sandboxed iframe.
5. Ingest/refresh source documents and inspect knowledge-base status.

## Acceptance criteria

- Chat accepts a message and optional session ID/provider/model; returns saved user/assistant messages, session, citations, retrieval metadata, provider, and model.
- A session's history is only used for requests against that same session.
- No sufficiently relevant transcript matches yields an explicit unsupported-answer message, not an unsupported LLM completion.
- Provider/network errors use the documented structured error envelope.
- Transcript sources remain traceable by citation title, URL, source, snippet, and score.
- HTML preview applies server-side allowlist sanitization, CSP, and an empty iframe sandbox; active content and external fetches are blocked.
- Database migration succeeds and the application can run with PostgreSQL or the documented SQLite fallback.
- Tests cover no-evidence chat persistence, provider fallback, chunking/URL validation, and HTML sanitization.

## Risks and trade-offs

| Risk | Mitigation / trade-off |
|---|---|
| Hallucination despite retrieved context | Restrict factual answers to evidence; cite sources; decline when retrieval is below threshold. LLM output still requires human review. |
| Poor or mismatched embeddings | Persist model/dimension metadata, use cosine similarity, surface provider errors; re-ingest after changing embedding model. |
| Local latency and memory pressure | Ollama is local-first, with configurable models and timeouts; smaller models may lower answer quality. |
| Cloud cost or credential exposure | Cloud providers are opt-in and keys stay in backend environment; never send secrets to the browser. |
| Unsafe generated HTML | Bleach allowlist plus CSS sanitization, restrictive CSP, blocked network resources, and a sandboxed iframe with no script permission. |
| Public URL ingestion SSRF | Allow HTTP(S) only, reject non-public DNS/IP destinations, revalidate redirects, cap response size; deployments should also restrict egress. |
| Unauthenticated sessions | Suitable only for local/demo use. Add auth and tenant-scoped ownership before exposing to users. |
| Repository license/terms | Evaluators/operators must confirm rights and follow source repository terms before distributing ingested content. |

## Delivery status

The local source includes the frontend, FastAPI routes and services, provider adapters, PostgreSQL migration/Compose configuration, SQLite local fallback, startup documentation, and automated tests. Verification must distinguish mocked integration coverage from a real model run: tests can verify citation mapping, follow-up isolation, no-evidence behavior, provider errors, and artifact persistence without proving model quality or live Lenny transcript ingestion.

## Runtime verification boundaries

- `/api/health` reports database and Ollama health; `degraded` means one or more of those dependencies is unavailable, not that the HTTP server failed to start.
- `/api/models` reports readiness for configured providers. Chat requires a reachable provider/model; transcript ingestion and grounded retrieval additionally require an available embeddings provider and indexed transcript passages.
- Cloud keys are optional backend-only configuration. Health probes check credentials/model access, while actual generation requires an inference request and may incur provider charges.
- The environment used for local verification may not include Docker, PostgreSQL, Ollama, cloud credentials, or an indexed transcript corpus. In their absence, only migrations on the SQLite fallback, service/API tests with controlled test data, frontend build checks, and UI rendering against explicit fixtures can be claimed as verified.
- The actual runtime verification report must state which dependencies were available, whether a response came from a live model, and which external workflows remain untested. Never represent a fixture or synthetic transcript as real model/source evidence.

### Local verification snapshot (October 10, 2026)

The Vite frontend and FastAPI API both responded on `127.0.0.1` ports 5173 and 8000. Health reported a working SQLite database and degraded Ollama readiness; the corpus contained no documents or chunks. `/api/models` reported Ollama unavailable and both cloud providers unconfigured. A live session could be created, fetched, and deleted. Disabling transcript grounding returned the backend's explicit policy message, not a generated answer. A grounded chat request returned HTTP 503 with Ollama unavailable. No live inference, transcript citations, essay generation, artifact generation, PostgreSQL/Compose, or cloud requests were verified. Backend tests passed (25); frontend typecheck and production build passed. Automated tests use controlled data/provider behavior and are not evidence of live model output.
