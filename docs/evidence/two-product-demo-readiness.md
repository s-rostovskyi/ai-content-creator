# Two-product demo readiness — 2026-10-25

Scope: owner-authorized UI/pipeline extension on cards 5.1 / 4.3 and 6.1, Musts M4/M5/M7/M8. Implementation and offline verification are complete; live second-product acceptance, named peer review and Render deployment are not claimed.

## Prepared products and boundaries

- Nano Puff men's US style 84212 retains its existing four primary/two secondary source assignments.
- Torrentshell 3L men's US style 85241 uses `knowledge_base/primary/torrentshell_85241.md`, captured from the official product page on 2026-10-25. Its profile excludes Nano Puff's mixed brand/editorial, care and competitor references.
- Source IDs are filtered before vector scoring/top-k, then lexical/factual ranking and context-budget selection apply. Missing product facts or absence of selected-product facts in the final context blocks retrieval. Explicit RAG is required for prepared product sessions.
- Product state includes channel sessions, working edits, feedback, approval/export records, attempts and selected workspace views. Earlier in-memory UI sessions are assigned to their existing product before further requests; historical exported artifacts are unchanged.
- Trusted generation/revision instructions, retrieval queries/provenance and new JSON exports retain product identity. Unassigned uploads remain excluded until deliberately assigned in `src/product_catalog.py`.

## Offline verification

The affected-area run passed **186 tests, 1 skipped** in 146.82 seconds. Files: `tests/test_app.py`, `tests/test_demo_access.py`, `tests/test_ui_state.py`, `tests/test_rag_index.py`, `tests/test_rag_retrieval.py`, `tests/test_rag_service.py`, `tests/test_content_pipeline.py`, `tests/test_prompt_templates.py`, `tests/test_campaign_brief.py`, `tests/test_document_processor.py`, `tests/test_source_registry.py`, `tests/test_knowledge_base.py`.

A later targeted legacy-session/product-switch regression run passed **2 tests, 52 deselected** in 13.35 seconds. These overlap the affected-area coverage; do not sum repeated tests as independent evidence. The one skip is the existing Windows symlink-creation limitation. The full repository suite was not run in this task. Tests suppress real `.env` loading and use injected fake clients/vectors where embedding/generation behavior is exercised.

Coverage includes perfect-similarity foreign-source exclusion, missing-facts preflight rejection before embedding, retained limitations, product-specific briefs, separate editor/approval/export state, product identity in new exports, and native operation-status complete/error states.

A separate local browser preview (real `.env` loading disabled, no API calls) confirmed the product selector, the Torrentshell default brief, corpus counts 5 primary/2 secondary and disabled generation against the stale real index. This is not a live generation or new-product acceptance test. `git diff --check` passed.

## Real-corpus offline build plan

- New corpus snapshot: `e2ab88df5679fb9accb6937fa9b7c94ece8d30fc2b962ee82841f9385e6c202e`.
- Configured model used for explicit offline planning: `text-embedding-3-small`.
- Chunks: 23; primary 17, secondary 6.
- Reusable embeddings: 20; pending: 3; planned batches: 1; pending input characters: 6074. Characters are not token or price estimates.
- The real active index and the earlier deployment seed remain unchanged with SHA-256 `430ab2e8bff73c972155c97ebfd4ac73bc859e9a656a43af0a2bebce6ad4a845`; both belong to the previous corpus. No embeddings were rebuilt or copied into a fake deployment index.

## Required next steps

1. Owner opens Index, previews the current snapshot, reviews the charge notice and explicitly builds/updates. Confirm Ready and the actual build result; plan counts are not completed-call measurements.
2. Run an owner-reviewed second-product scenario, inspect sources and limitations, approve/export only the exact saved revision and preserve the new evidence under its actual snapshot. Existing Nano Puff evidence remains historical.
3. Package the compatible real index offline into a new deliberate seed path; validate it before publication. Do not publish the old stale seed or synthetic test vectors.
4. Proceed to Render configuration and clean hosted runtime verification, with shared-password access, source mutations/builds disabled and the approved compatible seed. Publication/deployment still require their separate owner authorization.

## Changed file scope for this extension

New: `src/product_catalog.py`, `knowledge_base/primary/torrentshell_85241.md`, this readiness note.

Backend/state: `src/rag_index.py`, `src/rag_retrieval.py`, `src/rag_context_provider.py`, `src/content_pipeline.py`, `src/prompt_templates.py`, `src/campaign_brief.py`, `src/ui_state.py`, `scripts/retrieve_rag_context.py`.

UI: `app.py` (selector, overview and native animated status).

Tests: `tests/test_app.py`, `tests/test_ui_state.py`, `tests/test_rag_retrieval.py`, `tests/test_content_pipeline.py`, `tests/test_campaign_brief.py`, `tests/test_document_processor.py`, `tests/test_knowledge_base.py`.

Current-scope docs: `README.md`, `agents.md`, `project_structure.md`, `rag_decision.md`. Other uncommitted bootstrap/password/UI changes from preceding tasks are preserved; no staging, commit, push, dependency install, paid API call or deployment was performed.

## Subsequent owner-authorized live preparation

The later live build completed successfully: 23 chunks, 20 reused embeddings, 3 new embeddings, 1 API batch, 1,583 prompt/total tokens, 2.634059 seconds. The compatible two-product seed was packaged offline and validated. See `docs/evidence/rag/two-product-index-build.json` (repository-relative path). Earlier deferred/stale statements above describe the preceding checkpoint; they are superseded for index preparation only. Hosted runtime and second-product generation acceptance are not established by this build.
