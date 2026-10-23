from pathlib import Path

import pytest

from src.document_processor import load_knowledge_base_documents
from src.rag_chunking import build_rag_chunks
from src.rag_index import (
    CorpusSnapshotMismatchError,
    IndexBuildError,
    InvalidVectorError,
    SearchParameterError,
    build_corpus_snapshot,
    open_vector_index,
    write_vector_index,
)

PRIMARY_URL = "https://www.patagonia.com/product/mens-nano-puff-insulated-jacket/84212.html"
SECONDARY_URL = "https://example.com/outdoor-context"


def _write_document(
    path: Path,
    *,
    title: str,
    source_url: str,
    knowledge_base: str,
    facts: str,
    limitations: str,
    publisher: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        chr(10).join(
            [
                f"# {title}",
                "",
                f"- Source URL: {source_url}",
                f"- Publisher: {publisher}",
                "- Published/updated: Not stated",
                "- Accessed: 2026-10-22",
                f"- Knowledge base: {knowledge_base}",
                "- Evidence type: official statement",
                "",
                "## Relevant facts",
                "",
                facts,
                "",
                "## Limitations",
                "",
                limitations,
            ]
        ) + chr(10),
        encoding="utf-8",
    )


def _build_corpus(root: Path) -> None:
    (root / "knowledge_base" / "primary").mkdir(parents=True, exist_ok=True)
    (root / "knowledge_base" / "secondary").mkdir(parents=True, exist_ok=True)
    _write_document(
        root / "knowledge_base" / "primary" / "alpha.md",
        title="Alpha Primary",
        source_url=PRIMARY_URL,
        knowledge_base="primary",
        facts="Alpha primary facts with a compact description.",
        limitations="- Alpha limitations stay attached to every primary chunk.",
        publisher="Patagonia, US website",
    )
    _write_document(
        root / "knowledge_base" / "primary" / "beta.md",
        title="Beta Primary",
        source_url=PRIMARY_URL,
        knowledge_base="primary",
        facts="Beta primary facts with another compact description.",
        limitations="- Beta limitations stay attached to every primary chunk.",
        publisher="Patagonia, US website",
    )
    _write_document(
        root / "knowledge_base" / "secondary" / "gamma.md",
        title="Gamma Secondary",
        source_url=SECONDARY_URL,
        knowledge_base="secondary",
        facts="Gamma secondary facts with a compact description.",
        limitations="- Gamma limitations stay attached to every secondary chunk.",
        publisher="Example Publisher",
    )


def _vectors_for_chunks(chunks, *, primary_vector, secondary_vector):
    vectors = {}
    for chunk in chunks:
        vectors[chunk.chunk_id] = primary_vector if chunk.knowledge_base == "primary" else secondary_vector
    return vectors


def test_index_ranking_isolation_and_validation(tmp_path: Path) -> None:
    _build_corpus(tmp_path)
    documents = load_knowledge_base_documents(tmp_path)
    chunks = build_rag_chunks(documents)
    snapshot = build_corpus_snapshot(documents)
    index_path = tmp_path / ".rag" / "vector-index.sqlite3"

    write_vector_index(
        index_path,
        corpus_snapshot=snapshot,
        chunks=chunks,
        vectors_by_chunk_id=_vectors_for_chunks(chunks, primary_vector=[1.0, 0.0], secondary_vector=[0.0, 1.0]),
        embedding_model_id="offline-test",
        vector_dimensions=2,
    )

    index = open_vector_index(index_path)
    primary_results = index.search_primary([1.0, 0.0], top_k=10, current_corpus_snapshot=snapshot)
    secondary_results = index.search_secondary([0.0, 1.0], top_k=10, current_corpus_snapshot=snapshot)

    assert all(result.chunk.knowledge_base == "primary" for result in primary_results)
    assert all(result.chunk.knowledge_base == "secondary" for result in secondary_results)
    assert [result.chunk_id for result in primary_results] == sorted(
        chunk.chunk_id for chunk in chunks if chunk.knowledge_base == "primary"
    )
    assert [result.chunk_id for result in secondary_results] == sorted(
        chunk.chunk_id for chunk in chunks if chunk.knowledge_base == "secondary"
    )

    with pytest.raises(InvalidVectorError):
        write_vector_index(
            tmp_path / ".rag" / "bad-vector.sqlite3",
            corpus_snapshot=snapshot,
            chunks=chunks,
            vectors_by_chunk_id={chunk.chunk_id: [1.0] for chunk in chunks},
            embedding_model_id="offline-test",
            vector_dimensions=2,
        )

    with pytest.raises(InvalidVectorError):
        index.search_primary([0.0, 0.0], top_k=1, current_corpus_snapshot=snapshot)

    with pytest.raises(SearchParameterError):
        index.search_primary([1.0, 0.0], top_k=0, current_corpus_snapshot=snapshot)

    with pytest.raises(SearchParameterError):
        index.search_secondary([0.0, 1.0], top_k=1, minimum_similarity=1.5, current_corpus_snapshot=snapshot)


def test_index_persistence_atomic_failure_snapshot_mismatch_and_deleted_source_suppression(tmp_path: Path) -> None:
    _build_corpus(tmp_path)
    documents_v1 = load_knowledge_base_documents(tmp_path)
    chunks_v1 = build_rag_chunks(documents_v1)
    snapshot_v1 = build_corpus_snapshot(documents_v1)
    index_path = tmp_path / ".rag" / "vector-index.sqlite3"

    write_vector_index(
        index_path,
        corpus_snapshot=snapshot_v1,
        chunks=chunks_v1,
        vectors_by_chunk_id=_vectors_for_chunks(chunks_v1, primary_vector=[1.0, 0.0], secondary_vector=[0.0, 1.0]),
        embedding_model_id="offline-test",
        vector_dimensions=2,
    )

    initial_index = open_vector_index(index_path)
    initial_primary_ids = [
        result.chunk.repository_relative_path
        for result in initial_index.search_primary([1.0, 0.0], top_k=10, current_corpus_snapshot=snapshot_v1)
    ]
    assert "knowledge_base/primary/beta.md" in initial_primary_ids

    deleted_source_path = tmp_path / "knowledge_base" / "primary" / "beta.md"
    deleted_source_path.unlink()
    documents_v2 = load_knowledge_base_documents(tmp_path)
    chunks_v2 = build_rag_chunks(documents_v2)
    snapshot_v2 = build_corpus_snapshot(documents_v2)

    with pytest.raises(IndexBuildError):
        write_vector_index(
            index_path,
            corpus_snapshot=snapshot_v2,
            chunks=chunks_v2,
            vectors_by_chunk_id={chunk.chunk_id: [1.0, 0.0] for chunk in chunks_v2[:-1]},
            embedding_model_id="offline-test",
            vector_dimensions=2,
        )

    reopened_index = open_vector_index(index_path)
    assert reopened_index.corpus_snapshot.snapshot_id == snapshot_v1.snapshot_id
    with pytest.raises(CorpusSnapshotMismatchError):
        reopened_index.search_primary([1.0, 0.0], top_k=10, current_corpus_snapshot=snapshot_v2)

    write_vector_index(
        index_path,
        corpus_snapshot=snapshot_v2,
        chunks=chunks_v2,
        vectors_by_chunk_id=_vectors_for_chunks(chunks_v2, primary_vector=[1.0, 0.0], secondary_vector=[0.0, 1.0]),
        embedding_model_id="offline-test",
        vector_dimensions=2,
    )

    reopened_index_v2 = open_vector_index(index_path)
    final_primary_results = reopened_index_v2.search_primary([1.0, 0.0], top_k=10, current_corpus_snapshot=snapshot_v2)
    assert all(result.chunk.repository_relative_path != "knowledge_base/primary/beta.md" for result in final_primary_results)
    assert all(result.chunk.repository_relative_path == "knowledge_base/primary/alpha.md" for result in final_primary_results)
