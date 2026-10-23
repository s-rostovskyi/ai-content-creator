# Instagram RAG Acceptance Evidence

This folder preserves one owner-reviewed Instagram RAG export pair exactly as copied from `UI_Test/`:

- Markdown export: `instagram-rev3-20261023T130612Z-0fee9998.md`
- JSON export: `instagram-rev3-20261023T130612Z-0fee9998.json`

Recorded facts:
- Retrieval saved at: `2026-10-23T12:53:49Z`
- Approval timestamp: `2026-10-23T13:06:12.559683+00:00`
- Approved revision: `3`
- Model: `gpt-5.4-mini-2026-03-17`
- Retrieval usage: prompt_tokens=`87`, total_tokens=`87`, latency=`2.715s`
- Generation usage: input_tokens=`1837`, output_tokens=`547`, total_tokens=`2384`, latency=`5.113s`
- Context mode: `rag`
- Source snapshot: `9349972665c952782b93afde17efc583f4f577019709d36d43b35d0523cf1e20`
- SHA-256 markdown: `87d9cdc3c6d578829f3308fd1390cbd55caa01aefc7c5ec656e6d1f1c9ea1a1e`
- SHA-256 JSON: `9af39228d04cd56eae09bd40635f23222a985560b5c132752024a0a6038fce95`
- Markdown/channel_copy equality: `True`

Scope notes:
- This is one owner-reviewed Instagram generation -> manual notes edit -> approval -> export, not all-channel RAG acceptance.
- This is not an independent peer review and not a live revision test.
- Earlier failed retrieval evidence remains preserved in `docs/evidence/rag/` and was not rewritten.
- Owner browser checks previously confirmed per-channel view retention and an explicit zero-API index rebuild; those are reported checks, not claims from this copy step.
- Native rerenders can still reset scroll position; this limitation is not fixed here.
