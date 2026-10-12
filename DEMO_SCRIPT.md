# 2-3 Minute Live Demo Script: The Lenny Growth Assistant

**Audience**: Evaluator / Engineering Hiring Team  
**Demonstrator**: Candidate / Engineer  
**Stack**: Local Ollama (`llama3.2` + `nomic-embed-text`) + PostgreSQL/SQLite + FastAPI + React/TypeScript

---

## 0:00 - 0:45: The Problem & The Solution
> *"Hi everyone. Product and growth leaders listen to hundreds of hours of Lenny's Podcast and read countless newsletter issues, but finding exact frameworks and quotes when making strategy decisions is painful. Generic AI assistants hallucinate and cannot cite exact sources.*
> 
> *The **Lenny Growth Assistant** solves this with a grounded RAG architecture: it ingests real transcripts from Lenny's podcast repository, creates dense vector embeddings locally, and enforces strict citations. If a concept isn't supported in the transcripts, it explicitly declines to answer rather than fabricating facts."*

---

## 0:45 - 1:45: Live Demo on Local Ollama
> *"Let's see it in action running completely locally on my machine without any cloud API keys.*
> 
> 1. **Grounded Q&A with Citations**:
>    - *I'll open the web UI at `http://localhost:5173`.*
>    - *Notice the top bar: the provider shows **Ollama · Ready** with model **llama3.2**, and source grounding toggle is ON.*
>    - *I'll ask: **'What did Lenny and guests discuss about product market fit?'***
>    - *Within seconds, the assistant synthesizes key points and displays clickable source citations linking directly to the episode transcript and chunk.*
> 
> 2. **Refusal on Unsupported Questions**:
>    - *Now let's ask an out-of-scope question: **'What is quantum computing error correction?'***
>    - *Instead of guessing, the assistant cleanly informs us: 'I can't answer that from the transcript knowledge base yet' — preserving trust.*
> 
> 3. **Ship 30 for 30 Skill & Sandboxed Artifacts**:
>    - *Next, I'll click **'30-for-30'** in the top action bar and enter the topic: **'Diagnosing early user churn'**.*
>    - *The dedicated writing skill extracts the core lesson from the transcripts, crafts a hook, clear headings, bulleted insights, and an actionable takeaway in an editorial format.*
>    - *We can also generate an HTML preview, which renders in an untrusted iframe with strict CSP, blocking external scripts and tracking."*

---

## 1:45 - 2:30: Technical Architecture & Core Trade-off
> *"Let's talk about the architecture and one key technical trade-off:
> 
> - **Architecture**: FastAPI backend with Pydantic v2 schemas and SQLAlchemy supporting PostgreSQL (and local SQLite fallback). Vector embeddings use `nomic-embed-text` (768 dimensions) with cosine distance matching.
> - **Technical Trade-off: Agent Layer SDK Routing vs Local Ollama**:
>   - *The assignment specifies the **Claude Agent SDK**. However, that SDK requires Anthropic API credentials and cannot communicate directly with local Ollama.*
>   - *Rather than faking or failing when no cloud keys are configured, our architecture implements an elegant dual-mode agent routing: when `ANTHROPIC_API_KEY` is present, it uses the Claude Agent SDK with an MCP `search_transcripts` tool; when running locally on Ollama, it routes through our internal `ProviderRouter` with the exact same vector retrieval, citation grounding, and strict refusal guarantees.*
> - **Technical Trade-off: Local vs. Cloud LLM**:
>   - *Running local Ollama (`llama3.2`) provides **100% data privacy** and **zero API costs**, which is great for confidential company data.*
>   - *However, local CPU/GPU execution involves latency and context length limits compared to frontier models like Claude 3.5 Sonnet. To mitigate this without coupling, we built an abstracted **ProviderRouter**: you can switch to Anthropic or OpenAI by simply setting an environment variable with zero code modifications."*

---

## 2:30: Closing
> *"The repository includes one-command startup scripts (`start.sh` and `start.ps1`), Docker Compose, complete unit tests, and thorough documentation. Thank you!"*
