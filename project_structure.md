# 1. Project identity
- **Project name:** Patagonia Content Studio.
- **Type:** two-day applied R&D / educational prototype.
- **Goal:** deliver an English-only Patagonia content studio in Python/Streamlit that drafts Instagram, LinkedIn, and email newsletter content from curated Markdown knowledge bases, then routes output through human review, revision, and export without inventing facts.
- **Dates:** October 22-23, 2026.
- **Initial product:** Patagonia Men's Nano Puff Jacket, style 84212.
- **Owner-authorized demo extension (2026-10-25):** a second prepared product, Men's Torrentshell 3L Rain Jacket (85241), with explicit source filtering and separate per-product channel work. New-product live acceptance and refreshed deployment seed remain pending.
- **Canonical source:** https://www.patagonia.com/product/mens-nano-puff-insulated-jacket/84212.html
- **Market/source scope:** US website, English content.
- **Channels:** Instagram, LinkedIn, email newsletter.
- **Initial use case:** a marketing team enters a campaign brief and receives three channel-specific drafts grounded in verified product and industry sources, with human review, revision, and approval.
- **Excluded scope:** live prices, discounts, availability, unsupported performance claims, and facts from other styles or seasons.
- **Characteristics:** defined goal, limited resources, interdisciplinary work, responsibility for results, complexity, novelty, and a fixed start/end window.

# 2. Objectives (Quality / Time / Cost)
- **Quality:** outputs remain grounded in verified Patagonia source notes, channel tone is distinct per format, and reviewers can trace every significant claim back to the knowledge base.
- **Quality:** the UI makes each state obvious so the workflow is usable for non-builders and easy to demo.
- **Quality:** advisory format checks surface length and structure issues without pretending to verify factual accuracy.
- **Time:** finish a working end-to-end demo by Day 2 while keeping at most two active cards across the team and using pair/review work to avoid overload.
- **Cost:** keep the model configurable, bound generation and revision calls, and record token and usage data when the API returns it.
- **Cost:** model preset is `gpt-5.4-mini`, configurable through `OPENAI_MODEL`.
- **Cost:** the shared team API budget is USD 5 for October 22-23, 2026; this is an agreed spending budget, not an enforced cap in the code.
- **Cost:** actual measurement evidence is recorded in `rag_decision.md` and the evaluation artifacts.
- **Milestone - Day 1:** the loader, context bundle, CLI dry-run, live smoke test, and preserved evidence are complete.
- **Milestone - Day 2:** final docs, demo, presentation, and any remaining board evidence are completed or explicitly marked pending.

# 3. Stakeholder analysis
- **Quadrant mapping:** I = high interest / high influence; II = low interest / high influence; III = high interest / low influence; IV = low interest / low influence.

| Role | Interest | Influence | Quadrant | Engagement |
|---|---|---|---|---|
| Sergii, technical lead | H | H | I | Owns architecture, ingestion, context selection, OpenAI integration, pipeline integration, and delivery risk control. |
| Sandra, primary KB owner | H | H | I | Curates the primary Markdown knowledge base and channel prompt templates; pairs on claim safety and tone. |
| Martha, evaluation/usability reviewer | H | H | I | Checks content quality, usability, and whether the workflow is understandable for the team. |
| Hypothetical Patagonia marketing approver | H | H | I | Non-builder client persona; validates brand fit, factual discipline, and whether outputs are acceptable. |
| Course instructor | H | H | I | Reviews feasibility, Trello discipline, and whether the two-day scope stays realistic. |

# 4. Requirements -> implementation
- **Use case:** the team needs a small, reviewable content studio that can take verified Patagonia source material, assemble bounded context, generate channel-specific drafts, and support human approval before export.
- **Won't:** no automated social publishing.
- **Won't:** no auth or scheduling in the original MVP.
- **Baseline note:** the original MVP did not require a hosted database or remote vector service; the later owner-authorized SQLite RAG index is a separate local expansion, not the baseline.

| Must | Proposed files | Verification |
|---|---|---|
| **M1 - Both Markdown KBs ingested with source metadata** | `src/document_processor.py`, `knowledge_base/primary/`, `knowledge_base/secondary/` | Loader tests now cover 5 primary and 2 secondary documents (the baseline had 4 primary), metadata preservation, section hierarchy, and source-line tracking. |
| **M2 - Bounded deterministic context assembly using both KBs** | `src/knowledge_base.py` | Context bundle returns separate primary and secondary context strings, a source manifest, and measured corpus data with deterministic ordering. |
| **M3 - Real configurable OpenAI integration** | `src/llm_integration.py` | Live smoke test produced a real response with usage capture; offline tests cover configuration errors, sanitized failures, and no-retry behavior. |
| **M4 - Three channel templates** | `src/prompt_templates.py`, `templates/instagram.md`, `templates/linkedin.md`, `templates/email.md` | Channel templates enforce the three formats and support the evaluation comparison and format validation. |
| **M5 - CLI and web generation, feedback/revision, human approval and export** | `src/content_pipeline.py`, `src/main.py`, `app.py`, `src/ui_state.py`, `src/rag_context_provider.py`, `src/content_validation.py`, `src/source_registry.py` | CLI dry-run and Streamlit UI are implemented; per-channel workspaces, source CRUD preview/validation/hash conflict checks, the local management gate, approval/export protection, selected-view retention, and preserved acceptance evidence exist. |
| **M6 - Generic-versus-contextual evaluation** | `scripts/generic_vs_contextual_eval.py`, `src/evaluation_runner.py`, `docs/evaluation/` | The preserved six-response historical full-context comparison, scorecard, comparison report, and email-counting clarification document the non-RAG evaluation. |
| **M7 - RAG decision record and implementation notes** | `rag_decision.md`, `src/embedding_integration.py`, `src/rag_chunking.py`, `src/rag_index.py`, `src/rag_service.py`, `src/rag_retrieval.py`, `src/rag_context_provider.py`, `scripts/build_rag_index.py`, `scripts/retrieve_rag_context.py`, `app.py`, `docs/evidence/rag/` | The decision record and supporting modules capture heading-aware chunking, configurable embeddings, persistent local SQLite vectors, explicit index preview/build, retrieval provenance, and preserved RAG evidence. |
| **M8 - Planning files and board alignment** | `agents.md`, `project_structure.md`, `README.md`, `docs/evidence/` | Planning closure, evidence links, and board alignment are documented before any new development card starts. |

# 5. WBS (2 levels)
This WBS keeps the original October 22-23 plan as the baseline. The owner later reported instructor-approved weekend completion; that changes schedule context only and does not add a new deadline.

1. **Work package: Planning and source foundation**
   - **Activity 1.1 Planning alignment** - Owner: Sergii; Reviewer: Martha; Must: M8; Dependencies: none; Verification: `project_structure.md`, `agents.md`, and the board rules are aligned; planning closure precedes development cards; Day 1/Day 2 timing: D1 AM.
   - **Activity 1.2 Primary KB** - Owner: Sandra; Reviewer: Martha; Must: M1; Dependencies: none; Verification: Markdown structure, source URLs, access dates, factual grounding, and primary/secondary separation are reviewed for the primary KB; Day 1/Day 2 timing: D1 AM.
   - **Activity 1.3 Secondary KB** - Owner: Martha; Reviewer: Sandra; Must: M1; Dependencies: none; Verification: Markdown structure, source URLs, access dates, factual grounding, and primary/secondary separation are reviewed for the secondary KB; Day 1/Day 2 timing: D1 AM.
   - **Activity 1.4 Markdown ingestion** - Owner: Sergii; Reviewer: Sandra; Must: M1; Dependencies: 2 and 3; Verification: loader integration is verified when both KB folders ingest successfully with metadata preserved; Day 1/Day 2 timing: D1 PM.

2. **Work package: Core generation, context, and comparison**
   - **Activity 2.1 Context assembly and RAG assessment** - Owner: Sergii; Reviewer: Martha; Must: M2, M7; Dependencies: 4; Verification: repeatable source selection, separate primary and secondary context strings, source manifest, measured corpus data, the retrieval-backed bounded context path, and index preview/build evidence are recorded; Day 1/Day 2 timing: D1 PM.
   - **Activity 2.2 OpenAI client** - Owner: Sergii; Reviewer: Martha; Must: M3; Dependencies: none; Verification: real response, missing-key/API errors, model configuration, and usage capture when available; Day 1/Day 2 timing: D1 PM.
   - **Activity 2.3 Three channel templates** - Owner: Sandra; Reviewer: Martha; Must: M4; Dependencies: 2 and 3; Verification: Instagram, LinkedIn, and email templates enforce channel constraints and contain no unresolved placeholders; Day 1/Day 2 timing: D1 PM.
   - **Activity 2.4 Pipeline, feedback, approval and export** - Owner: Sergii; Reviewer: Sandra; Must: M5; Dependencies: 5, 6, 7; Verification: full workflow works and a draft cannot be marked approved without human action; Day 1/Day 2 timing: D2 AM.

3. **Work package: Interface, evaluation, and release**
   - **Activity 3.1 Streamlit interface** - Owner: Sergii; Reviewer: Martha; Must: M5; Dependencies: 8; Verification: loading, empty, error, success, per-channel workspace, source CRUD, RAG preview/build states, selected-view retention, and revision consistency appear in the UI; Day 1/Day 2 timing: D2 AM.
   - **Activity 3.2 Generic-versus-contextual evaluation** - Owner: Martha; Reviewer: Sandra; Must: M6; Dependencies: 6, 7, 8; Verification: preserved run artifacts, prompts, settings, raw outputs, and source-grounded review exist for all three channels; Day 1/Day 2 timing: D2 AM.
   - **Activity 3.3 Render deployment attempt and runtime verification** - Owner: Sergii; Reviewer: Martha; Must: M5, M8; Dependencies: 9; Verification: local readiness checks come first; Render deployment is attempted and runtime behavior is checked, but failure does not block final delivery; any hosted mutable source/index path would still need durable storage; Day 1/Day 2 timing: D2 PM.
   - **Activity 3.4 Final docs, demo, and presentation** - Owner: Martha; Reviewers: Sergii and Sandra; Must: M7, M8; Dependencies: 9 and 10; Verification: docs, demo, board screenshots, the five-slide presentation, and preserved evidence links are complete; Day 1/Day 2 timing: D2 PM.

# 6. Risks
| Risk | Probability | Impact | Strategy | Concrete response |
|---|---|---|---|---|
| Unsupported or stale claims | M | H | Reduction | Keep claims source-grounded, require peer review, and block approval if a statement cannot be traced to the KB. |
| API availability or cost problems | M | H | Mitigation | Keep model choice configurable, cap generation and revision calls, log usage when available, and fall back to saved comparison artifacts if the API is unstable. |
| Scope or WIP bottlenecks | H | H | Reduction | Keep only two active cards, pair on risky work, cut stretch tasks early, and protect the Day 2 demo path. |

# 7. Bridge to RAG decision
Marketing quality needs still require source-grounded content, but the architecture now supports both the historical deterministic baseline and the authorized RAG path. Streamlit uses the RAG provider for owner-facing generation, while `src.main` still exercises the full-corpus historical path for comparison and evaluation. The owner-reviewed RAG evidence now includes Instagram, LinkedIn, and email across different runs and corpus snapshots, but those examples remain owner checks rather than independent all-channel acceptance or a controlled benchmark. The generic-versus-contextual comparison remains historical non-RAG evidence; it documents the previous full-context experiment and should not be treated as RAG acceptance. The fixed post-Revise stale display was validated offline, but a new live browser revision retest was not performed. Revisit the balance between the two paths only if the corpus grows enough that fixed inclusion becomes unwieldy, request diversity outgrows the fixed bundle, retrieval blocking becomes too frequent, or the manual review burden of the current workflow becomes too high.


## Two-product demo extension

Cards 5.1 / 4.3 (UI/pipeline) and 6.1 (deployment readiness), Musts M4/M5/M7/M8: `src/product_catalog.py` owns the two profiles and source allowlists; `src/rag_index.py` filters source IDs before ranking; `src/rag_retrieval.py` requires selected-product factual evidence; `src/ui_state.py` retains product-owned channel state; `app.py` exposes selection, overview status and native animated operation panels. The seven-document corpus requires an explicit index refresh and a new validated deployment seed. Existing evidence is preserved under its original snapshots; offline product isolation is not new live or peer acceptance. Render and presentation remain separate later activities.
