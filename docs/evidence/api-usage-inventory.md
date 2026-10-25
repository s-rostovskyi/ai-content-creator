# API Usage Inventory

Scope: evidence-based inventory for cost accounting only. This tracks application-side generation and embedding usage observed in saved evidence. It does **not** estimate dollar cost and does not include Codex usage outside the application.

## Deduplication rules
- Count each unique generation response once, using `response_id` when preserved.
- For repeated exports or manual edits that preserve the same originating response, count the originating response once and note the later artifact as a reuse.
- For retrieval evidence, a shared `query.digest` identifies query content, not a unique API invocation. Count separate executions separately when timestamps, latency, or provenance show distinct runs, even if the query text is identical.
- Do not count manual edits, offline previews, or zero-batch rebuild previews as paid calls.
- Zero-batch rebuilds require zero new embedding batches; an offline preview is not a build or API call.
- The current `.rag/rag_build_manifest.json` is treated as the latest build snapshot; if an older manifest was overwritten, that gap is recorded below.

## Observed usage by evidence class

| Class | Unique request basis | Evidence paths | Model | Tokens recorded | Usage completeness | Purpose / notes |
|---|---|---|---|---|---|---|
| Historical full-context generation: channel acceptance baseline | `response_id` values `resp_073b7d413d9db95b006ada7378c82087d2b7853b5319998bb1`, `resp_0cc94867f1bfc214006ada8af0e40087d29b1810eee66affda`, `resp_02830046d75b13c5006ada8b9b181887d280b0a60a1ad2de6c` | `docs/evidence/channel-acceptance/instagram-rev3-20261022T204049Z-a149b306.json`; `docs/evidence/channel-acceptance/linkedin-rev4-20261022T221546Z-313b21a5.json`; `docs/evidence/channel-acceptance/email-rev2-20261022T222413Z-105918ca.json` | `gpt-5.4-mini-2026-03-17` | Input 11,660; output 1,629; total 13,289; cached 2,176 (instagram only) | Complete | Historical non-RAG channel acceptance; all three are generation calls, with later manual edits/approvals preserved separately. |
| Historical full-context generation: Day 1 smoke test | `response_id` `resp_046e0e064730d2cc006ada61e5e20487d29c9389cc5958ebdb` | `docs/evidence/day1-smoke-test.md`; `docs/evidence/day1-smoke-test.json` | `gpt-5.4-mini-2026-03-17` | Input 3,683; output 547; total 4,230; cached 0 | Complete | Historical full-context smoke test preserved as a separate generation call; it is not represented elsewhere in this inventory. |
| Historical full-context generation/evaluation: six-response comparison | `response_id` values `resp_09c1c2c307e16e70006adaa7024dd487d28dd275de4765cc1b`, `resp_06e6d9e8a588921e006adaa705e2bc87d281a1dd52484f4fe1`, `resp_099403d09217c204006adaa70a7eac87d2b38821bf97f5b047`, `resp_0b28518e7d2365ee006adaa70e1e4887d2be994f2675c00f96`, `resp_02b4a7c6cea677a0006adaa71462cc87d29712dead83683a08`, `resp_05bfce73d3e74649006adaa71832e487d2882a409cde2dc7b7` | `docs/evaluation/runs/20261023T021455-aab889c1/01-instagram-generic.json`; `02-instagram-contextual.json`; `03-linkedin-generic.json`; `04-linkedin-contextual.json`; `05-email-generic.json`; `06-email-contextual.json` | `gpt-5.4-mini-2026-03-17` | Input 12,284; output 2,971; total 15,255; cached 0 | Complete | Historical non-RAG evaluation; preserved run artifacts only, no new generation here. |
| RAG generation / live model revision: Instagram | `response_id` `resp_0ed20c09f9852441006adb58dec24887d1a9047d203f731d92` | `docs/evidence/rag/acceptance/instagram-rev3-20261023T130612Z-0fee9998.json` (paired with `.md`) | `gpt-5.4-mini-2026-03-17` | Input 1,837; output 547; total 2,384; cached 0 | Complete | Owner-reviewed RAG Instagram export; later manual notes edit and approval are not additional paid calls. |
| RAG generation / live model revision: LinkedIn | `response_id` `resp_0c5477726ab09734006adbc05004f887d295b1b3c43d91a367` | `docs/evidence/rag/acceptance/linkedin-rev2-20261023T201936Z-84be0282.json` (paired with `.md`) | `gpt-5.4-mini-2026-03-17` | Input 2,157; output 436; total 2,593; cached 0 | Complete | Owner-reviewed live revision; the preserved pair does not include the earlier initial-response metadata, so only the final preserved revision is counted. |
| RAG generation / live model revision: Email | `response_id` `resp_09e6fd570aa17ae7006adbc7ec826887d2a898be7d2d6257db` | `docs/evidence/rag/acceptance/email-rev3-20261023T205812Z-272e76ac.json` (paired with `.md`) | `gpt-5.4-mini-2026-03-17` | Input 1,840; output 691; total 2,531; cached 0 | Complete | Owner-reviewed email export after manual editing; the initial 140-word generated body is mentioned in evidence but is not a separate counted call here. |
| Retrieval-query embeddings: packability retrieval before selection fix | `query.digest` `4cbea1873db18da9c220c1eeb87edbbd1e136a1d477613ca6c850f9043c18694`; distinct execution at `2026-10-23T10:49:32Z` | `docs/evidence/rag/packability-20261023T104924560Z.json` | `text-embedding-3-small` | Prompt/total 56 | Partial | Live retrieval call preserved as a separate execution before the selection fix; same query text as the later preview but not the same invocation. |
| Retrieval-query embeddings: packability retrieval after selection fix | `query.digest` `4cbea1873db18da9c220c1eeb87edbbd1e136a1d477613ca6c850f9043c18694`; distinct execution at `2026-10-23T11:28:11Z` | `docs/evidence/rag/packability-fixed-20261023T112803662Z.json` | `text-embedding-3-small` | Prompt/total 56 | Partial | Live retrieval call preserved after the selection fix; counted separately because timestamp and latency show a second execution. |
| Retrieval-query embeddings: Instagram RAG retrieval | `query.digest` `1f33436c0eed25465214e869c5f53f24e11bcd46b309ea85188507b4d17a8922` | `docs/evidence/rag/acceptance/instagram-rev3-20261023T130612Z-0fee9998.json` | `text-embedding-3-small` | Prompt/total 87 | Partial | Retrieval provenance for the owner-reviewed Instagram RAG export; no separate retrieval response ID was preserved. |
| Retrieval-query embeddings: LinkedIn RAG retrieval | `query.digest` `89f5f2412b5dbdc5d33d812e023da0babbfead3e69b43c2a1ccf4b6488ab1402` | `docs/evidence/rag/acceptance/linkedin-rev2-20261023T201936Z-84be0282.json` | `text-embedding-3-small` | Prompt/total 422 | Partial | Retrieval provenance for the live LinkedIn revision; no separate retrieval response ID was preserved. |
| Retrieval-query embeddings: Email RAG retrieval | `query.digest` `af77c672a44e6850e339d9b207b1260db87baa9c6d63879cae266d8d328ba6b0` | `docs/evidence/rag/acceptance/email-rev3-20261023T205812Z-272e76ac.json` | `text-embedding-3-small` | Prompt/total 87 | Partial | Retrieval provenance for the owner-reviewed email export; no separate retrieval response ID was preserved. |
| Index-build embeddings: machine-readable manifest | Build snapshot `corpus_snapshot_id` `4984775f808b507cc6c77b5394d5e730a314e80a7da19da1ada8bc0cd1bcb531` | `.rag/rag_build_manifest.json` | `text-embedding-3-small` | Prompt/total 1634 | Complete | Direct build manifest record: 3 embedded chunks, 17 reused embeddings, 1 completed batch, 1 planned batch, elapsed `3.205738s`. |

## Owner-reported corroboration
- The owner’s successful build screenshot / conversation report describes the same index-build invocation as the manifest row above and repeats `prompt_tokens=1634` and `total_tokens=1634`, with 3 embedded chunks, 17 reused embeddings, 1 batch, and elapsed `3.205738s`.
- This corroboration is retained for audit completeness but is not counted as a second paid call because it refers to the same build invocation already represented in the machine-readable manifest.

## Subtotals

### Directly recorded generation usage (`gpt-5.4-mini-2026-03-17`)
- Historical full-context generation: 4 requests; input 15,343; output 2,176; total 17,519; cached 2,176.
- Historical full-context generation/evaluation: 6 requests; input 12,284; output 2,971; total 15,255; cached 0.
- Combined historical full-context generation: 10 requests; input 27,627; output 5,147; total 32,774; cached 2,176.
- RAG generation / live model revision: 3 requests; input 5,834; output 1,674; total 7,508; cached 0.
- Combined directly recorded generation calls: 13 requests; input 33,461; output 6,821; total 40,282; cached 2,176.

### Directly recorded retrieval-query embeddings (`text-embedding-3-small`)
- Unique observed retrieval calls counted: 5.
- Prompt/total tokens recorded: 708 total across the counted retrieval queries (56 + 56 + 87 + 422 + 87).
- The two packability artifacts are separate observed calls because their timestamps and latencies show distinct executions, even though they share the same query digest.

### Directly recorded index-build embeddings (`text-embedding-3-small`)
- Completed batches: 1.
- Embedded chunks: 3.
- Reused embeddings: 17.
- Prompt/total tokens: 1634 / 1634.

### Owner-reported usage / corroboration
- Build screenshot / conversation report: one build invocation, prompt/total 1634, 3 embedded chunks, 17 reused embeddings, 1 batch, elapsed 3.205738 seconds.
- This is corroborative evidence for the same build invocation already counted above, not an extra paid call.

### Unknown usage and gaps
- The retrieval rows do not preserve separate request/response IDs, so they are deduped by execution evidence rather than by ID.
- Initial-response metadata behind the LinkedIn live revision is not preserved, so only the final revision is counted.
- If an earlier `.rag/rag_build_manifest.json` existed, it may have been overwritten; only the current build snapshot is available now.
- Manual edits, offline previews, and zero-batch rebuild previews are not counted as paid calls.
- This inventory records observed usage only; it does not equal billed account usage and does not include Codex usage outside the application.
