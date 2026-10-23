# RAG decision

## Terms
- **Proposed non-RAG context injection:** fixed, deterministic inclusion of the curated corpus without query-based retrieval, keyword ranking, embeddings, or a vector store.
- **RAG:** any query-based retrieval layer, including keyword retrieval without embeddings.
- **Vector stores:** optional; they are not required for this project stage.

## Provisional position
- Keep the current implementation as fixed corpus context injection.
- The implementation loads all six curated Markdown documents in a deterministic order and serializes them into separate primary and secondary context strings.
- This gives the team a bounded, reviewable baseline for a small corpus and a two-day schedule.
- Character-limit checks are only a project guardrail; they do not prove fit inside the model token window.

## Decision factors
- **Corpus size and structure:** more documents, deeper hierarchy, or more overlap can justify retrieval later.
- **Update frequency:** if the curated Markdown set changes often, retrieval may reduce manual assembly work.
- **Request diversity:** if briefs expand beyond the fixed corpus, retrieval may improve coverage.
- **Context limits:** the current character limit guards serialization size, but it is not a token-window guarantee.
- **Implementation complexity:** the simplest architecture that keeps Patagonia facts grounded should win for this project.

## Evidence anchors
- Day 1 smoke test evidence: `docs/evidence/day1-smoke-test.md` and `docs/evidence/day1-smoke-test.json`.
- Generic-versus-contextual comparison: `docs/evaluation/generic-vs-contextual-results.md` and `docs/evaluation/email-counting-clarification.md`.
- The run artifacts and acceptance exports are preserved under `docs/evaluation/runs/20261023T021455-aab889c1/` and `docs/evidence/channel-acceptance/`.

## Measurements from the current implementation
These values come from one Day 1 Instagram smoke test and are not representative benchmarks.

| Metric | Value | Definition |
|---|---|---|
| Primary documents | 4 | Curated Markdown files loaded from `knowledge_base/primary/`; excludes `README.md` and `.gitkeep`. |
| Secondary documents | 2 | Curated Markdown files loaded from `knowledge_base/secondary/`; excludes `README.md` and `.gitkeep`. |
| Total documents | 6 | Primary plus secondary curated documents loaded by the existing loader. |
| UTF-8 corpus bytes | 14,351 | Sum of on-disk byte sizes for the six curated Markdown source files only. |
| Serialized context characters | 14,474 | `len(primary_context) + len(secondary_context)` from `assemble_context_bundle()`, including group labels, source wrappers, document markdown, metadata, source links, interpretations, limitations, and blank-line separators. |
| Returned model | gpt-5.4-mini-2026-03-17 | Model reported by the single live Instagram smoke test. |
| Input tokens | 3,683 | Input tokens reported by the single live Instagram smoke test response usage object. |
| Output tokens | 547 | Output tokens reported by the single live Instagram smoke test response usage object. |
| Total tokens | 4,230 | Combined input plus output tokens reported by the single live Instagram smoke test response usage object. |
| API latency | 6.347893500002101 seconds | End-to-end elapsed time measured for the single live Instagram smoke test request. |
| API usage or cost | not calculated | Cost remains uncalculated and was not treated as an enforced budget cap. |

## Revisit conditions
- Revisit the architecture if the corpus grows enough that fixed inclusion becomes unwieldy or too large.
- Revisit it if request diversity starts demanding source selection that a fixed bundle cannot cover.
- Revisit it if measured token usage, latency, or review burden makes the current approach inefficient.
- Revisit it only after a measured generic-versus-contextual comparison is available.

## Current status
- The implementation includes the fixed corpus without retrieval.
- The source manifest is separate from the serialized context strings.
- The generic-versus-contextual comparison has been completed and documented.
- No deployment or billing event has been performed by this decision record alone.

## Day 1 Instagram smoke test note
- The smoke test used the same fixed corpus and a single live Instagram request.
- The evidence records `gpt-5.4-mini-2026-03-17`, 3,683 input tokens, 547 output tokens, 4,230 total tokens, and 6.347893500002101 seconds of latency.
- These measurements describe one smoke test only and do not prove production fit, token-window fit, or benchmark performance.
