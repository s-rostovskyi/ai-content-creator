# Free Render demo runbook

Card 6.1 — Deployment attempt and runtime verification. Musts M5, M8.

Status: the owner authorized completion of live indexing and deployment. The real incremental build and validated two-product seed are now prepared. See `../evidence/rag/two-product-index-build.json`. Render deployment and hosted acceptance remain pending until verified.

## Before publication

1. Completed live index refresh: 23 chunks, 20 reused, 3 newly embedded in one batch; 1,583 embedding tokens. The prepared seed matches the current seven-source corpus.
2. Confirm Ready against the actual current corpus and inspect a second-product result with human review and approved export. Preserve historical artifacts unchanged.
3. Package the compatible real index with `python scripts/package_rag_index_seed.py --seed-path deploy/rag_index_seed_two_products.sqlite3 --embedding-model text-embedding-3-small --vector-dimensions 1536`. Packaging is offline and refuses an existing destination. Validate the exact artifact before owner-authorized publication; never publish the stale old seed or synthetic test vectors.
4. Review and publish only approved application/config/test/docs files and the approved seed. Exclude `.env`, `.rag/`, local exports, `.vscode/`, temporary directories and test vectors. No push is authorized by this runbook.

## Existing dashboard form

Use the already connected `s-rostovskyi/ai-content-creator` repository. Do not create an additional Blueprint service just because `render.yaml` now exists; it is also a reference for the manual form.

| Setting | Value |
|---|---|
| Language | Python 3 |
| Branch | main |
| Root directory | empty |
| Region | Frankfurt if available |
| Compute | Free |
| Build command | `python -m pip install -r requirements.txt` |
| Start command | `python scripts/render_start.py` |
| Advanced health check path | `/_stcore/health` |
| Automatic deploys | Off/manual while assembling and verifying the demo |

Set `PYTHON_VERSION=3.14.7`, `SOURCE_MANAGEMENT_ENABLED=false`, `DEMO_ACCESS_ENABLED=true`, `OPENAI_EMBEDDING_MODEL=text-embedding-3-small`, `RAG_INDEX_VECTOR_DIMENSIONS=1536`, and `RAG_INDEX_BOOTSTRAP_SEED_PATH=deploy/rag_index_seed_two_products.sqlite3`.

Set `OPENAI_MODEL` to the owner's configured generation model; set `OPENAI_API_KEY` and a unique nonblank `DEMO_PASSWORD` privately in Render Environment. Do not upload a complete .env file or put real secret values in screenshots, Git or this runbook. Render supplies `PORT` (normally 10000); the startup script reads it and constructs the Streamlit command without shell interpolation.

A partially completed creation form is not treated as a saved service. If it expires, refill it from this runbook. Do not click Deploy until the approved commit/seed and environment are ready.

## Startup guarantees and limits

The startup script reads environment configuration, not .env. It enforces hosted read-only/password settings, validates the seed through the existing corpus/version/model/dimension/schema checks, then restores/reuses the runtime index atomically and starts Streamlit. Validation failure stops before HTTP binding and never triggers an embedding build. The application still enforces its own login and index/readiness gates.

The Streamlit health endpoint checks server liveness only. Verify login, index Ready, product source isolation and the authorized content workflow separately; an HTTP 200 is not live generation acceptance. Tests use synthetic vectors only inside temporary directories, never as a deployment artifact. Existing direct requirements have lower bounds; the first clean Linux dependency build remains unverified until Render executes it.

Free-host disk state is ephemeral. The packaged seed must be included in the deployment; local source/index editing stays disabled. Download approved exports before disconnecting/restarting. Browser sessions and runtime exports are not durable storage. Free service cold starts can delay the demo; open the link before presenting. Per-session generation limits and a shared password are not a global spending cap or individual user accounts.

## Hosted verification after explicit deployment authorization

- Record deployed commit, runtime/Python version, actual URL, date and logs without secrets.
- Confirm the login gate; incorrect password must not expose workspace controls.
- After authorized login, confirm read-only sources, disabled index builds and a Ready compatible index; inspect actual source/chunk provenance.
- Make only separately authorized paid generation/revision requests. Review format and factual limitations, approve the exact saved revision and verify Markdown/JSON exports.
- Confirm fresh startup can recover the prepared index without embedding calls. Record failures honestly; do not replace missing live or peer acceptance with offline tests.

Official references: [Render web services](https://render.com/docs/web-services), [Python version selection](https://render.com/docs/python-version), [Blueprint fields](https://render.com/docs/blueprint-spec), [Free service limits](https://render.com/docs/free).
