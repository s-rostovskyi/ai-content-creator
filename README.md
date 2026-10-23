# Patagonia Content Studio

Patagonia Content Studio is an unofficial educational prototype that combines company brand-content generation with a multi-channel content pipeline. It is scoped to one product and one market slice for the course project: Patagonia Men's Nano Puff Jacket, style 84212, on the US site in English.

The goal is to help a marketing team move from a curated source snapshot to channel-ready drafts for Instagram, LinkedIn, and email, then through human review, feedback, manual editing, explicit approval, and Markdown/JSON export. It is a publication-ready export workflow, not automatic posting.

## What the workflow does

1. Review the curated Markdown knowledge base snapshot.
2. Prepare or edit one shared campaign brief.
3. Generate independent channel drafts.
4. Review reviewer notes and source provenance.
5. Revise or manually edit when needed.
6. Explicitly approve the exact saved revision.
7. Export approved content to Markdown plus a JSON sidecar.

The source review is manual snapshot analysis, not live monitoring. The secondary knowledge base is historical context and competitor/industry reference material; it is not treated as current market telemetry.

## Source management

The source manager supports preview-before-write CRUD for create, edit, and delete. It validates Markdown structure and provenance, detects hash conflicts against the previewed snapshot, and preserves the current campaign work when a conflict blocks a write. The local management gate is disabled by default; `SOURCE_MANAGEMENT_ENABLED=true` is required to allow validated mutations. When the gate is off, the UI is read-only.

## Setup

Install dependencies with the active Python interpreter:

```bash
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set the application configuration:

```ini
OPENAI_API_KEY=
OPENAI_MODEL=
OPENAI_EMBEDDING_MODEL=
SOURCE_MANAGEMENT_ENABLED=
```

Application configuration names:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_EMBEDDING_MODEL`
- `SOURCE_MANAGEMENT_ENABLED`

`OPENAI_API_KEY` is the application key used by the OpenAI client inside this repo. It is separate from Codex authentication and should stay local. `OPENAI_MODEL` selects the generation model at runtime. `OPENAI_EMBEDDING_MODEL` selects the embedding model for RAG indexing and retrieval. `SOURCE_MANAGEMENT_ENABLED` is optional and keeps the source manager read-only unless it is exactly `true`. The repo-root `.env` is loaded with `override=False`: existing process environment values take precedence. Restart Streamlit after changing local credentials or startup configuration.

## Run the app

Start the Streamlit UI:

```bash
python -m streamlit run app.py
```

Run the CLI in dry-run mode to build prompts without loading credentials or calling the API:

```bash
python -m src.main --channel instagram --brief "..." --dry-run
```

Run the CLI in live review mode after configuration is in place:

```bash
python -m src.main --channel instagram --brief "..."
```

The CLI shares pipeline primitives with the UI, but `src.main` currently uses full-corpus context without the RAG provider. Streamlit uses explicit RAG retrieval; the separate retrieval CLI below exercises retrieval without content generation. CLI live mode shows the draft, reviewer notes, and explicit review actions; quit never implies approval or export.

## RAG workflow

Fresh clones do not contain a `.rag/` index. RAG generation and revision therefore require an explicit index preparation step before the retrieval-backed path is usable.

Run the RAG index planner in dry-run mode by default:

```bash
python scripts/build_rag_index.py
```

Run the live index build only after the explicit charge confirmation path in the UI or when you intentionally want to write the local SQLite vector index:

```bash
python scripts/build_rag_index.py --live
```

Run the retrieval planner in dry-run mode by default:

```bash
python scripts/retrieve_rag_context.py --channel instagram --brief "..."
```

Run live retrieval only when you want the retrieval result and optional evidence file:

```bash
python scripts/retrieve_rag_context.py --channel instagram --brief "..." --live --save-evidence <path>
```

The retrieval script keeps `--save-evidence` live-only. The Streamlit UI previews and builds the index explicitly, reuses compatible embeddings, and blocks missing, stale, or incompatible indexes instead of silently falling back to full-context generation. Any hosted deployment would need durable storage for the managed sources, the `.rag/` index, and exported artifacts; this repository does not claim one.

## Evaluation commands

Run the generic-versus-contextual comparison in dry-run mode by default:

```bash
python scripts/generic_vs_contextual_eval.py
```

Run the six live comparison requests only when you explicitly want them:

```bash
python scripts/generic_vs_contextual_eval.py --live
```

Use `--runs-dir` if you want a different output base under `docs/evaluation/runs/`. The six-response experiment is the historical full-context, non-RAG comparison; it is preserved for evaluation and does not validate the new RAG pipeline.

## Tests

Run the offline suite with a fresh temporary base directory:

```bash
python -m pytest -q -p no:cacheprovider --basetemp <fresh temp dir>
```

## Operational notes

- Session memory is browser-session scoped only; refreshing the page does not preserve state, and native rerenders can reset scroll position.
- Switching channels restores that channel's own draft, editor buffers, revision state, approval state, export record, attempt count, and selected Draft/Edit/Review workspace view.
- Replacing the shared brief requires explicit confirmation if any channel already has work.
- Per-channel request limits are enforced by the pipeline; a failed revision still consumes the attempt allowance.
- Format checks are advisory. They help reviewers catch length and structure problems, but they do not verify factual accuracy, brand fit, or publication readiness.
- Approval and export remain explicit human actions.
- The UI uses the shared brief plus channel-specific workspaces; stale content is invalidated when the channel or brief changes.
- No silent full-context fallback is exposed in the RAG UI; blocked retrieval stays blocked until the index is repaired or refreshed.

## Evidence and references

- Channel acceptance evidence: [docs/evidence/channel-acceptance/README.md](docs/evidence/channel-acceptance/README.md)
- RAG acceptance evidence: [docs/evidence/rag/acceptance/README.md](docs/evidence/rag/acceptance/README.md)
- Earlier retrieval evidence: [docs/evidence/rag/packability-20261023T104924560Z.json](docs/evidence/rag/packability-20261023T104924560Z.json)
- Earlier retrieval evidence: [docs/evidence/rag/packability-fixed-20261023T112803662Z.json](docs/evidence/rag/packability-fixed-20261023T112803662Z.json)
- Generic-versus-contextual comparison report: [docs/evaluation/generic-vs-contextual-results.md](docs/evaluation/generic-vs-contextual-results.md)
- Email counting clarification: [docs/evaluation/email-counting-clarification.md](docs/evaluation/email-counting-clarification.md)
- Independent non-RAG ratings by Sandra, with rationale and original Trello comment: [evaluation scorecard](docs/evaluation/generic-vs-contextual-scorecard.md). Martha's independent ratings remain pending.
- Incremental source/index refresh verification: [source-refresh-verification.md](docs/evidence/rag/source-refresh-verification.md)

Observed format issues in the preserved comparison report:
- Generic LinkedIn is below the 120-word minimum.
- Both email variants remain below the 150-word body minimum under the clarified counting convention.
- The comparison is one qualitative sample per condition and channel; it does not prove uniqueness or complete all independent reviews.


## Preserved RAG owner checks

The [RAG acceptance record](docs/evidence/rag/acceptance/README.md) preserves exact approved Markdown/JSON pairs, copy fingerprints, retrieval provenance, model usage and limitations:

| Channel | Preserved owner workflow | Result and boundary |
|---|---|---|
| Instagram | RAG generation -> manual notes correction -> approval -> export | Revision 3; earlier corpus snapshot `93499726...`. This is not a live model-revision test. |
| LinkedIn | RAG generation -> live RAG revision using prior copy and human feedback -> approval -> export | Revision 2; 129 words meets the channel's 120-200 range but misses the feedback request of 130-160 by one word. The final revision's metadata is preserved. |
| Email newsletter | RAG generation -> manual copy/notes correction -> approval -> export | Revision 3; subject 39/50 characters, preheader 63/90, final body 157 words. Initial generated body was 140 words and failed the minimum; compliance was achieved through human editing. |

LinkedIn and email use the corrected corpus snapshot `4984775f...`; Instagram remains tied to its recorded earlier snapshot. Full snapshot identities and measurements are in the linked acceptance record. These examples demonstrate owner-run workflows across separate runs/snapshots, not a controlled RAG benchmark, independent all-channel acceptance, or proof of improved accuracy/cost.

Reviewer notes required correction of unused facts and source URLs. The retrieval source manifest records context supplied to the model, which can include sources not used in the final copy; it is not a list of claims actually made. Human review remains necessary.

The incremental index refresh reused 17 embeddings and recomputed 3 in one batch (1634 tokens), then the owner confirmed Ready and an offline plan of 20 reusable/0 missing/0 batches. The [refresh record](docs/evidence/rag/source-refresh-verification.md) preserves its scope; historical evidence was not rewritten.

The stale Review display immediately after Revise was fixed by reading the current draft after processing the revision form. Offline regressions cover immediate revision/provenance consistency, one revision operation, and failure preservation. A new live browser revision solely to retest this fix has not been performed; native rerenders may still reset scroll position.

## Status

Implemented behavior includes Markdown ingestion, deterministic context assembly, OpenAI integration, channel templates, CLI dry-run/live review, Streamlit drafting and revision, validation, approval, export, guarded source CRUD, explicit RAG index preview/build, retrieval-backed context, and preserved evaluation artifacts.

Latest independently executed offline suite after the Review-panel revision fix: **239 passed, 1 skipped** in 121.56 seconds. The skipped test requires Windows symlink creation unavailable in the verification environment. The focused source-discovery/registry run was separately reported as 18 passed, 1 skipped; these are distinct runs, not additive totals.

Not deployed: there has been no production deployment from this repo. Remaining course work, if any, should be tracked on the board rather than implied by the codebase.
