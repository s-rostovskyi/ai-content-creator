from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.rag_service import RagServiceError, package_rag_index_seed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Package a validated RAG index seed")
    parser.add_argument("--index-path", type=Path, default=None, help="override the runtime index path")
    parser.add_argument(
        "--seed-path",
        type=Path,
        default=Path("deploy/rag_index_seed.sqlite3"),
        help="destination path for the packaged deployment seed",
    )
    parser.add_argument("--embedding-model", default=None, help="model identity; otherwise OPENAI_EMBEDDING_MODEL")
    parser.add_argument("--vector-dimensions", type=int, default=None, help="expected dimensions; otherwise RAG_INDEX_VECTOR_DIMENSIONS")
    args = parser.parse_args(argv)

    try:
        result = package_rag_index_seed(repo_root=REPO_ROOT, index_path=args.index_path, seed_path=args.seed_path, embedding_model_id=args.embedding_model, vector_dimensions=args.vector_dimensions)
    except RagServiceError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("RAG index seed package")
    print(f"Source index: {result.source_index_path}")
    print(f"Seed path: {result.seed_path}")
    print(f"Corpus snapshot: {result.corpus_snapshot.snapshot_id}")
    print(f"Embedding model: {result.embedding_model_id}")
    print(f"Vector dimensions: {result.vector_dimensions}")
    print(f"Chunk count: {result.chunk_count}")
    print(f"Source count: {result.source_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
