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

## Measurements from the current implementation
| Metric | Value | Definition |
|---|---|---|
| Primary documents | 4 | Curated Markdown files loaded from `knowledge_base/primary/`; excludes `README.md` and `.gitkeep`. |
| Secondary documents | 2 | Curated Markdown files loaded from `knowledge_base/secondary/`; excludes `README.md` and `.gitkeep`. |
| Total documents | 6 | Primary plus secondary curated documents loaded by the existing loader. |
| UTF-8 corpus bytes | 14,351 | Sum of on-disk byte sizes for the six curated Markdown source files only. |
| Serialized context characters | 14,474 | `len(primary_context) + len(secondary_context)` from `assemble_context_bundle()`, including group labels, source wrappers, document markdown, metadata, source links, interpretations, limitations, and blank-line separators. |
| Prompt token usage | not measured | Not captured yet because no OpenAI request was run in this task. |
| API latency | not measured | Not captured yet because no OpenAI request was run in this task. |
| API usage/cost | not measured | Not captured yet because no OpenAI request was run in this task. |

## Revisit conditions
- Revisit the architecture if the corpus grows enough that fixed inclusion becomes unwieldy or too large.
- Revisit it if request diversity starts demanding source selection that a fixed bundle cannot cover.
- Revisit it if measured token usage, latency, or review burden makes the current approach inefficient.
- Revisit it only after a measured generic-versus-contextual comparison is available.

## Current status
- The implementation includes the fixed corpus without retrieval.
- The source manifest is separate from the serialized context strings.
- No generic-versus-contextual comparison has been run yet.
- No deployment, API call, or billing event has been performed by this decision record alone.
