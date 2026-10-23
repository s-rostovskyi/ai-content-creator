from __future__ import annotations

"""Query-driven retrieval and bounded context assembly for the RAG corpus."""

from dataclasses import dataclass
from hashlib import sha256
from datetime import datetime, timezone
import math
import re
import os
from pathlib import Path
from typing import Literal, Mapping, Sequence

from src.document_processor import load_knowledge_base_documents
from src.embedding_integration import (
    DEFAULT_TIMEOUT_SECONDS,
    EmbeddedBatch,
    EmbeddingUsageMetrics,
    OpenAIEmbeddingIntegrationError,
    OpenAIEmbeddingSettings,
    OpenAIEmbeddingsClientProtocol,
    embed_texts,
    load_embedding_settings,
)
from src.rag_index import CorpusSnapshot, SearchResult, SQLiteVectorIndex, build_corpus_snapshot, open_vector_index
from src.rag_service import resolve_runtime_index_path

Channel = Literal["instagram", "linkedin", "email"]

DEFAULT_PRIMARY_TOP_K = 3
DEFAULT_SECONDARY_TOP_K = 3
DEFAULT_PRIMARY_MINIMUM_SIMILARITY = 0.18
DEFAULT_SECONDARY_MINIMUM_SIMILARITY = 0.12
DEFAULT_MAX_CONTEXT_CHARACTERS = 6000
DEFAULT_RANKING_CANDIDATE_MULTIPLIER = 4
DEFAULT_LEXICAL_RELEVANCE_WEIGHT = 0.35
DEFAULT_FACT_PRIORITY_BONUS = 0.08


class RagRetrievalError(Exception):
    """Base error for retrieval orchestration failures."""


class RetrievalConfigurationError(RagRetrievalError):
    """Raised when retrieval inputs or configured settings are invalid."""


class RetrievalBlockedError(RagRetrievalError):
    """Raised when retrieval cannot produce usable primary evidence."""


class RetrievalStaleCorpusError(RagRetrievalError):
    """Raised when the corpus changes while a retrieval is in progress."""


@dataclass(frozen=True)
class RetrievedContextSourceManifestEntry:
    repository_relative_path: str
    knowledge_base: Literal["primary", "secondary"]
    document_title: str
    source_urls: tuple[str, ...]
    source_url_text: str
    publisher: str
    published_updated: str
    accessed: str
    evidence_type: str
    chunk_ids: tuple[str, ...]
    chunk_scores: tuple[float, ...]
    chunk_kinds: tuple[str, ...]


@dataclass(frozen=True)
class RetrievedContextMeasurements:
    primary_selected_count: int
    primary_fact_count: int
    secondary_selected_count: int
    secondary_fact_count: int
    included_source_count: int
    serialized_context_characters: int
    max_serialized_characters: int


@dataclass(frozen=True)
class RetrievedContextBundle:
    primary_context: str
    secondary_context: str
    source_manifest: tuple[RetrievedContextSourceManifestEntry, ...]
    retrieval_measurements: RetrievedContextMeasurements


@dataclass(frozen=True)
class RetrievalManifest:
    corpus_snapshot_id: str
    embedding_model_id: str
    requested_model_id: str
    returned_model_id: str
    query_digest: str
    query_character_count: int
    query_usage: EmbeddingUsageMetrics | None
    query_elapsed_seconds: float
    included_sources: tuple[RetrievedContextSourceManifestEntry, ...]
    omission_reasons: tuple[str, ...]


@dataclass(frozen=True)
class RagRetrievalPlan:
    repo_root: Path
    index_path: Path
    query_digest: str
    query_character_count: int
    embedding_model_id: str | None
    corpus_snapshot: CorpusSnapshot
    existing_index_path: Path | None
    existing_index_matches: bool | None
    existing_index_reason: str
    primary_top_k: int
    secondary_top_k: int
    primary_minimum_similarity: float
    secondary_minimum_similarity: float
    max_context_characters: int


@dataclass(frozen=True)
class RagRetrievalResult:
    repo_root: Path
    index_path: Path
    query_text: str
    query_digest: str
    query_character_count: int
    corpus_snapshot: CorpusSnapshot
    embedding_model_id: str
    query_usage: EmbeddingUsageMetrics | None
    query_elapsed_seconds: float
    primary_results: tuple[SearchResult, ...]
    secondary_results: tuple[SearchResult, ...]
    blocked_reason: str | None
    context_bundle: RetrievedContextBundle | None
    manifest: RetrievalManifest


@dataclass(frozen=True)
class RankedRetrievalCandidate:
    search_result: SearchResult
    lexical_relevance: float
    combined_score: float



def build_retrieval_query(channel: Channel | str, campaign_brief: str, revision_feedback: str = "") -> str:
    normalized_channel = _validate_channel(channel)
    normalized_brief = _require_nonempty_string(campaign_brief, "campaign_brief")
    normalized_feedback = revision_feedback.strip()
    return "\n".join(
        (
            "## Retrieval query",
            f"Channel: {normalized_channel}",
            "Campaign brief:",
            normalized_brief,
            "Revision feedback:",
            normalized_feedback if normalized_feedback else "None",
            "End of retrieval query.",
        )
    )



def plan_rag_context_retrieval(
    *,
    repo_root: str | Path | None = None,
    index_path: str | Path | None = None,
    channel: Channel | str,
    campaign_brief: str,
    revision_feedback: str = "",
    embedding_model_id: str | None = None,
    primary_top_k: int = DEFAULT_PRIMARY_TOP_K,
    secondary_top_k: int = DEFAULT_SECONDARY_TOP_K,
    primary_minimum_similarity: float = DEFAULT_PRIMARY_MINIMUM_SIMILARITY,
    secondary_minimum_similarity: float = DEFAULT_SECONDARY_MINIMUM_SIMILARITY,
    max_context_characters: int = DEFAULT_MAX_CONTEXT_CHARACTERS,
) -> RagRetrievalPlan:
    root_path = _resolve_repo_root(repo_root)
    resolved_index_path = resolve_runtime_index_path(root_path, index_path)
    query_text = build_retrieval_query(channel, campaign_brief, revision_feedback)
    query_digest = _hash_text(query_text)
    query_character_count = len(query_text)
    documents = load_knowledge_base_documents(root_path)
    corpus_snapshot = build_corpus_snapshot(documents)
    resolved_model = _resolve_embedding_model_id(embedding_model_id)
    existing_index = _open_existing_index(resolved_index_path)
    existing_matches, existing_reason = _classify_existing_index(
        existing_index,
        current_corpus_snapshot=corpus_snapshot,
        embedding_model_id=resolved_model,
    )
    return RagRetrievalPlan(
        repo_root=root_path,
        index_path=resolved_index_path,
        query_digest=query_digest,
        query_character_count=query_character_count,
        embedding_model_id=resolved_model,
        corpus_snapshot=corpus_snapshot,
        existing_index_path=resolved_index_path if existing_index is not None else None,
        existing_index_matches=existing_matches,
        existing_index_reason=existing_reason,
        primary_top_k=_validate_positive_int(primary_top_k, "primary_top_k"),
        secondary_top_k=_validate_positive_int(secondary_top_k, "secondary_top_k"),
        primary_minimum_similarity=_validate_similarity_threshold(primary_minimum_similarity, "primary_minimum_similarity"),
        secondary_minimum_similarity=_validate_similarity_threshold(secondary_minimum_similarity, "secondary_minimum_similarity"),
        max_context_characters=_validate_positive_int(max_context_characters, "max_context_characters"),
    )



def retrieve_rag_context(
    *,
    repo_root: str | Path | None = None,
    index_path: str | Path | None = None,
    channel: Channel | str,
    campaign_brief: str,
    revision_feedback: str = "",
    embedding_model_id: str | None = None,
    settings: OpenAIEmbeddingSettings | None = None,
    client: OpenAIEmbeddingsClientProtocol | None = None,
    primary_top_k: int = DEFAULT_PRIMARY_TOP_K,
    secondary_top_k: int = DEFAULT_SECONDARY_TOP_K,
    primary_minimum_similarity: float = DEFAULT_PRIMARY_MINIMUM_SIMILARITY,
    secondary_minimum_similarity: float = DEFAULT_SECONDARY_MINIMUM_SIMILARITY,
    max_context_characters: int = DEFAULT_MAX_CONTEXT_CHARACTERS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> RagRetrievalResult:
    root_path = _resolve_repo_root(repo_root)
    resolved_index_path = resolve_runtime_index_path(root_path, index_path)
    query_text = build_retrieval_query(channel, campaign_brief, revision_feedback)
    query_digest = _hash_text(query_text)
    query_character_count = len(query_text)
    documents = load_knowledge_base_documents(root_path)
    initial_snapshot = build_corpus_snapshot(documents)

    resolved_settings = settings
    if resolved_settings is None:
        resolved_settings = load_embedding_settings(root_path)
    if embedding_model_id is not None and embedding_model_id != resolved_settings.model:
        raise RetrievalConfigurationError("Requested embedding model does not match the configured settings model.")

    index = _open_existing_index(resolved_index_path)
    if index is None:
        raise RetrievalConfigurationError(f"Missing retrieval index: {resolved_index_path}")

    if index.corpus_snapshot.snapshot_id != initial_snapshot.snapshot_id:
        raise RetrievalStaleCorpusError("Retrieval index snapshot does not match the current corpus snapshot.")
    if index.embedding_model_id != resolved_settings.model:
        raise RetrievalConfigurationError("Retrieval index embedding model does not match the configured model.")

    query_batch = _embed_query(
        query_text,
        client=client,
        settings=resolved_settings,
        timeout_seconds=timeout_seconds,
    )
    query_vector = query_batch.vectors[0]

    primary_search_results = index.search_primary(
        query_vector,
        top_k=_candidate_search_limit(index, "primary", _validate_positive_int(primary_top_k, "primary_top_k")),
        minimum_similarity=_validate_similarity_threshold(primary_minimum_similarity, "primary_minimum_similarity"),
        current_corpus_snapshot=initial_snapshot,
    )
    secondary_search_results = index.search_secondary(
        query_vector,
        top_k=_candidate_search_limit(index, "secondary", _validate_positive_int(secondary_top_k, "secondary_top_k")),
        minimum_similarity=_validate_similarity_threshold(secondary_minimum_similarity, "secondary_minimum_similarity"),
        current_corpus_snapshot=initial_snapshot,
    )

    ranked_primary_candidates = _rank_search_results(query_text, primary_search_results)
    ranked_secondary_candidates = _rank_search_results(query_text, secondary_search_results)
    selected_primary_results, primary_ranking_omissions = _select_ranked_candidates(
        ranked_primary_candidates,
        max_selected=_validate_positive_int(primary_top_k, "primary_top_k"),
    )
    selected_secondary_results, secondary_ranking_omissions = _select_ranked_candidates(
        ranked_secondary_candidates,
        max_selected=_validate_positive_int(secondary_top_k, "secondary_top_k"),
    )

    final_snapshot = build_corpus_snapshot(load_knowledge_base_documents(root_path))
    if final_snapshot.snapshot_id != initial_snapshot.snapshot_id:
        raise RetrievalStaleCorpusError("Corpus changed during retrieval.")

    blocked_reason: str | None = None
    context_bundle: RetrievedContextBundle | None = None
    omission_reasons: list[str] = list(primary_ranking_omissions) + list(secondary_ranking_omissions)
    if not any(result.chunk.chunk_kind == "facts" for result in selected_primary_results):
        blocked_reason = "No primary factual evidence met the configured similarity threshold."
        omission_reasons.append("no_primary_factual_evidence")
    else:
        context_bundle, budget_omissions = _assemble_retrieved_context(
            primary_results=selected_primary_results,
            secondary_results=selected_secondary_results,
            max_context_characters=_validate_positive_int(max_context_characters, "max_context_characters"),
        )
        omission_reasons.extend(budget_omissions)
        if context_bundle.retrieval_measurements.primary_fact_count == 0:
            blocked_reason = "Primary factual evidence did not fit within the context budget."
            omission_reasons.append("primary_factual_evidence_exceeded_context_budget")

    manifest = RetrievalManifest(
        corpus_snapshot_id=initial_snapshot.snapshot_id,
        embedding_model_id=resolved_settings.model,
        requested_model_id=query_batch.requested_model,
        returned_model_id=query_batch.returned_model,
        query_digest=query_digest,
        query_character_count=query_character_count,
        query_usage=query_batch.usage,
        query_elapsed_seconds=query_batch.elapsed_seconds,
        included_sources=() if context_bundle is None else context_bundle.source_manifest,
        omission_reasons=tuple(dict.fromkeys(omission_reasons)),
    )

    return RagRetrievalResult(
        repo_root=root_path,
        index_path=resolved_index_path,
        query_text=query_text,
        query_digest=query_digest,
        query_character_count=query_character_count,
        corpus_snapshot=initial_snapshot,
        embedding_model_id=resolved_settings.model,
        query_usage=query_batch.usage,
        query_elapsed_seconds=query_batch.elapsed_seconds,
        primary_results=tuple(ranked_primary_candidates),
        secondary_results=tuple(ranked_secondary_candidates),
        blocked_reason=blocked_reason,
        context_bundle=context_bundle,
        manifest=manifest,
    )




def _candidate_search_limit(index: SQLiteVectorIndex, knowledge_base: Literal["primary", "secondary"], desired_top_k: int) -> int:
    total_count = sum(1 for record in index.records if record.chunk.knowledge_base == knowledge_base)
    if total_count <= desired_top_k:
        return max(1, total_count)
    expanded_limit = desired_top_k * DEFAULT_RANKING_CANDIDATE_MULTIPLIER
    return min(total_count, max(desired_top_k, expanded_limit))



def _rank_search_results(query_text: str, results: Sequence[SearchResult]) -> tuple[SearchResult, ...]:
    query_terms = _tokenize_relevance_terms(query_text)
    scored_results: list[RankedRetrievalCandidate] = []
    for result in results:
        lexical_relevance = _lexical_relevance(query_terms, _candidate_text_for_relevance(result.chunk))
        combined_score = result.similarity + (lexical_relevance * DEFAULT_LEXICAL_RELEVANCE_WEIGHT)
        if result.chunk.chunk_kind == "facts":
            combined_score += DEFAULT_FACT_PRIORITY_BONUS
        scored_results.append(
            RankedRetrievalCandidate(
                search_result=result,
                lexical_relevance=lexical_relevance,
                combined_score=combined_score,
            )
        )
    scored_results.sort(
        key=lambda candidate: (
            -candidate.combined_score,
            -candidate.search_result.similarity,
            -candidate.lexical_relevance,
            candidate.search_result.chunk.chunk_id,
        )
    )
    return tuple(candidate.search_result for candidate in scored_results)



def _select_ranked_candidates(
    ranked_results: Sequence[SearchResult],
    *,
    max_selected: int,
) -> tuple[tuple[SearchResult, ...], list[str]]:
    supported_results = tuple(result for result in ranked_results if result.chunk.chunk_kind in {"facts", "editorial"})
    fact_results = tuple(result for result in supported_results if result.chunk.chunk_kind == "facts")
    editorial_results = tuple(result for result in supported_results if result.chunk.chunk_kind == "editorial")
    unsupported_results = tuple(result for result in ranked_results if result.chunk.chunk_kind not in {"facts", "editorial"})

    selected: list[SearchResult] = []
    omission_reasons: list[str] = [f"{result.chunk.chunk_id}:unsupported_chunk_kind" for result in unsupported_results]

    for result in (*fact_results, *editorial_results):
        if len(selected) >= max_selected:
            omission_reasons.append(f"{result.chunk.chunk_id}:ranked_out")
            continue
        selected.append(result)

    return tuple(selected), omission_reasons



def _candidate_text_for_relevance(chunk: RagChunk) -> str:
    parts = [chunk.document_title, *chunk.section_heading_path, chunk.chunk_text, chunk.applicable_limitations]
    return "\n".join(part for part in parts if part)



def _tokenize_relevance_terms(text: str) -> set[str]:
    tokens = set()
    for raw_token in re.findall(r"[a-z0-9]+", text.lower()):
        token = raw_token.strip()
        if not token or token in _RETRIEVAL_STOPWORDS:
            continue
        tokens.add(_normalize_relevance_token(token))
    return tokens



def _normalize_relevance_token(token: str) -> str:
    for suffix in ("'s", "es", "s", "ed", "ing"):
        if token.endswith(suffix) and len(token) > len(suffix) + 2:
            return token[: -len(suffix)]
    return token



def _lexical_relevance(query_terms: set[str], candidate_text: str) -> float:
    candidate_terms = _tokenize_relevance_terms(candidate_text)
    if not query_terms or not candidate_terms:
        return 0.0
    overlap = len(query_terms & candidate_terms)
    return overlap / len(query_terms)


_RETRIEVAL_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "be",
    "by",
    "do",
    "for",
    "from",
    "have",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "me",
    "my",
    "of",
    "on",
    "or",
    "our",
    "that",
    "the",
    "this",
    "to",
    "with",
    "you",
}



def render_rag_retrieval_plan(plan: RagRetrievalPlan) -> str:
    lines = ["RAG retrieval dry-run", f"Repository: {plan.repo_root}", f"Index: {plan.index_path}"]
    lines.append(f"Query characters: {plan.query_character_count}")
    lines.append(f"Query digest: {plan.query_digest}")
    lines.append(f"Embedding model: {plan.embedding_model_id if plan.embedding_model_id is not None else 'unresolved'}")
    lines.append(f"Primary top-k: {plan.primary_top_k} @ >= {plan.primary_minimum_similarity}")
    lines.append(f"Secondary top-k: {plan.secondary_top_k} @ >= {plan.secondary_minimum_similarity}")
    lines.append(f"Max context characters: {plan.max_context_characters}")
    lines.append(f"Existing index: {plan.existing_index_path if plan.existing_index_path is not None else 'missing'}")
    lines.append(f"Existing index matches: {plan.existing_index_matches}")
    lines.append(f"Existing index status: {plan.existing_index_reason}")
    lines.append(f"Corpus snapshot: {plan.corpus_snapshot.snapshot_id}")
    return "\n".join(lines)



def render_rag_retrieval_result(result: RagRetrievalResult) -> str:
    measurements = result.context_bundle.retrieval_measurements if result.context_bundle is not None else None
    lines = ["RAG retrieval", f"Repository: {result.repo_root}", f"Index: {result.index_path}"]
    lines.append(f"Query digest: {result.query_digest}")
    lines.append(f"Requested embedding model: {result.manifest.requested_model_id}")
    lines.append(f"Returned embedding model: {result.manifest.returned_model_id}")
    lines.append(f"Configured embedding model: {result.embedding_model_id}")
    lines.append(f"Query elapsed seconds: {result.query_elapsed_seconds:.3f}")
    lines.append(f"Query usage: {_format_query_usage(result.query_usage)}")
    lines.append(f"Primary results: {len(result.primary_results)}")
    lines.append(f"Secondary results: {len(result.secondary_results)}")
    if result.blocked_reason is not None:
        lines.append(f"Blocked: {result.blocked_reason}")
    lines.append(f"Primary selected chunks: {measurements.primary_selected_count if measurements is not None else 0}")
    lines.append(f"Secondary selected chunks: {measurements.secondary_selected_count if measurements is not None else 0}")
    lines.append(f"Distinct sources: {measurements.included_source_count if measurements is not None else 0}")
    if measurements is not None:
        lines.append(
            f"Serialized context characters: {measurements.serialized_context_characters} / {measurements.max_serialized_characters}"
        )
        lines.append("Included chunks:")
        lines.extend(_render_included_chunk_summaries(result))
    lines.append(f"Omission reasons: {', '.join(result.manifest.omission_reasons) if result.manifest.omission_reasons else 'none'}")
    lines.append(f"Corpus snapshot: {result.corpus_snapshot.snapshot_id}")
    return "\n".join(lines)



def build_rag_retrieval_evidence_payload(
    result: RagRetrievalResult,
    *,
    channel: Channel | str,
    retrieval_settings: Mapping[str, object],
    saved_at_utc: str | None = None,
) -> dict[str, object]:
    included_chunk_ids = {
        chunk_id
        for entry in result.manifest.included_sources
        for chunk_id in entry.chunk_ids
    }
    ranked_candidates = {
        "primary": [
            _serialize_candidate_result(result_item, pool_name="primary", rank=index + 1)
            for index, result_item in enumerate(result.primary_results)
        ],
        "secondary": [
            _serialize_candidate_result(result_item, pool_name="secondary", rank=index + 1)
            for index, result_item in enumerate(result.secondary_results)
        ],
    }
    included_chunks = [
        _serialize_included_chunk_result(result_item, pool_name="primary", rank=index + 1)
        for index, result_item in enumerate(result.primary_results)
        if result_item.chunk.chunk_id in included_chunk_ids
    ] + [
        _serialize_included_chunk_result(result_item, pool_name="secondary", rank=index + 1)
        for index, result_item in enumerate(result.secondary_results)
        if result_item.chunk.chunk_id in included_chunk_ids
    ]
    return {
        "saved_at_utc": saved_at_utc or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "channel": channel,
        "retrieval_status": "blocked" if result.blocked_reason is not None else "success",
        "query": {
            "text": result.query_text,
            "digest": result.query_digest,
            "character_count": result.query_character_count,
        },
        "corpus_snapshot_id": result.corpus_snapshot.snapshot_id,
        "retrieval_settings": dict(retrieval_settings),
        "manifest": {
            "corpus_snapshot_id": result.manifest.corpus_snapshot_id,
            "embedding_model_id": result.manifest.embedding_model_id,
            "requested_model_id": result.manifest.requested_model_id,
            "returned_model_id": result.manifest.returned_model_id,
            "query_digest": result.manifest.query_digest,
            "query_character_count": result.manifest.query_character_count,
            "query_usage": _serialize_query_usage(result.manifest.query_usage),
            "query_elapsed_seconds": result.manifest.query_elapsed_seconds,
            "omission_reasons": list(result.manifest.omission_reasons),
            "included_sources": [_serialize_source_manifest_entry(entry) for entry in result.manifest.included_sources],
        },
        "blocked_reason": result.blocked_reason,
        "query_usage": _serialize_query_usage(result.query_usage),
        "query_elapsed_seconds": result.query_elapsed_seconds,
        "source_manifest": [_serialize_source_manifest_entry(entry) for entry in result.manifest.included_sources],
        "ranked_candidates": ranked_candidates,
        "included_chunks": included_chunks,
        "retrieved_context": {
            "primary": result.context_bundle.primary_context if result.context_bundle is not None else "",
            "secondary": result.context_bundle.secondary_context if result.context_bundle is not None else "",
        },
        "measurements": {
            "primary_selected_count": result.context_bundle.retrieval_measurements.primary_selected_count if result.context_bundle is not None else 0,
            "primary_fact_count": result.context_bundle.retrieval_measurements.primary_fact_count if result.context_bundle is not None else 0,
            "secondary_selected_count": result.context_bundle.retrieval_measurements.secondary_selected_count if result.context_bundle is not None else 0,
            "secondary_fact_count": result.context_bundle.retrieval_measurements.secondary_fact_count if result.context_bundle is not None else 0,
            "included_source_count": result.context_bundle.retrieval_measurements.included_source_count if result.context_bundle is not None else 0,
            "serialized_context_characters": result.context_bundle.retrieval_measurements.serialized_context_characters if result.context_bundle is not None else 0,
            "max_serialized_characters": result.context_bundle.retrieval_measurements.max_serialized_characters if result.context_bundle is not None else int(retrieval_settings.get("max_context_characters", 0) or 0),
        },
    }



def _render_included_chunk_summaries(result: RagRetrievalResult) -> list[str]:
    included_chunk_ids = {
        chunk_id
        for entry in result.manifest.included_sources
        for chunk_id in entry.chunk_ids
    }
    lines: list[str] = []
    for pool_name, results in (("primary", result.primary_results), ("secondary", result.secondary_results)):
        for search_result in results:
            if search_result.chunk.chunk_id not in included_chunk_ids:
                continue
            chunk = search_result.chunk
            lines.append(
                "- "
                f"{pool_name}/{chunk.chunk_kind} | "
                f"score={search_result.similarity:.6f} | "
                f"source={chunk.repository_relative_path} | "
                f"chunk={chunk.chunk_id} | "
                f"excerpt={_short_excerpt(chunk.chunk_text)}"
            )
    return lines



def _serialize_candidate_result(result: SearchResult, *, pool_name: str, rank: int) -> dict[str, object]:
    chunk = result.chunk
    return {
        "rank": rank,
        "pool": pool_name,
        "chunk_id": chunk.chunk_id,
        "source_path": chunk.repository_relative_path,
        "knowledge_base": chunk.knowledge_base,
        "chunk_kind": chunk.chunk_kind,
        "similarity": round(result.similarity, 6),
        "document_title": chunk.document_title,
        "section_id": chunk.section_id,
        "section_heading_path": list(chunk.section_heading_path),
        "section_line_range": list(chunk.section_line_range),
        "chunk_line_range": list(chunk.chunk_line_range),
    }



def _serialize_included_chunk_result(result: SearchResult, *, pool_name: str, rank: int) -> dict[str, object]:
    chunk = result.chunk
    payload = _serialize_candidate_result(result, pool_name=pool_name, rank=rank)
    payload.update(
        {
            "source_urls": list(chunk.source_urls),
            "source_url_text": chunk.source_url_text,
            "publisher": chunk.publisher,
            "published_updated": chunk.published_updated,
            "accessed": chunk.accessed,
            "evidence_type": chunk.evidence_type,
            "chunk_text": chunk.chunk_text,
            "applicable_limitations": chunk.applicable_limitations,
        }
    )
    return payload



def _serialize_source_manifest_entry(entry: RetrievedContextSourceManifestEntry) -> dict[str, object]:
    return {
        "repository_relative_path": entry.repository_relative_path,
        "knowledge_base": entry.knowledge_base,
        "document_title": entry.document_title,
        "source_urls": list(entry.source_urls),
        "source_url_text": entry.source_url_text,
        "publisher": entry.publisher,
        "published_updated": entry.published_updated,
        "accessed": entry.accessed,
        "evidence_type": entry.evidence_type,
        "chunk_ids": list(entry.chunk_ids),
        "chunk_scores": list(entry.chunk_scores),
        "chunk_kinds": list(entry.chunk_kinds),
    }



def _serialize_query_usage(usage: EmbeddingUsageMetrics | None) -> dict[str, int | None] | None:
    if usage is None:
        return None
    return {"prompt_tokens": usage.prompt_tokens, "total_tokens": usage.total_tokens}



def _format_query_usage(usage: EmbeddingUsageMetrics | None) -> str:
    if usage is None:
        return "none"
    return f"prompt_tokens={usage.prompt_tokens}, total_tokens={usage.total_tokens}"



def _short_excerpt(text: str, *, limit: int = 120) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: max(limit - 1, 1)].rstrip() + "?"



def _assemble_retrieved_context(
    *,
    primary_results: Sequence[SearchResult],
    secondary_results: Sequence[SearchResult],
    max_context_characters: int,
) -> tuple[RetrievedContextBundle, list[str]]:
    selected: list[tuple[str, SearchResult]] = []
    for result in primary_results:
        selected.append(("primary", result))
    for result in secondary_results:
        selected.append(("secondary", result))

    primary_sections: dict[str, list[str]] = {"facts": [], "editorial": []}
    secondary_sections: dict[str, list[str]] = {"facts": [], "editorial": []}
    source_entries: dict[str, RetrievedContextSourceManifestEntry] = {}
    omission_reasons: list[str] = []

    for pool_name, result in selected:
        if result.chunk.chunk_kind not in {"facts", "editorial"}:
            omission_reasons.append(f"{result.chunk.chunk_id}:unsupported_chunk_kind")
            continue

        block_text = _render_context_block(result, pool_name=pool_name)
        if pool_name == "primary":
            candidate_primary_sections = {kind: list(blocks) for kind, blocks in primary_sections.items()}
            candidate_secondary_sections = {kind: list(blocks) for kind, blocks in secondary_sections.items()}
            candidate_primary_sections[result.chunk.chunk_kind].append(block_text)
        else:
            candidate_primary_sections = {kind: list(blocks) for kind, blocks in primary_sections.items()}
            candidate_secondary_sections = {kind: list(blocks) for kind, blocks in secondary_sections.items()}
            candidate_secondary_sections[result.chunk.chunk_kind].append(block_text)

        candidate_primary_context = _render_pool_context("Primary retrieved context", candidate_primary_sections)
        candidate_secondary_context = _render_pool_context("Secondary retrieved context", candidate_secondary_sections)
        candidate_total = len(candidate_primary_context) + len(candidate_secondary_context)
        if candidate_total > max_context_characters:
            omission_reasons.append(f"{result.chunk.chunk_id}:budget_exceeded")
            continue

        if pool_name == "primary":
            primary_sections[result.chunk.chunk_kind].append(block_text)
        else:
            secondary_sections[result.chunk.chunk_kind].append(block_text)
        source_entries[result.chunk.repository_relative_path] = _merge_source_manifest_entry(
            source_entries.get(result.chunk.repository_relative_path), result
        )

    primary_context = _render_pool_context("Primary retrieved context", primary_sections)
    secondary_context = _render_pool_context("Secondary retrieved context", secondary_sections)
    retrieval_measurements = RetrievedContextMeasurements(
        primary_selected_count=sum(len(blocks) for blocks in primary_sections.values()),
        primary_fact_count=len(primary_sections["facts"]),
        secondary_selected_count=sum(len(blocks) for blocks in secondary_sections.values()),
        secondary_fact_count=len(secondary_sections["facts"]),
        included_source_count=len(source_entries),
        serialized_context_characters=len(primary_context) + len(secondary_context),
        max_serialized_characters=max_context_characters,
    )
    bundle = RetrievedContextBundle(
        primary_context=primary_context,
        secondary_context=secondary_context,
        source_manifest=tuple(
            sorted(source_entries.values(), key=lambda entry: entry.repository_relative_path)
        ),
        retrieval_measurements=retrieval_measurements,
    )
    return bundle, omission_reasons



def _render_pool_context(title: str, sections: dict[str, list[str]]) -> str:
    lines: list[str] = []
    ordered_sections = (("facts", "Facts"), ("editorial", "Editorial interpretation"))
    for section_key, section_title in ordered_sections:
        blocks = sections.get(section_key, [])
        if not blocks:
            continue
        if not lines:
            lines.append(f"# {title}")
        lines.append(f"## {section_title}")
        lines.extend(blocks)
    return "\n\n".join(lines).strip()



def _render_context_block(result: SearchResult, *, pool_name: str) -> str:
    chunk = result.chunk
    chunk_kind_label = "Facts" if chunk.chunk_kind == "facts" else "Editorial interpretation"
    lines = [
        f"### {chunk_kind_label}",
        f"Source path: {chunk.repository_relative_path}",
        f"Chunk ID: {chunk.chunk_id}",
        f"Similarity: {result.similarity:.6f}",
        f"Section ID: {chunk.section_id}",
        f"Section heading: {' / '.join(chunk.section_heading_path)}",
        f"Section lines: {chunk.section_line_range[0]}-{chunk.section_line_range[1]}",
        f"Chunk lines: {chunk.chunk_line_range[0]}-{chunk.chunk_line_range[1]}",
        f"Applicable limitations: {chunk.applicable_limitations}",
        f"Provenance: {chunk.source_url_text} | {chunk.publisher} | {chunk.published_updated} | {chunk.accessed} | {chunk.evidence_type}",
        f"Pool: {pool_name}",
        "",
        chunk.chunk_text,
    ]
    return "\n".join(lines).strip()



def _merge_source_manifest_entry(
    existing: RetrievedContextSourceManifestEntry | None,
    result: SearchResult,
) -> RetrievedContextSourceManifestEntry:
    chunk = result.chunk
    if existing is None:
        return RetrievedContextSourceManifestEntry(
            repository_relative_path=chunk.repository_relative_path,
            knowledge_base=chunk.knowledge_base,
            document_title=chunk.document_title,
            source_urls=chunk.source_urls,
            source_url_text=chunk.source_url_text,
            publisher=chunk.publisher,
            published_updated=chunk.published_updated,
            accessed=chunk.accessed,
            evidence_type=chunk.evidence_type,
            chunk_ids=(chunk.chunk_id,),
            chunk_scores=(round(result.similarity, 6),),
            chunk_kinds=(chunk.chunk_kind,),
        )
    return RetrievedContextSourceManifestEntry(
        repository_relative_path=existing.repository_relative_path,
        knowledge_base=existing.knowledge_base,
        document_title=existing.document_title,
        source_urls=existing.source_urls,
        source_url_text=existing.source_url_text,
        publisher=existing.publisher,
        published_updated=existing.published_updated,
        accessed=existing.accessed,
        evidence_type=existing.evidence_type,
        chunk_ids=existing.chunk_ids + (chunk.chunk_id,),
        chunk_scores=existing.chunk_scores + (round(result.similarity, 6),),
        chunk_kinds=existing.chunk_kinds + (chunk.chunk_kind,),
    )



def _embed_query(
    query_text: str,
    *,
    client: OpenAIEmbeddingsClientProtocol | None,
    settings: OpenAIEmbeddingSettings,
    timeout_seconds: float,
) -> EmbeddedBatch:
    try:
        batch = embed_texts(
            [query_text],
            client=client,
            settings=settings,
            max_batch_size=1,
            timeout_seconds=timeout_seconds,
        )
    except OpenAIEmbeddingIntegrationError as exc:
        raise RetrievalConfigurationError(str(exc) or exc.__class__.__name__) from exc
    if batch.requested_model != settings.model or batch.returned_model != settings.model:
        raise RetrievalConfigurationError("Query embedding model changed during retrieval.")
    return batch



def _classify_existing_index(
    index: SQLiteVectorIndex | None,
    *,
    current_corpus_snapshot: CorpusSnapshot,
    embedding_model_id: str | None,
) -> tuple[bool | None, str]:
    if index is None:
        return None, "missing"
    if index.corpus_snapshot.snapshot_id != current_corpus_snapshot.snapshot_id:
        return False, "snapshot_mismatch"
    if embedding_model_id is None:
        return None, "model_unresolved"
    if index.embedding_model_id != embedding_model_id:
        return False, "model_mismatch"
    return True, "ready"



def _open_existing_index(index_path: Path) -> SQLiteVectorIndex | None:
    if not index_path.exists():
        return None
    try:
        return open_vector_index(index_path)
    except FileNotFoundError:
        return None



def _resolve_repo_root(repo_root: str | Path | None) -> Path:
    if repo_root is None:
        return Path(__file__).resolve().parents[1]
    return Path(repo_root).resolve()



def _resolve_embedding_model_id(embedding_model_id: str | None) -> str | None:
    if embedding_model_id is not None:
        resolved = embedding_model_id.strip()
        return resolved or None
    resolved = os.getenv("OPENAI_EMBEDDING_MODEL", "").strip()
    return resolved or None



def _validate_channel(channel: Channel | str) -> Channel:
    if channel not in {"instagram", "linkedin", "email"}:
        raise RetrievalConfigurationError(f"Unknown channel: {channel!r}.")
    return channel  # type: ignore[return-value]



def _require_nonempty_string(value: str, label: str) -> str:
    if not isinstance(value, str):
        raise RetrievalConfigurationError(f"{label} must be a string.")
    stripped = value.strip()
    if not stripped:
        raise RetrievalConfigurationError(f"{label} must be a non-empty string.")
    return stripped



def _validate_positive_int(value: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise RetrievalConfigurationError(f"{label} must be a positive integer.")
    return value



def _validate_similarity_threshold(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise RetrievalConfigurationError(f"{label} must be a finite number.")
    threshold = float(value)
    if threshold < -1.0 or threshold > 1.0:
        raise RetrievalConfigurationError(f"{label} must be between -1.0 and 1.0.")
    return threshold



def _hash_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


__all__ = [
    "DEFAULT_MAX_CONTEXT_CHARACTERS",
    "DEFAULT_PRIMARY_MINIMUM_SIMILARITY",
    "DEFAULT_PRIMARY_TOP_K",
    "DEFAULT_SECONDARY_MINIMUM_SIMILARITY",
    "DEFAULT_SECONDARY_TOP_K",
    "RagRetrievalError",
    "RagRetrievalPlan",
    "RagRetrievalResult",
    "RetrievedContextBundle",
    "build_rag_retrieval_evidence_payload",
    "RetrievedContextMeasurements",
    "RetrievedContextSourceManifestEntry",
    "RetrievalBlockedError",
    "RetrievalConfigurationError",
    "RetrievalManifest",
    "RetrievalStaleCorpusError",
    "build_retrieval_query",
    "plan_rag_context_retrieval",
    "retrieve_rag_context",
    "render_rag_retrieval_plan",
    "render_rag_retrieval_result",
]
