from __future__ import annotations

"""Persistent SQLite storage for deterministic RAG chunk vectors.

The index stores chunk metadata, injected embedding vectors, model identity, and
corpus snapshot identity. Writes are published atomically by building a complete
SQLite file at a temporary path and replacing the active snapshot only after the
write succeeds.
"""

from dataclasses import dataclass
from hashlib import sha256
import gc
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Iterable, Literal, Mapping, Sequence

from src.document_processor import KnowledgeBaseDocument
from src.rag_chunking import (
    ChunkingPolicy,
    DEFAULT_CHUNKING_VERSION,
    RagChunk,
    build_rag_chunks,
)

DEFAULT_INDEX_DIRECTORY = Path(".rag")
DEFAULT_INDEX_FILENAME = "rag_index.sqlite3"
INDEX_SCHEMA_VERSION = 1
SNAPSHOT_VERSION = "rag-corpus-snapshot-v1"
VECTOR_INDEX_VERSION = "rag-sqlite-index-v1"


class RagIndexError(Exception):
    """Base error for vector-index operations."""


class IndexBuildError(RagIndexError):
    """Raised when an index cannot be built or published safely."""


class InvalidVectorError(RagIndexError):
    """Raised when a vector has the wrong dimension or invalid numeric values."""


class CorpusSnapshotMismatchError(RagIndexError):
    """Raised when a query uses a corpus snapshot that does not match the index."""


class SearchParameterError(RagIndexError):
    """Raised when a similarity-search parameter is invalid."""


@dataclass(frozen=True)
class CorpusSourceFingerprint:
    repository_relative_path: str
    knowledge_base: Literal["primary", "secondary"]
    document_hash: str
    section_count: int


@dataclass(frozen=True)
class CorpusSnapshot:
    snapshot_id: str
    source_fingerprints: tuple[CorpusSourceFingerprint, ...]


@dataclass(frozen=True)
class IndexedChunkRecord:
    chunk: RagChunk
    vector: tuple[float, ...]


@dataclass(frozen=True)
class SearchResult:
    chunk_id: str
    similarity: float
    chunk: RagChunk


class SQLiteVectorIndex:
    """In-memory view over a persisted SQLite vector snapshot."""

    def __init__(
        self,
        *,
        index_path: Path,
        corpus_snapshot: CorpusSnapshot,
        embedding_model_id: str,
        vector_dimensions: int,
        chunking_version: str,
        chunking_policy: ChunkingPolicy,
        records: tuple[IndexedChunkRecord, ...],
    ) -> None:
        self.index_path = index_path
        self.corpus_snapshot = corpus_snapshot
        self.embedding_model_id = embedding_model_id
        self.vector_dimensions = vector_dimensions
        self.chunking_version = chunking_version
        self.chunking_policy = chunking_policy
        self._records = records

    @property
    def chunk_count(self) -> int:
        return len(self._records)

    @property
    def source_count(self) -> int:
        return len(self.corpus_snapshot.source_fingerprints)

    @classmethod
    def open(cls, index_path: str | Path) -> "SQLiteVectorIndex":
        resolved_path = Path(index_path).resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(resolved_path)

        with sqlite3.connect(resolved_path) as connection:
            connection.row_factory = sqlite3.Row
            metadata = _load_metadata(connection)
            records = _load_records(connection, expected_embedding_model_id=metadata["embedding_model_id"])

        return cls(
            index_path=resolved_path,
            corpus_snapshot=metadata["corpus_snapshot"],
            embedding_model_id=metadata["embedding_model_id"],
            vector_dimensions=metadata["vector_dimensions"],
            chunking_version=metadata["chunking_version"],
            chunking_policy=metadata["chunking_policy"],
            records=records,
        )

    def search_primary(
        self,
        query_vector: Sequence[float],
        *,
        top_k: int,
        minimum_similarity: float = 0.0,
        current_corpus_snapshot: CorpusSnapshot | str,
    ) -> tuple[SearchResult, ...]:
        return self.search(
            knowledge_base="primary",
            query_vector=query_vector,
            top_k=top_k,
            minimum_similarity=minimum_similarity,
            current_corpus_snapshot=current_corpus_snapshot,
        )

    def search_secondary(
        self,
        query_vector: Sequence[float],
        *,
        top_k: int,
        minimum_similarity: float = 0.0,
        current_corpus_snapshot: CorpusSnapshot | str,
    ) -> tuple[SearchResult, ...]:
        return self.search(
            knowledge_base="secondary",
            query_vector=query_vector,
            top_k=top_k,
            minimum_similarity=minimum_similarity,
            current_corpus_snapshot=current_corpus_snapshot,
        )

    def search(
        self,
        *,
        knowledge_base: Literal["primary", "secondary"],
        query_vector: Sequence[float],
        top_k: int,
        minimum_similarity: float = 0.0,
        current_corpus_snapshot: CorpusSnapshot | str,
    ) -> tuple[SearchResult, ...]:
        self._ensure_snapshot_matches(current_corpus_snapshot)
        self._validate_top_k(top_k)
        self._validate_similarity_threshold(minimum_similarity)
        validated_query_vector = _validate_vector(query_vector, self.vector_dimensions)
        query_norm = _vector_norm(validated_query_vector)

        scored_results: list[SearchResult] = []
        for record in self._records:
            if record.chunk.knowledge_base != knowledge_base:
                continue
            score = _cosine_similarity(validated_query_vector, record.vector, query_norm=query_norm)
            if score < minimum_similarity:
                continue
            scored_results.append(SearchResult(chunk_id=record.chunk.chunk_id, similarity=score, chunk=record.chunk))

        scored_results.sort(key=lambda result: (-result.similarity, result.chunk_id))
        return tuple(scored_results[:top_k])

    def _ensure_snapshot_matches(self, current_corpus_snapshot: CorpusSnapshot | str) -> None:
        current_snapshot_id = (
            current_corpus_snapshot.snapshot_id
            if isinstance(current_corpus_snapshot, CorpusSnapshot)
            else str(current_corpus_snapshot)
        )
        if current_snapshot_id != self.corpus_snapshot.snapshot_id:
            raise CorpusSnapshotMismatchError(
                f"Index snapshot {self.corpus_snapshot.snapshot_id} does not match current corpus snapshot {current_snapshot_id}."
            )

    @staticmethod
    def _validate_top_k(top_k: int) -> None:
        if not isinstance(top_k, int) or top_k <= 0:
            raise SearchParameterError("top_k must be a positive integer.")

    @staticmethod
    def _validate_similarity_threshold(minimum_similarity: float) -> None:
        if not math.isfinite(minimum_similarity):
            raise SearchParameterError("minimum_similarity must be a finite number.")
        if minimum_similarity < -1.0 or minimum_similarity > 1.0:
            raise SearchParameterError("minimum_similarity must be between -1.0 and 1.0.")


def build_corpus_snapshot(documents: Iterable[KnowledgeBaseDocument]) -> CorpusSnapshot:
    fingerprints = tuple(
        sorted(
            (
                CorpusSourceFingerprint(
                    repository_relative_path=document.repository_relative_path,
                    knowledge_base=document.knowledge_base,
                    document_hash=_hash_text(document.markdown),
                    section_count=len(document.sections),
                )
                for document in documents
            ),
            key=lambda fingerprint: fingerprint.repository_relative_path,
        )
    )
    digest = sha256()
    digest.update(SNAPSHOT_VERSION.encode("utf-8"))
    for fingerprint in fingerprints:
        digest.update(fingerprint.repository_relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(fingerprint.knowledge_base.encode("utf-8"))
        digest.update(b"\0")
        digest.update(fingerprint.document_hash.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(fingerprint.section_count).encode("utf-8"))
        digest.update(b"\0")
    return CorpusSnapshot(snapshot_id=digest.hexdigest(), source_fingerprints=fingerprints)


def build_index_from_documents(
    index_path: str | Path,
    documents: Iterable[KnowledgeBaseDocument],
    vectors_by_chunk_id: Mapping[str, Sequence[float]],
    *,
    embedding_model_id: str,
    vector_dimensions: int | None = None,
    chunking_policy: ChunkingPolicy = ChunkingPolicy(),
) -> CorpusSnapshot:
    document_list = tuple(documents)
    corpus_snapshot = build_corpus_snapshot(document_list)
    chunks = build_rag_chunks(document_list, policy=chunking_policy)
    write_vector_index(
        index_path,
        corpus_snapshot=corpus_snapshot,
        chunks=chunks,
        vectors_by_chunk_id=vectors_by_chunk_id,
        embedding_model_id=embedding_model_id,
        vector_dimensions=vector_dimensions,
        chunking_policy=chunking_policy,
    )
    return corpus_snapshot


def write_vector_index(
    index_path: str | Path,
    *,
    corpus_snapshot: CorpusSnapshot,
    chunks: Sequence[RagChunk],
    vectors_by_chunk_id: Mapping[str, Sequence[float]],
    embedding_model_id: str,
    vector_dimensions: int | None = None,
    chunking_policy: ChunkingPolicy = ChunkingPolicy(),
) -> Path:
    resolved_index_path = Path(index_path).resolve()
    resolved_index_path.parent.mkdir(parents=True, exist_ok=True)
    chunk_records = tuple(chunks)
    if not chunk_records:
        raise IndexBuildError("Cannot build an index without chunks.")

    chunk_ids = [chunk.chunk_id for chunk in chunk_records]
    if len(set(chunk_ids)) != len(chunk_ids):
        raise IndexBuildError("Chunk identifiers must be unique.")
    expected_chunk_ids = set(chunk_ids)
    provided_chunk_ids = set(vectors_by_chunk_id)
    if provided_chunk_ids != expected_chunk_ids:
        missing_chunk_ids = sorted(expected_chunk_ids - provided_chunk_ids)
        extra_chunk_ids = sorted(provided_chunk_ids - expected_chunk_ids)
        message_parts = []
        if missing_chunk_ids:
            message_parts.append(f"missing vectors for {', '.join(missing_chunk_ids)}")
        if extra_chunk_ids:
            message_parts.append(f"unexpected vectors for {', '.join(extra_chunk_ids)}")
        raise IndexBuildError("; ".join(message_parts))

    resolved_vector_dimensions = _resolve_vector_dimensions(vectors_by_chunk_id, vector_dimensions)
    temp_fd, temp_name = tempfile.mkstemp(dir=resolved_index_path.parent, suffix=".sqlite3")
    os.close(temp_fd)
    temp_path = Path(temp_name)

    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(temp_path)
        _initialize_schema(connection)
        _write_metadata(
            connection,
            corpus_snapshot=corpus_snapshot,
            embedding_model_id=embedding_model_id,
            vector_dimensions=resolved_vector_dimensions,
            chunking_policy=chunking_policy,
            chunk_count=len(chunk_records),
            source_count=len(corpus_snapshot.source_fingerprints),
        )
        _write_chunks_and_vectors(
            connection,
            chunk_records,
            vectors_by_chunk_id=vectors_by_chunk_id,
            embedding_model_id=embedding_model_id,
            vector_dimensions=resolved_vector_dimensions,
        )
        connection.commit()
        connection.close()
        connection = None
        gc.collect()
        os.replace(temp_path, resolved_index_path)
    except Exception as exc:
        if connection is not None:
            connection.close()
            connection = None
        gc.collect()
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        if isinstance(exc, RagIndexError):
            raise
        raise IndexBuildError(str(exc)) from exc

    return resolved_index_path


def open_vector_index(index_path: str | Path) -> SQLiteVectorIndex:
    return SQLiteVectorIndex.open(index_path)


def _initialize_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE chunks (
            chunk_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            repository_relative_path TEXT NOT NULL,
            knowledge_base TEXT NOT NULL,
            document_hash TEXT NOT NULL,
            document_title TEXT NOT NULL,
            section_id TEXT NOT NULL,
            section_heading_path TEXT NOT NULL,
            section_heading_text TEXT NOT NULL,
            section_kind TEXT NOT NULL,
            chunk_kind TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            applicable_limitations TEXT NOT NULL,
            source_urls TEXT NOT NULL,
            source_url_text TEXT NOT NULL,
            publisher TEXT NOT NULL,
            published_updated TEXT NOT NULL,
            accessed TEXT NOT NULL,
            evidence_type TEXT NOT NULL,
            section_line_start INTEGER NOT NULL,
            section_line_end INTEGER NOT NULL,
            chunk_line_start INTEGER NOT NULL,
            chunk_line_end INTEGER NOT NULL,
            chunk_hash TEXT NOT NULL
        );

        CREATE TABLE vectors (
            chunk_id TEXT PRIMARY KEY,
            vector_model_id TEXT NOT NULL,
            vector_dimensions INTEGER NOT NULL,
            vector_json TEXT NOT NULL,
            FOREIGN KEY (chunk_id) REFERENCES chunks(chunk_id) ON DELETE CASCADE
        );
        """
    )


def _write_metadata(
    connection: sqlite3.Connection,
    *,
    corpus_snapshot: CorpusSnapshot,
    embedding_model_id: str,
    vector_dimensions: int,
    chunking_policy: ChunkingPolicy,
    chunk_count: int,
    source_count: int,
) -> None:
    metadata = {
        "schema_version": str(INDEX_SCHEMA_VERSION),
        "index_version": VECTOR_INDEX_VERSION,
        "corpus_snapshot_id": corpus_snapshot.snapshot_id,
        "embedding_model_id": embedding_model_id,
        "vector_dimensions": str(vector_dimensions),
        "chunking_version": DEFAULT_CHUNKING_VERSION,
        "chunking_max_characters": str(chunking_policy.max_chunk_characters),
        "chunking_overlap_characters": str(chunking_policy.overlap_characters),
        "chunk_count": str(chunk_count),
        "source_count": str(source_count),
        "source_fingerprints": json.dumps(
            [
                {
                    "repository_relative_path": fingerprint.repository_relative_path,
                    "knowledge_base": fingerprint.knowledge_base,
                    "document_hash": fingerprint.document_hash,
                    "section_count": fingerprint.section_count,
                }
                for fingerprint in corpus_snapshot.source_fingerprints
            ],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
    }
    connection.executemany(
        "INSERT INTO metadata (key, value) VALUES (?, ?)",
        metadata.items(),
    )


def _write_chunks_and_vectors(
    connection: sqlite3.Connection,
    chunk_records: Sequence[RagChunk],
    *,
    vectors_by_chunk_id: Mapping[str, Sequence[float]],
    embedding_model_id: str,
    vector_dimensions: int,
) -> None:
    connection.executemany(
        """
        INSERT INTO chunks (
            chunk_id,
            source_id,
            repository_relative_path,
            knowledge_base,
            document_hash,
            document_title,
            section_id,
            section_heading_path,
            section_heading_text,
            section_kind,
            chunk_kind,
            chunk_index,
            chunk_text,
            applicable_limitations,
            source_urls,
            source_url_text,
            publisher,
            published_updated,
            accessed,
            evidence_type,
            section_line_start,
            section_line_end,
            chunk_line_start,
            chunk_line_end,
            chunk_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                chunk.chunk_id,
                chunk.source_id,
                chunk.repository_relative_path,
                chunk.knowledge_base,
                chunk.document_hash,
                chunk.document_title,
                chunk.section_id,
                json.dumps(chunk.section_heading_path, ensure_ascii=False, sort_keys=False),
                chunk.section_heading_text,
                chunk.section_kind,
                chunk.chunk_kind,
                chunk.chunk_index,
                chunk.chunk_text,
                chunk.applicable_limitations,
                json.dumps(chunk.source_urls, ensure_ascii=False, sort_keys=False),
                chunk.source_url_text,
                chunk.publisher,
                chunk.published_updated,
                chunk.accessed,
                chunk.evidence_type,
                chunk.section_line_range[0],
                chunk.section_line_range[1],
                chunk.chunk_line_range[0],
                chunk.chunk_line_range[1],
                chunk.chunk_hash,
            )
            for chunk in chunk_records
        ],
    )
    connection.executemany(
        "INSERT INTO vectors (chunk_id, vector_model_id, vector_dimensions, vector_json) VALUES (?, ?, ?, ?)",
        [
            (
                chunk.chunk_id,
                embedding_model_id,
                vector_dimensions,
                json.dumps(
                    _validate_vector(vectors_by_chunk_id[chunk.chunk_id], vector_dimensions),
                    ensure_ascii=False,
                    sort_keys=False,
                    separators=(",", ":"),
                ),
            )
            for chunk in chunk_records
        ],
    )


def _load_metadata(connection: sqlite3.Connection) -> dict[str, object]:
    rows = connection.execute("SELECT key, value FROM metadata").fetchall()
    values = {row["key"]: row["value"] for row in rows}
    required_keys = {
        "schema_version",
        "index_version",
        "corpus_snapshot_id",
        "embedding_model_id",
        "vector_dimensions",
        "chunking_version",
        "chunking_max_characters",
        "chunking_overlap_characters",
        "source_fingerprints",
    }
    missing_keys = sorted(required_keys - values.keys())
    if missing_keys:
        raise IndexBuildError(f"Index metadata is incomplete: {', '.join(missing_keys)}")
    if values["schema_version"] != str(INDEX_SCHEMA_VERSION):
        raise IndexBuildError(f"Unsupported index schema version: {values['schema_version']}")
    if values["index_version"] != VECTOR_INDEX_VERSION:
        raise IndexBuildError(f"Unsupported index version: {values['index_version']}")

    chunking_policy = ChunkingPolicy(
        max_chunk_characters=int(values["chunking_max_characters"]),
        overlap_characters=int(values["chunking_overlap_characters"]),
    )
    corpus_snapshot = CorpusSnapshot(
        snapshot_id=values["corpus_snapshot_id"],
        source_fingerprints=tuple(
            CorpusSourceFingerprint(
                repository_relative_path=item["repository_relative_path"],
                knowledge_base=item["knowledge_base"],
                document_hash=item["document_hash"],
                section_count=int(item["section_count"]),
            )
            for item in json.loads(values["source_fingerprints"])
        ),
    )
    return {
        "corpus_snapshot": corpus_snapshot,
        "embedding_model_id": values["embedding_model_id"],
        "vector_dimensions": int(values["vector_dimensions"]),
        "chunking_version": values["chunking_version"],
        "chunking_policy": chunking_policy,
    }


def _load_records(connection: sqlite3.Connection, *, expected_embedding_model_id: str) -> tuple[IndexedChunkRecord, ...]:
    rows = connection.execute(
        """
        SELECT
            c.chunk_id,
            c.source_id,
            c.repository_relative_path,
            c.knowledge_base,
            c.document_hash,
            c.document_title,
            c.section_id,
            c.section_heading_path,
            c.section_heading_text,
            c.section_kind,
            c.chunk_kind,
            c.chunk_index,
            c.chunk_text,
            c.applicable_limitations,
            c.source_urls,
            c.source_url_text,
            c.publisher,
            c.published_updated,
            c.accessed,
            c.evidence_type,
            c.section_line_start,
            c.section_line_end,
            c.chunk_line_start,
            c.chunk_line_end,
            c.chunk_hash,
            v.vector_model_id,
            v.vector_dimensions,
            v.vector_json
        FROM chunks AS c
        INNER JOIN vectors AS v ON v.chunk_id = c.chunk_id
        ORDER BY c.chunk_id
        """
    ).fetchall()
    records: list[IndexedChunkRecord] = []
    for row in rows:
        if row["vector_model_id"] != expected_embedding_model_id:
            raise IndexBuildError(
                f"Vector model mismatch for {row['chunk_id']}: expected {expected_embedding_model_id}, found {row['vector_model_id']}"
            )
        vector = tuple(float(value) for value in json.loads(row["vector_json"]))
        validated_vector = _validate_vector(vector, int(row["vector_dimensions"]))
        chunk = RagChunk(
            chunk_id=row["chunk_id"],
            chunk_hash=row["chunk_hash"],
            document_hash=row["document_hash"],
            source_id=row["source_id"],
            repository_relative_path=row["repository_relative_path"],
            knowledge_base=row["knowledge_base"],
            document_title=row["document_title"],
            section_id=row["section_id"],
            section_heading_path=tuple(json.loads(row["section_heading_path"])),
            section_heading_text=row["section_heading_text"],
            section_kind=row["section_kind"],
            chunk_kind=row["chunk_kind"],
            chunk_index=int(row["chunk_index"]),
            chunk_text=row["chunk_text"],
            applicable_limitations=row["applicable_limitations"],
            source_urls=tuple(json.loads(row["source_urls"])),
            source_url_text=row["source_url_text"],
            publisher=row["publisher"],
            published_updated=row["published_updated"],
            accessed=row["accessed"],
            evidence_type=row["evidence_type"],
            section_line_range=(int(row["section_line_start"]), int(row["section_line_end"])),
            chunk_line_range=(int(row["chunk_line_start"]), int(row["chunk_line_end"])),
        )
        records.append(IndexedChunkRecord(chunk=chunk, vector=validated_vector))
    return tuple(records)


def _resolve_vector_dimensions(
    vectors_by_chunk_id: Mapping[str, Sequence[float]],
    vector_dimensions: int | None,
) -> int:
    if vector_dimensions is not None:
        if vector_dimensions <= 0:
            raise IndexBuildError("vector_dimensions must be a positive integer.")
        for chunk_id, vector in vectors_by_chunk_id.items():
            _validate_vector(vector, vector_dimensions, context=f"{chunk_id}")
        return vector_dimensions

    inferred_dimensions: int | None = None
    for chunk_id, vector in vectors_by_chunk_id.items():
        validated_vector = _validate_vector(vector, None, context=f"{chunk_id}")
        if inferred_dimensions is None:
            inferred_dimensions = len(validated_vector)
        elif len(validated_vector) != inferred_dimensions:
            raise IndexBuildError("All vectors must have the same dimension.")
    if inferred_dimensions is None:
        raise IndexBuildError("At least one vector is required to infer dimensions.")
    return inferred_dimensions


def _validate_vector(
    vector: Sequence[float],
    expected_dimensions: int | None,
    *,
    context: str | None = None,
) -> tuple[float, ...]:
    try:
        values = tuple(float(value) for value in vector)
    except (TypeError, ValueError) as exc:
        label = f" for {context}" if context is not None else ""
        raise InvalidVectorError(f"Vector contains non-numeric values{label}.") from exc
    if expected_dimensions is not None and len(values) != expected_dimensions:
        label = f" for {context}" if context is not None else ""
        raise InvalidVectorError(
            f"Vector dimension mismatch{label}: expected {expected_dimensions}, received {len(values)}."
        )
    if not values:
        label = f" for {context}" if context is not None else ""
        raise InvalidVectorError(f"Vector cannot be empty{label}.")
    if not all(math.isfinite(value) for value in values):
        label = f" for {context}" if context is not None else ""
        raise InvalidVectorError(f"Vector contains non-finite values{label}.")
    if _vector_norm(values) == 0.0:
        label = f" for {context}" if context is not None else ""
        raise InvalidVectorError(f"Vector must have a non-zero norm{label}.")
    return values


def _vector_norm(vector: Sequence[float]) -> float:
    return math.sqrt(math.fsum(value * value for value in vector))


def _cosine_similarity(
    left_vector: Sequence[float],
    right_vector: Sequence[float],
    *,
    query_norm: float | None = None,
) -> float:
    left = tuple(left_vector)
    right = tuple(right_vector)
    if len(left) != len(right):
        raise InvalidVectorError("Vector dimension mismatch during similarity calculation.")
    left_norm = query_norm if query_norm is not None else _vector_norm(left)
    right_norm = _vector_norm(right)
    if left_norm == 0.0 or right_norm == 0.0:
        raise InvalidVectorError("Vectors must have non-zero norms for cosine similarity.")
    dot_product = math.fsum(left_value * right_value for left_value, right_value in zip(left, right))
    return dot_product / (left_norm * right_norm)


def _hash_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


__all__ = [
    "CorpusSnapshot",
    "CorpusSnapshotMismatchError",
    "CorpusSourceFingerprint",
    "DEFAULT_INDEX_DIRECTORY",
    "DEFAULT_INDEX_FILENAME",
    "INDEX_SCHEMA_VERSION",
    "IndexedChunkRecord",
    "IndexBuildError",
    "InvalidVectorError",
    "RagIndexError",
    "SQLiteVectorIndex",
    "SearchParameterError",
    "SNAPSHOT_VERSION",
    "SearchResult",
    "VECTOR_INDEX_VERSION",
    "build_corpus_snapshot",
    "build_index_from_documents",
    "open_vector_index",
    "write_vector_index",
]
