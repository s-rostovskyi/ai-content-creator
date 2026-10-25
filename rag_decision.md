# RAG decision

## Terms
- **Historical non-RAG baseline:** fixed, deterministic inclusion of the curated corpus without query-based retrieval, keyword ranking, embeddings, or a vector store.
- **RAG:** any query-based retrieval layer, including keyword retrieval without embeddings.
- **Vector stores:** optional; they are not required for the project baseline, but the implemented RAG path uses a local SQLite vector index.

## Historical non-RAG rationale
- The original recommendation was to keep the first implementation as fixed corpus context injection.
- That baseline was appropriate for the small, reviewable corpus and the two-day schedule.
- The generic-versus-contextual six-response experiment is preserved as historical non-RAG evidence. It compares the older full-context backend against curated prompts; it does not validate the new RAG pipeline.
- Character-limit checks were always a project guardrail; they never proved fit inside the model token window.

## Authorized transition
- The owner later authorized local integration of the RAG path while preserving the historical non-RAG baseline for comparison.
- The implemented RAG system adds heading-aware chunking, applicable limitation capture, configurable OpenAI embeddings, a persistent local SQLite vector index, an explicit build/preview flow, and retrieval-backed generation and revision.
- The Streamlit UI now shows retrieval status, preview/build controls, and retrieved provenance instead of silently falling back to full-context generation.

## Current tradeoffs
- **Durability:** mutable sources and the `.rag/` index require durable local or hosted storage; a fresh clone still needs explicit index preparation before RAG generation is usable.
- **Blocking behavior:** missing, stale, or incompatible indexes stop RAG generation rather than falling back silently, which is safer but introduces an extra operational step.
- **Bounded context:** retrieved context stays capped and factual-first, but a tight top-k or similarity threshold can omit useful material.
- **Operational complexity:** the RAG path adds preview/build orchestration, evidence artifacts, and a second failure surface, even though it improves traceability and reuse when the index is current.

## Evidence anchors
- RAG acceptance evidence: `docs/evidence/rag/acceptance/README.md`.
- Earlier retrieval evidence: `docs/evidence/rag/packability-20261023T104924560Z.json` and `docs/evidence/rag/packability-fixed-20261023T112803662Z.json`.
- Generic-versus-contextual comparison: `docs/evaluation/generic-vs-contextual-results.md` and `docs/evaluation/email-counting-clarification.md`.
- Sandra's independent ratings are recorded in `docs/evaluation/generic-vs-contextual-scorecard.md` for the historical six-response non-RAG run; Martha's separate ratings remain pending.
- The comparison artifacts remain historical non-RAG evidence, not acceptance for the new RAG path.

## Historical Day 1 full-context smoke test
These measurements come from the historical full-context Instagram smoke test preserved in `docs/evidence/rag/acceptance/README.md`. They describe one request from the old backend, not the current RAG path.

| Metric | Value | Definition |
|---|---|---|
| Primary documents | 4 | Curated Markdown files loaded from `knowledge_base/primary/`; excludes `README.md` and `.gitkeep`. |
| Secondary documents | 2 | Curated Markdown files loaded from `knowledge_base/secondary/`; excludes `README.md` and `.gitkeep`. |
| Total documents | 6 | Primary plus secondary curated documents loaded by the existing loader. |
| UTF-8 corpus bytes | 14,351 | Sum of on-disk byte sizes for the six curated Markdown source files only. |
| Serialized context characters | 14,474 | `len(primary_context) + len(secondary_context)` from `assemble_context_bundle()`, including group labels, source wrappers, document markdown, metadata, source links, interpretations, limitations, and blank-line separators. |
| Returned model | gpt-5.4-mini-2026-03-17 | Model reported by the live Instagram smoke test response usage object. |
| Input tokens | 3,683 | Input tokens reported by the live Instagram smoke test response usage object. |
| Output tokens | 547 | Output tokens reported by the live Instagram smoke test response usage object. |
| Total tokens | 4,230 | Combined input plus output tokens reported by the live Instagram smoke test response usage object. |
| API latency | 6.347893500002101 seconds | End-to-end elapsed time measured for the live Instagram smoke test request. |
| API usage or cost | not calculated | Cost remains uncalculated and was not treated as an enforced budget cap. |

## Current RAG evidence and refresh measurements
- Owner-reviewed RAG examples exist for Instagram, LinkedIn, and email across different runs and corpus snapshots. These are owner checks, not independent all-channel peer acceptance or a controlled benchmark.
- LinkedIn demonstrates one live RAG revision using prior copy and human feedback.
- Email records a failed 140-word generated body followed by manual editing to the approved 157-word body.
- The incremental source refresh reused 17 embeddings and recomputed 3, advancing from corpus snapshot `9349972665c952782b93afde17efc583f4f577019709d36d43b35d0523cf1e20` to `4984775f808b507cc6c77b5394d5e730a314e80a7da19da1ada8bc0cd1bcb531`; the refresh record preserves both snapshot identities.
- The latest independently executed offline suite reported alongside this work was 239 passed, 1 skipped.

## Decision criteria
- The original six-document corpus did not require vector RAG for the MVP; fixed corpus context injection was enough for that schedule.
- The later transition was justified by authorized mutable sources and query-based retrieval, not by a claim of higher accuracy or lower cost.
- The concrete criteria now favoring the RAG path are corpus size, source-update churn, query diversity, bounded context and latency, and implementation complexity.
- The RAG path keeps context bounded and provenance explicit, but it also adds preview/build orchestration and an extra failure surface.

## Current status
- The implemented RAG path is local, explicit, and gated by an index readiness check.
- The historical full-context backend remains available for comparison and evaluation.
- Historical acceptance boundaries remain the owner-run Instagram, LinkedIn, and email examples above; they are not independent all-channel peer acceptance.
- Streamlit uses the RAG provider; `src.main` still uses full-corpus context for the historical CLI path.
- No deployment or billing event has been performed by this decision record alone.

## Future revisit conditions
- The historical generic-versus-contextual comparison already exists and remains non-RAG evidence.
- A future revisit should use fresh RAG measurements such as refresh cadence, blocked retrieval rate, chunk reuse, latency, token usage, source-update churn, and manual repair burden on representative prompts.
- The decision can be revisited if the measured RAG workflow becomes slower, less stable, or harder to review than the current approach.

## Day 1 Instagram smoke test note
- The smoke test used the same fixed corpus and a single live Instagram request.
- The evidence records `gpt-5.4-mini-2026-03-17`, 3,683 input tokens, 547 output tokens, 4,230 total tokens, and 6.347893500002101 seconds of latency.
- These measurements describe one smoke test only and do not prove production fit, token-window fit, or benchmark performance.
