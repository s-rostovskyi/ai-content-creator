# RAG Source Refresh Verification

- Editorial correction: `knowledge_base/primary/brand_voice.md` now places the `style 84212` observation under `## Content implications — interpretation, not an official brand manual`; the wording is preserved exactly.
- Regression coverage: `tests/test_document_processor.py` now verifies that a temporary corpus with `knowledge_base/secondary/.hidden/ignored.md` is excluded by both document discovery and `source_registry.list_sources()`, while a visible control document remains included.
- Focused test result: `18 passed, 1 skipped` from the documented focused run; this note does not claim a new rerun.
- Earlier corpus snapshot: `9349972665c952782b93afde17efc583f4f577019709d36d43b35d0523cf1e20` from the preserved earlier packability and acceptance evidence.
- Current corpus snapshot: `4984775f808b507cc6c77b5394d5e730a314e80a7da19da1ada8bc0cd1bcb531` from the current offline helper snapshot.
- Owner-run index refresh manifest: build model `text-embedding-3-small`, embedded chunks `3`, reused embeddings `17`, completed batches `1`, elapsed time `3.205738s`, corpus snapshot `4984775f808b507cc6c77b5394d5e730a314e80a7da19da1ada8bc0cd1bcb531`.
- Owner browser confirmation, as reported: source management showed `Ready`, then an offline preview reported `20` reusable embeddings, `0` missing embeddings, and `0` planned batches.
- Startup note, as reported: the first authentication attempt failed after restart, a later retry succeeded, and the root cause was not established.
- Historical generation/retrieval evidence remains unchanged and still refers to its recorded earlier snapshot; this refresh does not create new generation acceptance.