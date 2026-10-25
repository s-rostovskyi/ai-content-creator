# Render local preflight — 2026-10-25

Card 6.1, Musts M5/M8. This records local implementation and offline checks, not a deployment or human peer acceptance.

## Prepared configuration

- `render.yaml`: Python Web Service, Free, Frankfurt, main, automatic deploys off, health check `/_stcore/health`, private values requested through Render Environment.
- `.python-version`: 3.14.7, matching the local interpreter used for project verification.
- Build: `python -m pip install -r requirements.txt` (declared direct dependencies remain lower-bounded; no fresh dependency installation was performed).
- Start: `python scripts/render_start.py`, replacing the earlier direct Streamlit command in the dashboard draft.
- Intended new seed: `deploy/rag_index_seed_two_products.sqlite3` (not created or published).

## Startup behavior

The process-level preflight requires password-protected access, hosted source/index mutation disabled, nonblank application model/key configuration, a valid port and a prepared seed. The seed is validated read-only through the existing corpus/version/model/dimension/schema checks even when an existing runtime index is compatible. Only then does offline atomic restoration/reuse run and Streamlit start on 0.0.0.0 and Render's PORT. Failure prevents HTTP binding and never initiates paid embedding repair.

The health endpoint only establishes server liveness. Application login, product-scoped RAG readiness, real generation/revision, review/export and restart recovery must still be verified on Render after owner authorization. The shared demo password is not individual accounts or a global spend cap.

## Independently executed local checks

- `tests/test_render_startup.py` and `tests/test_rag_service.py`: **38 passed in 12.96 seconds**, with a fresh temporary base and cache disabled. No full suite was run.
- Cases include restore/reuse, denied hosted mutations, missing configuration, invalid port, missing/corrupt/stale/model/dimension-incompatible seed, sanitized failures, preservation of an existing index and check-only/no-server behavior.
- The HTTP smoke starts a real Streamlit child process on loopback after preflight in a disposable copy with synthetic corpus/vectors, test-only environment values and an isolated home directory. `/_stcore/health` and `/` returned HTTP 200. The owned child process is terminated afterward. This is a Windows/current-dependency check, not a Linux/Render build or live API test.
- Render YAML parsed successfully; Free/manual deployment, guarded start, health path, password/read-only flags and private value declarations were inspected locally. This is not Render API/schema acceptance.
- `git diff --check` passed.
- Real `.env` and credentials were not read. No package was installed, no OpenAI request or real index rebuild was made, and no Render service was created.
- The real active index and old local seed remain byte-identical to their preceding state (SHA-256 430ab2e8bff73c972155c97ebfd4ac73bc859e9a656a43af0a2bebce6ad4a845). They are still stale against the two-product corpus. No replacement seed, staging, commit, push or deployment was performed.

## Remaining gates

The owner deferred paid real indexing until new key/limits are available. Next: explicit real index refresh, Ready confirmation and reviewed second-product workflow; package/inspect the new compatible seed offline; separately authorize publication; finish the existing Render dashboard form with the new guarded start command; explicitly authorize deployment and verify the real hosted runtime. The dashboard draft itself is not a deployed service.

File scope for this task: `.python-version`, `render.yaml`, `scripts/render_start.py`, `tests/test_render_startup.py`, public validation helper in `src/rag_service.py`, `.env.example`, `deploy/README.md`, `docs/deployment/render.md`, this note and README deployment wording. A documentation-only correction also maps the earlier two-product UI/pipeline note to actual board cards 5.1/4.3 rather than 4.1. All earlier uncommitted implementation and evidence remain preserved.

## Subsequent owner-authorized live preparation

The later live build completed successfully: 23 chunks, 20 reused embeddings, 3 new embeddings, 1 API batch, 1,583 prompt/total tokens, 2.634059 seconds. The compatible two-product seed was packaged offline and validated. See `docs/evidence/rag/two-product-index-build.json` (repository-relative path). Earlier deferred/stale statements above describe the preceding checkpoint; they are superseded for index preparation only. Hosted runtime and second-product generation acceptance are not established by this build.

## Final publication preflight

The complete offline suite passed: **289 passed, 1 skipped in 169.68 seconds**. Real repository `.env` loading was suppressed while synthetic test configuration files remained enabled. The existing skip is Windows symlink creation. Current-corpus assertions in evaluation/CLI tests were updated from six to seven sources; historical recorded evaluations were not rewritten. The actual prepared seed was independently restored and reused in a fresh disposable copy with the real public corpus; no API client or real credentials were used in that recovery check. `git diff --check` passed. These local results do not establish Linux/Render acceptance.
