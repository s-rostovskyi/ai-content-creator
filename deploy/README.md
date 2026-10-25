# Prepared Render index seed

The prepared two-product deployment artifact is `deploy/rag_index_seed_two_products.sqlite3`.
The owner-authorized live refresh completed: 23 chunks, 20 reused embeddings, 3 newly embedded chunks in one batch.
Snapshot: `e2ab88df5679fb9accb6937fa9b7c94ece8d30fc2b962ee82841f9385e6c202e`. Seed SHA-256: `dff2897ffa36608261e75a5822135a23a3847f7ad4e5599a0159571825a63283`.
The seed contains validated public corpus/chunk/vector data; it contains no application credentials or session exports.
The older local `rag_index_seed.sqlite3` is stale against the seven-document corpus and must not be published as the current seed.

After an explicitly authorized real index refresh completes, package the new artifact offline:

```bash
python scripts/package_rag_index_seed.py --seed-path deploy/rag_index_seed_two_products.sqlite3 --embedding-model text-embedding-3-small --vector-dimensions 1536
```

Packaging never rebuilds embeddings, overwrites the active index or replaces an existing destination.
Review the seed's actual snapshot/count/model/dimensions and public-corpus contents before separate publication approval.
Never include `.env`, `.rag/`, exports, test vectors or runtime caches in this directory.
A prior compatible local runtime index is not a substitute for shipping the new seed to a fresh Render instance.
