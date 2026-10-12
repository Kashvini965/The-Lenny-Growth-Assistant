# Manual UI & API Test Plan: The Lenny Growth Assistant

This document outlines the manual verification steps for evaluating the Lenny Growth Assistant.

---

## Pre-test Checklist
1. Ollama is running (`curl -s http://127.0.0.1:11434/api/tags` returns `llama3.2` and `nomic-embed-text`).
2. Backend is healthy (`curl -s http://127.0.0.1:8000/api/health` returns status `ok`).
3. Frontend is loaded at `http://localhost:5173`.

---

## Test Cases

### TC-01: Health & Provider Discovery
- **Action**: Check top settings bar in the web UI.
- **Expected Result**: 
  - Provider selector displays `ollama · ready`.
  - Green status dot is visible.
  - Model selector displays `llama3.2`.
  - "Use sources" checkbox is checked by default.

### TC-02: Grounded Q&A with Valid Citations
- **Action**: In the composer, send: `"What are key strategies for product market fit?"`
- **Expected Result**:
  - Assistant responds with grounded content.
  - A collapsible `<details>` element labeled **"Sources"** appears below the response.
  - Clicking "Sources" expands the list showing episode title, URL, and excerpt snippets.

### TC-03: Strict Refusal on Unsupported Topics
- **Action**: Send an out-of-scope query: `"What are the key equations in general relativity?"`
- **Expected Result**:
  - Assistant refuses to answer with factual claims: states that the transcripts do not contain this information.
  - No fabricated citations are displayed.

### TC-04: Multi-turn Follow-up Context Isolation
- **Action**: 
  1. In conversation A, ask: `"Who is Lenny Rachitsky?"`
  2. Start a **New Conversation** via the sidebar button or `Cmd/Ctrl + K`.
  3. In conversation B, ask: `"Who were we just talking about?"`
- **Expected Result**:
  - Conversation B does not have access to conversation A's history.
  - Each session maintains strictly isolated context in storage.

### TC-05: Ship 30 for 30 Skill Generation
- **Action**: Click the **"30-for-30"** button in the top navigation. Enter topic: `"Diagnosing growth plateaus"`, audience: `"startup founders"`, and submit.
- **Expected Result**:
  - A modal dialog opens showing the generated essay.
  - Contains hook, clear progression headings (`##`), bullet points, bold emphasis, and a single concrete takeaway.
  - Citation sources are attached.

### TC-06: Untrusted HTML Artifact Sandbox
- **Action**: Click **"Write an essay"**, select format **"HTML preview"**, and generate.
- **Expected Result**:
  - Artifact renders inside an `<iframe>` element.
  - Inspect iframe element: `sandbox=""` (no allow-scripts, no allow-same-origin).
  - CSP header is applied (`default-src 'none'; style-src 'unsafe-inline'`).

### TC-07: Error Resilience (Ollama Unreachable)
- **Action**: If Ollama is temporarily stopped, send a chat message.
- **Expected Result**:
  - An inline, friendly error banner appears: *"Could not reach Ollama. Is it running?"* with a **Retry** button.
  - The UI does not crash with an uncaught exception or blank screen.
