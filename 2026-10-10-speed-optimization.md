# Work Session Log: Speed Optimization & Local Model Performance

**Date:** 2026-10-10  
**Focus:** Response latency reduction, embedding caching, CPU/GPU Ollama mode configuration, and timeout tuning.

---

## 1. Objectives & Scope
- Mitigate high latency when running local Ollama inference on consumer hardware.
- Reduce vector retrieval overhead for query embedding and cosine similarity search.
- Tune timeouts across backend HTTP adapters to prevent 504 Gateway Timeouts under load.
- Ensure streaming/batching behavior remains stable.

---

## 2. Work Completed
1. **Ollama Provider Optimization:**
   - Evaluated Ollama CPU vs GPU execution flags. Configured OLLAMA_TIMEOUT_SECONDS=120 in .env.example to accommodate cold starts.
   - Set optimal context window limits (MAX_CONTEXT_CHARS=6000) to avoid bloating local model KV-cache.
2. **Embedding & Retrieval Pipeline:**
   - Implemented cosine similarity calculation over memory-mapped vectors.
   - Added bounded top-K retrieval (RAG_TOP_K=5) with minimum relevance score cutoff (RAG_MIN_SCORE=0.15).
   - Skipped duplicate text embeddings during ingestion by content hashing.
3. **Frontend Responsiveness:**
   - Added optimistic UI loading states and generation indicators in App.tsx.
   - Prevented double submissions while requests are in flight.

---

## 3. Failed Attempts & Resolutions
1. **Issue:** Ollama hanging indefinitely on GPU offload when CUDA runtime was missing.
   - *Detail:* Certain local machines with incomplete CUDA installs hung on layer allocation.
   - *Resolution:* Verified fallback to CPU mode (CUDA_VISIBLE_DEVICES=-1, OLLAMA_LLM_LIBRARY=cpu) gracefully executes inference without process crashes.
2. **Issue:** Large transcript chunk sizes exceeding local context window, causing degraded answer quality.
   - *Detail:* 2000-character chunks caused truncation of conversation history in llama3.2 (3B).
   - *Resolution:* Tuned chunk size to 900 characters with 150-character overlap (CHUNK_SIZE=900, CHUNK_OVERLAP=150), improving precision and retrieval speed.

---

## 4. Verification Record
- Pytest suite passes: 26 passed.
- Retrieval benchmark: Query vectorization and ranking executes under 150ms for indexed chunks.

---

## 5. Notes on Raw Transcripts & Sanitization
*Sanitized work log. Stripped local filesystem paths, environment secrets, and machine identifiers.*
