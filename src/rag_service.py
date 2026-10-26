from __future__ import annotations

"""Orchestration for deterministic RAG index builds.

Dry-runs validate the corpus and plan embedding batches without loading
credentials or writing index files. Live builds reuse compatible existing
vectors, embed only missing inputs, and publish a completed SQLite snapshot
atomically.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
import math
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from time import perf_counter
from typing import Sequence

from src.document_processor import KnowledgeBaseDocument, load_knowledge_base_documents
from src.embedding_integration import (
    DEFAULT_MAX_EMBEDDING_BATCH_SIZE,
    DEFAULT_MAX_INPUT_CHARACTERS,
    DEFAULT_MAX_TOTAL_CHARACTERS,
    DEFAULT_TIMEOUT_SECONDS,
    EmbeddingUsageMetrics,
    EmbeddedBatch,
    OpenAIEmbeddingSettings,
    OpenAIEmbeddingConfigurationError,
    OpenAIEmbeddingIntegrationError,
    OpenAIEmbeddingsClientProtocol,
    _validate_timeout_seconds,
    embed_texts,
    load_embedding_settings,
)
from src.rag_chunking import ChunkingPolicy, DEFAULT_CHUNKING_VERSION, RagChunk, build_rag_chunks
from src.rag_index import (
    CorpusSnapshot,
    IndexBuildError,
    SQLiteVectorIndex,
    DEFAULT_INDEX_DIRECTORY,
    DEFAULT_INDEX_FILENAME,
    build_corpus_snapshot,
    open_vector_index,
    write_vector_index,
)

EMBEDDING_INPUT_VERSION = "rag-embedding-input-v1"
DEFAULT_RUNTIME_INDEX_PATH = DEFAULT_INDEX_DIRECTORY / DEFAULT_INDEX_FILENAME
DEFAULT_RUNTIME_MANIFEST_NAME = "rag_build_manifest.json"


class RagServiceError(Exception):
    """Base error for RAG build orchestration failures."""


@dataclass(frozen=True)
class RagEmbeddingBatchPlan:
    chunk_ids: tuple[str, ...]
    input_character_sizes: tuple[int, ...]
    total_input_characters: int


@dataclass(frozen=True)
class RagBuildPlan:
    repo_root: Path
    index_path: Path
    embedding_model_id: str | None
    chunking_policy: ChunkingPolicy
    corpus_snapshot: CorpusSnapshot
    chunk_count: int
    chunk_counts_by_knowledge_base: tuple[tuple[str, int], ...]
    input_character_sizes: tuple[int, ...]
    pending_embedding_count: int
    reusable_embedding_count: int
    planned_batches: tuple[RagEmbeddingBatchPlan, ...]
    existing_index_path: Path | None
    existing_index_matches: bool | None
    existing_index_reason: str
    vector_dimensions: int | None


@dataclass(frozen=True)
class RagBatchResult:
    chunk_ids: tuple[str, ...]
    input_character_sizes: tuple[int, ...]
    total_input_characters: int
    requested_model: str
    returned_model: str
    vector_dimensions: int
    usage: EmbeddingUsageMetrics | None
    elapsed_seconds: float


@dataclass(frozen=True)
class RagBuildResult:
    repo_root: Path
    index_path: Path
    manifest_path: Path
    corpus_snapshot: CorpusSnapshot
    embedding_model_id: str
    chunking_policy: ChunkingPolicy
    vector_dimensions: int
    chunk_count: int
    chunk_counts_by_knowledge_base: tuple[tuple[str, int], ...]
    reused_embedding_count: int
    embedded_chunk_count: int
    planned_batches: tuple[RagEmbeddingBatchPlan, ...]
    completed_batches: tuple[RagBatchResult, ...]
    existing_index_path: Path | None
    build_elapsed_seconds: float


@dataclass(frozen=True)
class RagIndexSeedPackageResult:
    source_index_path: Path
    seed_path: Path
    corpus_snapshot: CorpusSnapshot
    embedding_model_id: str
    vector_dimensions: int
    chunk_count: int
    source_count: int
    chunking_policy: ChunkingPolicy


@dataclass(frozen=True)
class RagIndexBootstrapResult:
    runtime_index_path: Path
    seed_path: Path
    corpus_snapshot: CorpusSnapshot
    embedding_model_id: str
    vector_dimensions: int
    chunk_count: int
    source_count: int
    restored: bool


@dataclass(frozen=True)
class _ChunkInput:
    chunk: RagChunk
    input_text: str
    input_hash: str



def resolve_runtime_index_path(
    repo_root: str | Path | None = None,
    index_path: str | Path | None = None,
) -> Path:
    root_path = _resolve_repo_root(repo_root)
    if index_path is None:
        return (root_path / DEFAULT_RUNTIME_INDEX_PATH).resolve()
    candidate_path = Path(index_path)
    if candidate_path.is_absolute():
        return candidate_path.resolve()
    return (root_path / candidate_path).resolve()



def plan_embedding_batches(
    embedding_inputs: Sequence[tuple[str, str]],
    *,
    max_batch_size: int = DEFAULT_MAX_EMBEDDING_BATCH_SIZE,
    max_input_characters: int = DEFAULT_MAX_INPUT_CHARACTERS,
    max_total_characters: int = DEFAULT_MAX_TOTAL_CHARACTERS,
) -> tuple[RagEmbeddingBatchPlan, ...]:
    _validate_batch_limits(max_batch_size, max_input_characters, max_total_characters)
    normalized_inputs = _normalize_embedding_inputs(embedding_inputs)
    if not normalized_inputs:
        return tuple()

    plans: list[RagEmbeddingBatchPlan] = []
    batch_chunk_ids: list[str] = []
    batch_lengths: list[int] = []
    batch_total = 0

    for chunk_id, input_text in normalized_inputs:
        input_length = len(input_text)
        if input_length > max_input_characters:
            raise IndexBuildError(
                f"Embedding input for {chunk_id} exceeds the configured character limit of {max_input_characters}."
            )
        if input_length > max_total_characters:
            raise IndexBuildError(
                f"Embedding input for {chunk_id} exceeds the configured total character limit of {max_total_characters}."
            )
        if batch_chunk_ids and (
            len(batch_chunk_ids) >= max_batch_size or batch_total + input_length > max_total_characters
        ):
            plans.append(
                RagEmbeddingBatchPlan(
                    chunk_ids=tuple(batch_chunk_ids),
                    input_character_sizes=tuple(batch_lengths),
                    total_input_characters=batch_total,
                )
            )
            batch_chunk_ids = []
            batch_lengths = []
            batch_total = 0
        batch_chunk_ids.append(chunk_id)
        batch_lengths.append(input_length)
        batch_total += input_length

    if batch_chunk_ids:
        plans.append(
            RagEmbeddingBatchPlan(
                chunk_ids=tuple(batch_chunk_ids),
                input_character_sizes=tuple(batch_lengths),
                total_input_characters=batch_total,
            )
        )
    return tuple(plans)



def plan_rag_index_build(
    *,
    repo_root: str | Path | None = None,
    index_path: str | Path | None = None,
    embedding_model_id: str | None = None,
    chunking_policy: ChunkingPolicy = ChunkingPolicy(),
    max_batch_size: int = DEFAULT_MAX_EMBEDDING_BATCH_SIZE,
    max_input_characters: int = DEFAULT_MAX_INPUT_CHARACTERS,
    max_total_characters: int = DEFAULT_MAX_TOTAL_CHARACTERS,
) -> RagBuildPlan:
    root_path = _resolve_repo_root(repo_root)
    resolved_index_path = resolve_runtime_index_path(root_path, index_path)
    documents = load_knowledge_base_documents(root_path)
    corpus_snapshot = build_corpus_snapshot(documents)
    chunks = build_rag_chunks(documents, policy=chunking_policy)
    chunk_inputs = _build_chunk_inputs(chunks)
    chunk_counts_by_kb = _count_chunks_by_knowledge_base(chunks)
    resolved_model = _resolve_embedding_model_id(embedding_model_id)

    existing_index = _open_existing_index(resolved_index_path)
    compatible_vectors, compatible_match, existing_reason, vector_dimensions = _classify_existing_index(
        existing_index,
        current_chunks=chunks,
        current_corpus_snapshot=corpus_snapshot,
        embedding_model_id=resolved_model,
        chunking_policy=chunking_policy,
    )
    pending_inputs = tuple(
        (chunk_input.chunk.chunk_id, chunk_input.input_text)
        for chunk_input in chunk_inputs
        if chunk_input.chunk.chunk_id not in compatible_vectors
    )
    planned_batches = plan_embedding_batches(
        pending_inputs,
        max_batch_size=max_batch_size,
        max_input_characters=max_input_characters,
        max_total_characters=max_total_characters,
    )
    return RagBuildPlan(
        repo_root=root_path,
        index_path=resolved_index_path,
        embedding_model_id=resolved_model,
        chunking_policy=chunking_policy,
        corpus_snapshot=corpus_snapshot,
        chunk_count=len(chunks),
        chunk_counts_by_knowledge_base=chunk_counts_by_kb,
        input_character_sizes=tuple(len(chunk_input.input_text) for chunk_input in chunk_inputs),
        pending_embedding_count=len(pending_inputs),
        reusable_embedding_count=len(compatible_vectors),
        planned_batches=planned_batches,
        existing_index_path=resolved_index_path if existing_index is not None else None,
        existing_index_matches=compatible_match,
        existing_index_reason=existing_reason,
        vector_dimensions=vector_dimensions,
    )



def build_rag_index(
    *,
    repo_root: str | Path | None = None,
    index_path: str | Path | None = None,
    embedding_model_id: str | None = None,
    settings: OpenAIEmbeddingSettings | None = None,
    client: OpenAIEmbeddingsClientProtocol | None = None,
    chunking_policy: ChunkingPolicy = ChunkingPolicy(),
    max_batch_size: int = DEFAULT_MAX_EMBEDDING_BATCH_SIZE,
    max_input_characters: int = DEFAULT_MAX_INPUT_CHARACTERS,
    max_total_characters: int = DEFAULT_MAX_TOTAL_CHARACTERS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    allow_new_embeddings: bool = True,
) -> RagBuildResult:
    _validate_timeout_seconds(timeout_seconds)
    if settings is None:
        settings = load_embedding_settings(repo_root)
    if embedding_model_id is not None and embedding_model_id != settings.model:
        raise IndexBuildError("Requested embedding model does not match the configured settings model.")

    root_path = _resolve_repo_root(repo_root)
    resolved_index_path = resolve_runtime_index_path(root_path, index_path)
    documents = load_knowledge_base_documents(root_path)
    corpus_snapshot = build_corpus_snapshot(documents)
    chunks = build_rag_chunks(documents, policy=chunking_policy)
    chunk_inputs = _build_chunk_inputs(chunks)
    chunk_counts_by_kb = _count_chunks_by_knowledge_base(chunks)
    resolved_model = settings.model

    existing_index = _open_existing_index(resolved_index_path)
    compatible_vectors, _, _, vector_dimensions = _classify_existing_index(
        existing_index,
        current_chunks=chunks,
        current_corpus_snapshot=corpus_snapshot,
        embedding_model_id=resolved_model,
        chunking_policy=chunking_policy,
    )
    vectors_by_chunk_id: dict[str, tuple[float, ...]] = dict(compatible_vectors)
    completed_batches: list[RagBatchResult] = []
    pending_inputs = [chunk_input for chunk_input in chunk_inputs if chunk_input.chunk.chunk_id not in compatible_vectors]
    if pending_inputs and not allow_new_embeddings:
        raise IndexBuildError("Reuse-only rebuild needs compatible vectors for every chunk. No embedding request was made; existing index preserved.")
    batch_plans = plan_embedding_batches(
        [(chunk_input.chunk.chunk_id, chunk_input.input_text) for chunk_input in pending_inputs],
        max_batch_size=max_batch_size,
        max_input_characters=max_input_characters,
        max_total_characters=max_total_characters,
    )
    pending_by_id = {chunk_input.chunk.chunk_id: chunk_input for chunk_input in pending_inputs}

    build_start = perf_counter()
    for batch_plan in batch_plans:
        batch_inputs = [pending_by_id[chunk_id].input_text for chunk_id in batch_plan.chunk_ids]
        embedded_batch = embed_texts(
            batch_inputs,
            client=client,
            settings=settings,
            max_batch_size=max_batch_size,
            max_input_characters=max_input_characters,
            max_total_characters=max_total_characters,
            timeout_seconds=timeout_seconds,
        )
        if embedded_batch.requested_model != resolved_model:
            raise IndexBuildError("Embedding adapter returned an unexpected requested model.")
        if embedded_batch.returned_model != resolved_model:
            raise IndexBuildError("Embedding adapter returned an unexpected returned model.")
        if vector_dimensions is None:
            vector_dimensions = len(embedded_batch.vectors[0]) if embedded_batch.vectors else None
        if vector_dimensions is None:
            raise IndexBuildError("Embedding adapter returned no vectors for a non-empty batch.")
        for chunk_id, vector in zip(batch_plan.chunk_ids, embedded_batch.vectors, strict=True):
            if len(vector) != vector_dimensions:
                raise IndexBuildError("Embedding dimensions changed during the build.")
            vectors_by_chunk_id[chunk_id] = vector
        completed_batches.append(
            RagBatchResult(
                chunk_ids=batch_plan.chunk_ids,
                input_character_sizes=batch_plan.input_character_sizes,
                total_input_characters=batch_plan.total_input_characters,
                requested_model=embedded_batch.requested_model,
                returned_model=embedded_batch.returned_model,
                vector_dimensions=vector_dimensions,
                usage=embedded_batch.usage,
                elapsed_seconds=embedded_batch.elapsed_seconds,
            )
        )

    final_documents = load_knowledge_base_documents(root_path)
    final_snapshot = build_corpus_snapshot(final_documents)
    if final_snapshot.snapshot_id != corpus_snapshot.snapshot_id:
        raise IndexBuildError("Corpus changed during index build.")

    if vector_dimensions is None:
        existing_dimensions = existing_index.vector_dimensions if existing_index is not None else None
        if existing_dimensions is None:
            raise IndexBuildError("Cannot determine vector dimensions for index publication.")
        vector_dimensions = existing_dimensions

    manifest_path = _resolve_manifest_path(resolved_index_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_temp_path = _create_temp_path(manifest_path.parent, suffix=".json")
    build_elapsed_seconds = perf_counter() - build_start
    manifest_data = _render_manifest_data(
        repo_root=root_path,
        index_path=resolved_index_path,
        manifest_path=manifest_path,
        corpus_snapshot=final_snapshot,
        embedding_model_id=resolved_model,
        chunking_policy=chunking_policy,
        vector_dimensions=vector_dimensions,
        chunk_count=len(chunks),
        chunk_counts_by_knowledge_base=chunk_counts_by_kb,
        reused_embedding_count=len(compatible_vectors),
        embedded_chunk_count=len(pending_inputs),
        planned_batches=batch_plans,
        completed_batches=tuple(completed_batches),
        existing_index_path=resolved_index_path if existing_index is not None else None,
        build_elapsed_seconds=build_elapsed_seconds,
    )
    try:
        _write_json_file(manifest_temp_path, manifest_data)
        write_vector_index(
            resolved_index_path,
            corpus_snapshot=final_snapshot,
            chunks=chunks,
            vectors_by_chunk_id=vectors_by_chunk_id,
            embedding_model_id=resolved_model,
            vector_dimensions=vector_dimensions,
            chunking_policy=chunking_policy,
        )
        os.replace(manifest_temp_path, manifest_path)
    except Exception as exc:
        _cleanup_temp_path(manifest_temp_path)
        if isinstance(exc, (OpenAIEmbeddingIntegrationError, IndexBuildError)):
            raise
        raise IndexBuildError(str(exc)) from exc

    return RagBuildResult(
        repo_root=root_path,
        index_path=resolved_index_path,
        manifest_path=manifest_path,
        corpus_snapshot=final_snapshot,
        embedding_model_id=resolved_model,
        chunking_policy=chunking_policy,
        vector_dimensions=vector_dimensions,
        chunk_count=len(chunks),
        chunk_counts_by_knowledge_base=chunk_counts_by_kb,
        reused_embedding_count=len(compatible_vectors),
        embedded_chunk_count=len(pending_inputs),
        planned_batches=batch_plans,
        completed_batches=tuple(completed_batches),
        existing_index_path=resolved_index_path if existing_index is not None else None,
        build_elapsed_seconds=build_elapsed_seconds,
    )



def _validate_seed_index(path: Path, root: Path, model: str, dimensions: int | None) -> SQLiteVectorIndex:
    # Read only and allow only the index schema, never arbitrary extra payloads.
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        objects = connection.execute(
            "SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
        ).fetchall()
        if set(objects) != {("table", "metadata"), ("table", "chunks"), ("table", "vectors")}:
            raise RagServiceError("Index contains unexpected database objects.")
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RagServiceError("Index integrity check failed.")
        metadata = dict(connection.execute("SELECT key, value FROM metadata"))
        expected_keys = {
            "schema_version", "index_version", "corpus_snapshot_id", "embedding_model_id",
            "vector_dimensions", "chunking_version", "chunking_max_characters",
            "chunking_overlap_characters", "chunk_count", "source_count", "source_fingerprints",
        }
        if set(metadata) != expected_keys:
            raise RagServiceError("Index contains unexpected or missing metadata.")
        counts = [connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                  for table in ("chunks", "vectors")]
    index = open_vector_index(path)
    documents = load_knowledge_base_documents(root)
    snapshot = build_corpus_snapshot(documents)
    chunks = build_rag_chunks(documents)
    if index.corpus_snapshot != snapshot:
        raise RagServiceError("Index does not match the current corpus snapshot.")
    if index.embedding_model_id != model:
        raise RagServiceError("Index embedding model does not match configuration.")
    if (index.chunking_version != DEFAULT_CHUNKING_VERSION
            or index.chunking_policy != ChunkingPolicy()):
        raise RagServiceError("Index chunking version or policy is incompatible.")
    if index.vector_dimensions <= 0 or (dimensions is not None and index.vector_dimensions != dimensions):
        raise RagServiceError("Index vector dimensions do not match configuration.")
    expected = {chunk.chunk_id: chunk for chunk in chunks}
    actual = {record.chunk.chunk_id: record.chunk for record in index.records}
    if actual != expected or len(index.records) != len(chunks) or counts != [len(chunks), len(chunks)]:
        raise RagServiceError("Index records do not match the canonical corpus chunks.")
    if int(metadata["chunk_count"]) != len(chunks) or int(metadata["source_count"]) != len(documents):
        raise RagServiceError("Index metadata counts are inconsistent.")
    if any(len(record.vector) != index.vector_dimensions for record in index.records):
        raise RagServiceError("Index vector dimensions are inconsistent.")
    return index


def _seed_configuration(model: str | None, dimensions: int | None) -> tuple[str, int | None]:
    resolved = _resolve_embedding_model_id(model)
    if not resolved:
        raise RagServiceError("Set OPENAI_EMBEDDING_MODEL or provide an explicit embedding model.")
    if dimensions is None and os.getenv("RAG_INDEX_VECTOR_DIMENSIONS", "").strip():
        try:
            dimensions = int(os.environ["RAG_INDEX_VECTOR_DIMENSIONS"])
        except ValueError:
            raise RagServiceError("RAG_INDEX_VECTOR_DIMENSIONS must be a positive integer.") from None
    if dimensions is not None and (isinstance(dimensions, bool) or dimensions <= 0):
        raise RagServiceError("Expected vector dimensions must be a positive integer.")
    return resolved, dimensions


def _activate_seed_copy(index: SQLiteVectorIndex, destination: Path, root: Path,
                        model: str, dimensions: int | None, *, exclusive: bool = False) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = _create_temp_path(destination.parent, suffix=".sqlite3")
    try:
        # Copy validated logical records into a fresh database. This intentionally
        # excludes deleted SQLite pages and any unrelated physical file contents.
        write_vector_index(
            temp, corpus_snapshot=index.corpus_snapshot,
            chunks=tuple(record.chunk for record in index.records),
            vectors_by_chunk_id={record.chunk.chunk_id: record.vector for record in index.records},
            embedding_model_id=model, vector_dimensions=index.vector_dimensions,
            chunking_policy=index.chunking_policy,
        )
        _validate_seed_index(temp, root, model, dimensions)
        if exclusive:
            # Hard-link publication is atomic and refuses an existing seed.
            os.link(temp, destination)
        else:
            os.replace(temp, destination)
    finally:
        _cleanup_temp_path(temp)


def validate_rag_index_seed(
    *, repo_root: str | Path | None = None, seed_path: str | Path,
    embedding_model_id: str | None = None, vector_dimensions: int | None = None,
) -> SQLiteVectorIndex:
    """Read-only public validation for a deployment artifact, without credentials or APIs."""
    root = _resolve_repo_root(repo_root)
    seed = _resolve_repo_path(root, seed_path)
    model, dimensions = _seed_configuration(embedding_model_id, vector_dimensions)
    try:
        return _validate_seed_index(seed, root, model, dimensions)
    except RagServiceError:
        raise
    except Exception:
        raise RagServiceError("Prepared seed validation failed.") from None


def package_rag_index_seed(
    *, repo_root: str | Path | None = None, index_path: str | Path | None = None,
    seed_path: str | Path, embedding_model_id: str | None = None,
    vector_dimensions: int | None = None,
) -> RagIndexSeedPackageResult:
    root = _resolve_repo_root(repo_root)
    source = resolve_runtime_index_path(root, index_path)
    seed = _resolve_repo_path(root, seed_path)
    model, dimensions = _seed_configuration(embedding_model_id, vector_dimensions)
    if seed == source or _is_within_path(seed, root / ".rag"):
        raise RagServiceError("Deployment seed must be outside .rag and differ from the active index.")
    if seed.exists():
        raise RagServiceError("Deployment seed already exists; choose a new destination.")
    try:
        index = _validate_seed_index(source, root, model, dimensions)
        _activate_seed_copy(index, seed, root, model, dimensions, exclusive=True)
    except RagServiceError:
        raise
    except Exception:
        raise RagServiceError("Cannot package index: validation or atomic publication failed; active index preserved.") from None
    return RagIndexSeedPackageResult(source, seed, index.corpus_snapshot, model,
                                     index.vector_dimensions, index.chunk_count,
                                     index.source_count, index.chunking_policy)


def bootstrap_rag_index_from_seed(
    *, repo_root: str | Path | None = None, seed_path: str | Path,
    index_path: str | Path | None = None, embedding_model_id: str | None = None,
    vector_dimensions: int | None = None,
) -> RagIndexBootstrapResult:
    root = _resolve_repo_root(repo_root)
    runtime = resolve_runtime_index_path(root, index_path)
    seed = _resolve_repo_path(root, seed_path)
    model, dimensions = _seed_configuration(embedding_model_id, vector_dimensions)
    if seed == runtime:
        raise RagServiceError("Bootstrap seed must differ from the runtime index.")
    try:
        index = _validate_seed_index(runtime, root, model, dimensions)
    except Exception:
        pass
    else:
        return RagIndexBootstrapResult(runtime, seed, index.corpus_snapshot, model,
                                       index.vector_dimensions, index.chunk_count,
                                       index.source_count, False)
    try:
        index = _validate_seed_index(seed, root, model, dimensions)
        _activate_seed_copy(index, runtime, root, model, dimensions)
    except RagServiceError:
        raise
    except Exception:
        raise RagServiceError("Cannot restore seed: validation or atomic activation failed; existing index preserved.") from None
    return RagIndexBootstrapResult(runtime, seed, index.corpus_snapshot, model,
                                   index.vector_dimensions, index.chunk_count,
                                   index.source_count, True)


def render_rag_build_plan(plan: RagBuildPlan) -> str:
    lines = ["RAG index dry-run", f"Repository: {plan.repo_root}", f"Index: {plan.index_path}"]
    lines.append(f"Corpus snapshot: {plan.corpus_snapshot.snapshot_id}")
    lines.append(f"Embedding model: {plan.embedding_model_id or 'unresolved'}")
    lines.append(f"Chunks: {plan.chunk_count}")
    lines.append(
        "Counts by KB: "
        + ", ".join(f"{knowledge_base}={count}" for knowledge_base, count in plan.chunk_counts_by_knowledge_base)
    )
    lines.append(
        "Embedding input characters: "
        + f"min={min(plan.input_character_sizes, default=0)}, "
        + f"max={max(plan.input_character_sizes, default=0)}, "
        + f"total={sum(plan.input_character_sizes)}"
    )
    lines.append(f"Reusable embeddings: {plan.reusable_embedding_count}")
    lines.append(f"Pending embeddings: {plan.pending_embedding_count}")
    lines.append(f"Planned batches: {len(plan.planned_batches)}")
    lines.append(f"Existing index matches: {plan.existing_index_matches}")
    lines.append(f"Existing index status: {plan.existing_index_reason}")
    for index, batch in enumerate(plan.planned_batches, start=1):
        lines.append(
            f"Batch {index}: chunks={len(batch.chunk_ids)} chars={batch.total_input_characters}"
        )
    return "\n".join(lines)



def render_rag_build_result(result: RagBuildResult) -> str:
    lines = ["RAG index build", f"Repository: {result.repo_root}", f"Index: {result.index_path}"]
    lines.append(f"Manifest: {result.manifest_path}")
    lines.append(f"Corpus snapshot: {result.corpus_snapshot.snapshot_id}")
    lines.append(f"Embedding model: {result.embedding_model_id}")
    lines.append(f"Vector dimensions: {result.vector_dimensions}")
    lines.append(f"Chunks: {result.chunk_count}")
    lines.append(
        "Counts by KB: "
        + ", ".join(f"{knowledge_base}={count}" for knowledge_base, count in result.chunk_counts_by_knowledge_base)
    )
    lines.append(f"Reusable embeddings: {result.reused_embedding_count}")
    lines.append(f"Embedded chunks: {result.embedded_chunk_count}")
    lines.append(f"Batches: {len(result.completed_batches)}")
    lines.append(f"Build seconds: {result.build_elapsed_seconds:.3f}")
    return "\n".join(lines)



def _build_chunk_inputs(chunks: Sequence[RagChunk]) -> tuple[_ChunkInput, ...]:
    return tuple(
        _ChunkInput(
            chunk=chunk,
            input_text=build_embedding_input_text(chunk),
            input_hash=build_embedding_input_hash(chunk),
        )
        for chunk in chunks
    )



def build_embedding_input_text(chunk: RagChunk) -> str:
    payload = {
        "applicable_limitations": chunk.applicable_limitations,
        "chunk_hash": chunk.chunk_hash,
        "chunk_id": chunk.chunk_id,
        "chunk_index": chunk.chunk_index,
        "chunk_kind": chunk.chunk_kind,
        "chunk_text": chunk.chunk_text,
        "document_hash": chunk.document_hash,
        "document_title": chunk.document_title,
        "embedding_input_version": EMBEDDING_INPUT_VERSION,
        "evidence_type": chunk.evidence_type,
        "knowledge_base": chunk.knowledge_base,
        "publisher": chunk.publisher,
        "published_updated": chunk.published_updated,
        "repository_relative_path": chunk.repository_relative_path,
        "section_heading_path": chunk.section_heading_path,
        "section_heading_text": chunk.section_heading_text,
        "section_id": chunk.section_id,
        "section_kind": chunk.section_kind,
        "section_line_range": chunk.section_line_range,
        "source_id": chunk.source_id,
        "source_url_text": chunk.source_url_text,
        "source_urls": chunk.source_urls,
        "accessed": chunk.accessed,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))



def build_embedding_input_hash(chunk: RagChunk) -> str:
    return sha256(build_embedding_input_text(chunk).encode("utf-8")).hexdigest()



def _count_chunks_by_knowledge_base(chunks: Sequence[RagChunk]) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for chunk in chunks:
        counts[chunk.knowledge_base] = counts.get(chunk.knowledge_base, 0) + 1
    return tuple(sorted(counts.items()))



def _normalize_embedding_inputs(embedding_inputs: Sequence[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    if isinstance(embedding_inputs, (str, bytes, bytearray)):
        raise IndexBuildError("Embedding inputs must be provided as label/text pairs.")
    try:
        normalized = tuple(embedding_inputs)
    except TypeError as exc:
        raise IndexBuildError("Embedding inputs must be iterable.") from exc
    for index, item in enumerate(normalized):
        if not isinstance(item, tuple) or len(item) != 2:
            raise IndexBuildError(f"Embedding input at position {index} must be a (chunk_id, text) pair.")
        chunk_id, input_text = item
        if not isinstance(chunk_id, str) or not chunk_id.strip():
            raise IndexBuildError(f"Embedding input at position {index} must have a non-empty chunk id.")
        if not isinstance(input_text, str) or not input_text.strip():
            raise IndexBuildError(f"Embedding input at position {index} must have a non-empty text value.")
    return normalized



def _classify_existing_index(
    existing_index: SQLiteVectorIndex | None,
    *,
    current_chunks: Sequence[RagChunk],
    current_corpus_snapshot: CorpusSnapshot,
    embedding_model_id: str | None,
    chunking_policy: ChunkingPolicy,
) -> tuple[dict[str, tuple[float, ...]], bool | None, str, int | None]:
    if existing_index is None:
        return {}, False, "absent", None
    if embedding_model_id is None:
        return {}, None, "model_unresolved", existing_index.vector_dimensions
    if existing_index.chunking_version != DEFAULT_CHUNKING_VERSION:
        return {}, False, "version_mismatch", existing_index.vector_dimensions
    if existing_index.chunking_policy != chunking_policy:
        return {}, False, "policy_mismatch", existing_index.vector_dimensions
    if existing_index.embedding_model_id != embedding_model_id:
        return {}, False, "model_mismatch", existing_index.vector_dimensions

    reusable_vectors: dict[str, tuple[float, ...]] = {}
    by_chunk_id = {record.chunk.chunk_id: record for record in existing_index.records}
    for chunk_input in _build_chunk_inputs(current_chunks):
        record = by_chunk_id.get(chunk_input.chunk.chunk_id)
        if record is None:
            continue
        if chunk_input.input_hash == build_embedding_input_hash(record.chunk):
            reusable_vectors[chunk_input.chunk.chunk_id] = record.vector
    matches = len(reusable_vectors) == len(current_chunks) and existing_index.corpus_snapshot.snapshot_id == current_corpus_snapshot.snapshot_id
    reason = "match" if matches else "snapshot_mismatch"
    return reusable_vectors, matches, reason, existing_index.vector_dimensions


def _open_existing_index(index_path: Path) -> SQLiteVectorIndex | None:
    if not index_path.exists():
        return None
    try:
        return open_vector_index(index_path)
    except FileNotFoundError:
        return None



def _resolve_repo_root(repo_root: str | Path | None) -> Path:
    if repo_root is None:
        return Path.cwd().resolve()
    return Path(repo_root).resolve()



def _resolve_repo_path(repo_root: str | Path | None, path: str | Path) -> Path:
    candidate_path = Path(path)
    if candidate_path.is_absolute():
        return candidate_path.resolve()
    return (_resolve_repo_root(repo_root) / candidate_path).resolve()



def _is_within_path(candidate: Path, parent: Path) -> bool:
    try:
        return candidate.is_relative_to(parent)
    except AttributeError:  # pragma: no cover - Python 3.14 supports is_relative_to
        return str(candidate).startswith(str(parent))



def _resolve_embedding_model_id(embedding_model_id: str | None) -> str | None:
    if embedding_model_id is None:
        value = os.getenv("OPENAI_EMBEDDING_MODEL", "").strip()
        return value or None
    resolved = embedding_model_id.strip()
    return resolved or None



def _validate_batch_limits(
    max_batch_size: int,
    max_input_characters: int,
    max_total_characters: int,
) -> None:
    for label, value in (
        ("max_batch_size", max_batch_size),
        ("max_input_characters", max_input_characters),
        ("max_total_characters", max_total_characters),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise IndexBuildError(f"{label} must be a positive integer.")



def _resolve_manifest_path(index_path: Path) -> Path:
    return index_path.with_name(DEFAULT_RUNTIME_MANIFEST_NAME)



def _create_temp_path(directory: Path, *, suffix: str) -> Path:
    import tempfile

    file_descriptor, temp_name = tempfile.mkstemp(dir=directory, suffix=suffix)
    os.close(file_descriptor)
    return Path(temp_name)



def _write_json_file(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")



def _cleanup_temp_path(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass



def _render_manifest_data(
    *,
    repo_root: Path,
    index_path: Path,
    manifest_path: Path,
    corpus_snapshot: CorpusSnapshot,
    embedding_model_id: str,
    chunking_policy: ChunkingPolicy,
    vector_dimensions: int,
    chunk_count: int,
    chunk_counts_by_knowledge_base: tuple[tuple[str, int], ...],
    reused_embedding_count: int,
    embedded_chunk_count: int,
    planned_batches: tuple[RagEmbeddingBatchPlan, ...],
    completed_batches: tuple[RagBatchResult, ...],
    existing_index_path: Path | None,
    build_elapsed_seconds: float,
) -> dict[str, object]:
    return {
        "build_elapsed_seconds": round(build_elapsed_seconds, 6),
        "chunk_count": chunk_count,
        "chunk_counts_by_knowledge_base": dict(chunk_counts_by_knowledge_base),
        "chunking_policy": {
            "max_chunk_characters": chunking_policy.max_chunk_characters,
            "overlap_characters": chunking_policy.overlap_characters,
        },
        "completed_batches": [
            {
                "chunk_ids": list(batch.chunk_ids),
                "elapsed_seconds": round(batch.elapsed_seconds, 6),
                "input_character_sizes": list(batch.input_character_sizes),
                "requested_model": batch.requested_model,
                "returned_model": batch.returned_model,
                "total_input_characters": batch.total_input_characters,
                "usage": None
                if batch.usage is None
                else {
                    "prompt_tokens": batch.usage.prompt_tokens,
                    "total_tokens": batch.usage.total_tokens,
                },
                "vector_dimensions": batch.vector_dimensions,
            }
            for batch in completed_batches
        ],
        "corpus_snapshot_id": corpus_snapshot.snapshot_id,
        "embedding_model_id": embedding_model_id,
        "embedded_chunk_count": embedded_chunk_count,
        "existing_index_path": None if existing_index_path is None else str(existing_index_path),
        "index_path": str(index_path),
        "manifest_path": str(manifest_path),
        "planned_batches": [
            {
                "chunk_ids": list(batch.chunk_ids),
                "input_character_sizes": list(batch.input_character_sizes),
                "total_input_characters": batch.total_input_characters,
            }
            for batch in planned_batches
        ],
        "repo_root": str(repo_root),
        "reused_embedding_count": reused_embedding_count,
        "vector_dimensions": vector_dimensions,
    }


__all__ = [
    "DEFAULT_RUNTIME_INDEX_PATH",
    "EMBEDDING_INPUT_VERSION",
    "RagBatchResult",
    "RagBuildPlan",
    "RagBuildResult",
    "RagEmbeddingBatchPlan",
    "RagServiceError",
    "RagIndexSeedPackageResult",
    "RagIndexBootstrapResult",
    "build_embedding_input_hash",
    "build_embedding_input_text",
    "build_rag_index",
    "package_rag_index_seed",
    "validate_rag_index_seed",
    "bootstrap_rag_index_from_seed",
    "plan_embedding_batches",
    "plan_rag_index_build",
    "render_rag_build_plan",
    "render_rag_build_result",
    "resolve_runtime_index_path",
]
