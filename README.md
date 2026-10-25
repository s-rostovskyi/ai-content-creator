# Patagonia Content Studio

Patagonia Content Studio is an unofficial educational prototype that combines company brand-content generation with a multi-channel content pipeline. The Streamlit demo offers two prepared products on the US site in English: Men's Nano Puff Jacket (84212) and Men's Torrentshell 3L Rain Jacket (85241). The original course baseline and preserved live acceptance evidence concern Nano Puff.

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

## Studio navigation

The shared overview shows index readiness, corpus-wide primary/secondary source counts, selected product style, the loaded channel and each channel's status for the active product. Once a draft exists it also shows the saved revision, context mode, advisory format result and remaining generation attempts. Model, snapshot and index paths are under **System details**.

- **Campaign** starts with the prepared product selector, then contains brief preparation and compact campaign controls beside the Draft/Edit/Review workspace. Loading and generation remain explicit actions.
- **Sources** filters the corpus and displays one selected document in a bounded reader. Source create/edit/delete controls are grouped under **Manage sources** and retain the existing mutation gate.
- **Index** contains offline inspection/preview and the last build result. Builds require enabled source management and explicit charge confirmation; read-only deployments can inspect a preview without building.

Navigation within the same browser session preserves channel work, saved revisions, editor buffers, feedback and each channel's workspace view. A full browser refresh/reconnection can still lose session state; native rerenders do not guarantee scroll-position retention.

## Two prepared products

`src/product_catalog.py` defines the two supported product profiles, default briefs and explicit source assignments. Nano Puff keeps its four primary/two secondary source assignments. Torrentshell uses its dedicated official-product snapshot only; the mixed Nano Puff brand/editorial, repair and competitor documents are deliberately excluded. Primary/secondary counts in the overview describe the entire corpus, not how many documents a request retrieved. System details and the source reader show assignments.

Switching products saves/restores each product's channel sessions, editor buffers, feedback, approvals, export records and workspace views within the browser session. Loading a campaign and generating remain separate explicit actions. Preparation angles use the selected product's features, rather than reusing Nano Puff's stuffsack, insulation or care language.

The product's source allowlist is applied **before cosine ranking and top-k selection** in the same SQLite index. Retrieval blocks when the dedicated product facts are missing or no selected-product fact fits the evidence budget. Product identity appears in the trusted generation/revision instructions, query, retrieval provenance and new JSON exports. Prepared product sessions cannot silently fall back to full-corpus context. Older artifacts without product identity remain historical records; they are not relabeled or rewritten.

For retrieval-only inspection, use `python scripts/retrieve_rag_context.py --product torrentshell_85241 --channel instagram --brief "Introduce the rain shell"`. This is an offline planner unless `--live` is explicitly added. Omitting `--product` retains the retrieval CLI's legacy unscoped mode; `src.main` is also the historical unscoped full-context path. Use Streamlit for the prepared-product demo.

Adding the Torrentshell document changes the global corpus snapshot. The old index and deployment seed must be refreshed/repackaged explicitly before the new corpus can generate on Render. No automatic embedding repair occurs. Current two-product verification is offline; previous owner-approved live exports remain Nano Puff evidence. New uploads are visible to the source browser but are excluded from prepared-product retrieval until deliberately assigned in the catalogue. This is a two-product demo, not an automatic product-onboarding system.

Generation, revision and index builds display native animated status panels with elapsed work represented as running/completed/error states, not invented percentages or progress estimates. They describe the operation actually being awaited. Completion means the operation returned successfully, not that content was factually approved; format checks remain advisory.

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

The retrieval script keeps `--save-evidence` live-only. The Streamlit UI previews and builds the index explicitly, reuses compatible embeddings, and blocks missing, stale, or incompatible indexes instead of silently falling back to full-context generation. Durable hosted source editing would need persistent storage for sources, the index and exports. The free read-only demo instead uses the prepared-seed recovery path below; no hosted deployment has yet been verified.

### Offline seed for a temporary Render demo

Card 6.1 / Musts M5, M8: package the existing compatible index without loading credentials or making embedding calls:

```bash
python scripts/package_rag_index_seed.py --seed-path deploy/rag_index_seed.sqlite3 --embedding-model text-embedding-3-small --vector-dimensions 1536
```

This performs a logical copy of validated corpus/vector records into a fresh SQLite file, excluding deleted pages and unrelated database payloads. It refuses an existing destination; choose a new filename when replacing a seed. The active index is never modified by packaging. The seed is a deliberate deployment artifact outside ignored `.rag/`, containing public KB text and vectors, not generation history or secrets. Inspect and approve it separately before Git publication. Regenerate it offline after changing the canonical corpus or embedding configuration.

Opt in at startup with `RAG_INDEX_BOOTSTRAP_SEED_PATH=deploy/rag_index_seed.sqlite3`, `OPENAI_EMBEDDING_MODEL=text-embedding-3-small` and `RAG_INDEX_VECTOR_DIMENSIONS=1536`. Relative seed paths resolve against the repository root; override dimensions if the prepared embeddings use another dimension. No `.env` is read by the packaging/bootstrap service or command. Normal application startup retains its existing repo-root `.env` behavior. With no seed-path setting, local startup is unchanged.

Before readiness checks, startup preserves a compatible runtime index or validates and atomically restores the seed to `.rag/rag_index.sqlite3`. Missing, corrupt, stale, model/dimension/version-mismatched seeds block startup when restoration is needed; they never cause an automatic paid rebuild or full-context fallback. The SQLite file is portable across Windows/Linux; runtime paths are resolved on the destination host. A compatible runtime index can be reused even if the seed is unavailable.

Free-host files are ephemeral: restarts/redeploys can discard runtime index and exports. The approved seed must travel with each deployment so restoration is offline; download exports before restart. Hosted source mutation/index management must remain disabled (`SOURCE_MANAGEMENT_ENABLED=false`). This is a read-only-source demo, not durable hosted CRUD. Render startup/port configuration is prepared in `render.yaml` and `scripts/render_start.py`; publication and hosted verification remain pending. Follow [the Render runbook](docs/deployment/render.md); no deployment is claimed here.

### Shared-password demo access

For the hosted demo, set `DEMO_ACCESS_ENABLED=true` and a strong, unique `DEMO_PASSWORD` privately in Render Environment. Never commit the password or use an API key as the password. Local behavior is unchanged when the gate is disabled. When enabled without a nonblank password, the app blocks access.

The gate runs before index bootstrap, corpus loading and application controls. Login uses a password field and server-side constant-time comparison; the submitted password is removed from session state. A session-bound verifier allows reruns without retaining the plaintext password. Password changes invalidate existing authentication on the next rerun. Sign out clears campaign/editor state as well as authentication; reconnecting or refreshing can require login again.

Five failed attempts trigger a one-minute per-session cooldown. After waiting, refresh/reconnect the page if the button is still disabled; there is no automatic timer or sleeping server thread. This is a shared demo password, not individual user accounts, a global brute-force defense or a global API-spend cap. Share the link/password only with intended reviewers and disable the service after the demonstration if it is no longer needed. Keep `SOURCE_MANAGEMENT_ENABLED=false` on the hosted demo; the password does not authorize public source mutations or index builds.

### Render startup configuration

`render.yaml` is a reproducible Blueprint reference: Python 3.14.7, Free Web Service, Frankfurt, `main`, manual deploys, and Streamlit health checks. When using the dashboard form already in progress, copy these settings rather than creating a second service. The file does not automatically apply to a manually configured service.

Build: `python -m pip install -r requirements.txt`. Start: `python scripts/render_start.py`.

The guarded start command requires password access, disables hosted source/index mutation, validates the packaged seed even if an existing runtime index is compatible, and restores/reuses the runtime index offline **before the HTTP server starts**. It then binds Streamlit to `0.0.0.0:$PORT`. Missing configuration or an invalid seed exits without starting the server or repairing embeddings. `python scripts/render_start.py --check` runs the same offline validation/restoration without starting Streamlit; use a disposable copy for checks, not the canonical worktree.

Use `RAG_INDEX_BOOTSTRAP_SEED_PATH=deploy/rag_index_seed_two_products.sqlite3` for the validated compatible two-product seed. The authorized live refresh embedded 3 new chunks and reused 20; the resulting 23-chunk seed is packaged for publication. The old local seed is stale and must not be deployed. See [build measurements](docs/evidence/rag/two-product-index-build.json). Keep API key, generation model and demo password private in Render Environment. The native `/_stcore/health` endpoint indicates server liveness, not successful API generation or reviewed content. Offline tests and local Windows HTTP checks do not establish Linux/Render acceptance. Dependencies still use lower bounds, so a clean hosted dependency build remains a required check.

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
