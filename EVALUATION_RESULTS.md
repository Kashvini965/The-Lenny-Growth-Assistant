# 10-Question Evaluation Benchmark & Results

Evaluation conducted against local Ollama (`llama3.2` + `nomic-embed-text`) with grounded transcript retrieval.

---

## Benchmark Results Table

| # | Question / Request | Category | Expected Behavior | Actual Result | Status |
|---|---|---|---|---|---|
| 1 | "What did Lenny and guests discuss about product market fit?" | In-Scope Q&A | Synthesizes insights and provides episode citations | Detailed answer generated citing Adam Grenier and index transcripts with 5 citations. | **PASS** |
| 2 | "How should an early-stage founder decide on their north star metric?" | In-Scope Q&A | Provides grounded metric advice with citations | Answer delivered with framework breakdown and cited transcript chunks. | **PASS** |
| 3 | "What are the most common reasons user retention drops after signup?" | In-Scope Q&A | Summarizes retention levers citing episodes | Extracted onboarding and retention insights with source citations. | **PASS** |
| 4 | "Can you give me 2 specific tactics from the transcripts for pricing changes?" | In-Scope Q&A | Specific tactics with episode references | Returned concrete pricing change tactics with episode references. | **PASS** |
| 5 | "What did Lenny say about transitioning from IC product manager to VP?" | In-Scope Q&A | Leadership transitions grounded in interviews | Detailed management transition points with citation list. | **PASS** |
| 6 | Follow-up: "Could you summarize the previous advice in 2 bullet points?" | Follow-Up | Maintains session conversation context | Accurately condensed the previous answer into 2 bullet points within the session context. | **PASS** |
| 7 | "What are the mathematical equations for quantum entanglement?" | Out-of-Scope (Refusal) | Explicitly refuses to answer from transcripts | Cleanly responded that the transcript knowledge base does not cover quantum entanglement. Zero hallucinations. | **PASS** |
| 8 | "Who won the 2024 Olympic men's 100-meter dash?" | Out-of-Scope (Refusal) | Explicitly refuses to answer | Refused: indicates this is not covered in Lenny podcast transcripts. | **PASS** |
| 9 | "Run Ship 30 for 30 skill on diagnosing growth plateaus" | Dedicated Skill | Structured essay ~1,250 words with hook, headings, and takeaway | Generated structured essay with hook, `##` headings, bullet points, and specific action takeaway. | **PASS** |
| 10 | "Generate an HTML summary artifact on activation rate best practices" | Artifact Generation | Generates valid HTML rendered in sandboxed iframe with CSP | HTML generated with inline styles, sanitized server-side, rendered with `sandbox=""` and strict CSP. | **PASS** |

---

## Evaluation Summary
- **Total Test Cases**: 10
- **Passed**: 10 / 10
- **Success Rate**: **100%** (exceeds the 90% target metric specified in `PRD.md`)
