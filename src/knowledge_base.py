from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.document_processor import (
    KnowledgeBaseDocument,
    MarkdownCorpusError,
    load_knowledge_base_documents,
)

PRIMARY_LABEL = "Patagonia evidence"
SECONDARY_LABEL = "Industry/competitor evidence"
DEFAULT_MAX_SERIALIZED_CHARACTERS = 40000


class KnowledgeBaseContextError(MarkdownCorpusError):
    """Raised when deterministic context assembly cannot complete."""


class EmptyKnowledgeBaseError(KnowledgeBaseContextError):
    """Raised when the primary or secondary corpus is empty."""


class ContextSizeLimitExceededError(KnowledgeBaseContextError):
    """Raised when the serialized context exceeds the configured limit."""


@dataclass(frozen=True)
class ContextSourceManifestEntry:
    repository_relative_path: str
    knowledge_base: Literal["primary", "secondary"]
    document_title: str
    source_urls: tuple[str, ...]
    source_url_text: str
    publisher: str
    published_updated: str
    accessed: str
    evidence_type: str
    section_count: int


@dataclass(frozen=True)
class CorpusMeasurements:
    primary_document_count: int
    secondary_document_count: int
    total_document_count: int
    utf8_corpus_bytes: int
    primary_context_characters: int
    secondary_context_characters: int
    serialized_context_characters: int
    max_serialized_characters: int


@dataclass(frozen=True)
class ContextBundle:
    primary_context: str
    secondary_context: str
    source_manifest: tuple[ContextSourceManifestEntry, ...]
    corpus_measurements: CorpusMeasurements


def assemble_context_bundle(
    repo_root: str | Path | None = None,
    max_serialized_characters: int = DEFAULT_MAX_SERIALIZED_CHARACTERS,
) -> ContextBundle:
    root_path = _resolve_repo_root(repo_root)
    documents = load_knowledge_base_documents(root_path)
    primary_documents, secondary_documents = _split_documents(documents)

    if not primary_documents:
        raise EmptyKnowledgeBaseError("Primary knowledge base is empty.")
    if not secondary_documents:
        raise EmptyKnowledgeBaseError("Secondary knowledge base is empty.")

    source_manifest = tuple(
        _build_manifest_entry(document) for document in documents
    )
    primary_context = _serialize_context_group(PRIMARY_LABEL, primary_documents)
    secondary_context = _serialize_context_group(SECONDARY_LABEL, secondary_documents)
    serialized_context_characters = len(primary_context) + len(secondary_context)

    if serialized_context_characters > max_serialized_characters:
        raise ContextSizeLimitExceededError(
            f"Serialized context is {serialized_context_characters} characters, exceeding the limit of {max_serialized_characters}."
        )

    corpus_measurements = CorpusMeasurements(
        primary_document_count=len(primary_documents),
        secondary_document_count=len(secondary_documents),
        total_document_count=len(documents),
        utf8_corpus_bytes=_count_utf8_corpus_bytes(root_path, documents),
        primary_context_characters=len(primary_context),
        secondary_context_characters=len(secondary_context),
        serialized_context_characters=serialized_context_characters,
        max_serialized_characters=max_serialized_characters,
    )

    return ContextBundle(
        primary_context=primary_context,
        secondary_context=secondary_context,
        source_manifest=source_manifest,
        corpus_measurements=corpus_measurements,
    )


def _resolve_repo_root(repo_root: str | Path | None) -> Path:
    if repo_root is None:
        return Path(__file__).resolve().parents[1]
    return Path(repo_root).resolve()


def _split_documents(
    documents: tuple[KnowledgeBaseDocument, ...],
) -> tuple[tuple[KnowledgeBaseDocument, ...], tuple[KnowledgeBaseDocument, ...]]:
    primary_documents = tuple(document for document in documents if document.knowledge_base == "primary")
    secondary_documents = tuple(document for document in documents if document.knowledge_base == "secondary")
    return primary_documents, secondary_documents


def _serialize_context_group(label: str, documents: tuple[KnowledgeBaseDocument, ...]) -> str:
    parts = [f"# {label}"]
    for document in documents:
        parts.append(f"## Source: {document.repository_relative_path}")
        parts.append(document.markdown.rstrip())
    return "\n\n".join(parts) + "\n"


def _build_manifest_entry(document: KnowledgeBaseDocument) -> ContextSourceManifestEntry:
    return ContextSourceManifestEntry(
        repository_relative_path=document.repository_relative_path,
        knowledge_base=document.knowledge_base,
        document_title=document.metadata.document_title,
        source_urls=document.metadata.source_urls,
        source_url_text=document.metadata.source_url_text,
        publisher=document.metadata.publisher,
        published_updated=document.metadata.published_updated,
        accessed=document.metadata.accessed,
        evidence_type=document.metadata.evidence_type,
        section_count=len(document.sections),
    )


def _count_utf8_corpus_bytes(repo_root: Path, documents: tuple[KnowledgeBaseDocument, ...]) -> int:
    return sum((repo_root / document.repository_relative_path).stat().st_size for document in documents)

