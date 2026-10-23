from __future__ import annotations

"""Deterministic chunking for validated knowledge-base documents.

Chunk size is measured in characters, not tokens. The policy uses zero overlap.
Oversized sections are split at paragraph boundaries first, then sentence
boundaries, and finally by a bounded fixed-length fallback when a single
sentence is still too long.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Iterable, Literal

from src.document_processor import KnowledgeBaseDocument, KnowledgeBaseSection

ChunkKind = Literal["facts", "editorial", "limitations"]
SectionKind = ChunkKind

DEFAULT_MAX_CHUNK_CHARACTERS = 1200
DEFAULT_CHUNK_OVERLAP_CHARACTERS = 0
DEFAULT_CHUNKING_VERSION = "rag-chunking-v1"


class RagChunkingError(Exception):
    """Raised when documents cannot be chunked deterministically."""


@dataclass(frozen=True)
class ChunkingPolicy:
    max_chunk_characters: int = DEFAULT_MAX_CHUNK_CHARACTERS
    overlap_characters: int = DEFAULT_CHUNK_OVERLAP_CHARACTERS

    def __post_init__(self) -> None:
        if self.max_chunk_characters <= 0:
            raise RagChunkingError("Chunk size must be a positive number of characters.")
        if self.overlap_characters != DEFAULT_CHUNK_OVERLAP_CHARACTERS:
            raise RagChunkingError("Chunk overlap is fixed at 0 characters for this phase.")


@dataclass(frozen=True)
class RagChunk:
    chunk_id: str
    chunk_hash: str
    document_hash: str
    source_id: str
    repository_relative_path: str
    knowledge_base: Literal["primary", "secondary"]
    document_title: str
    section_id: str
    section_heading_path: tuple[str, ...]
    section_heading_text: str
    section_kind: SectionKind
    chunk_kind: ChunkKind
    chunk_index: int
    chunk_text: str
    applicable_limitations: str
    source_urls: tuple[str, ...]
    source_url_text: str
    publisher: str
    published_updated: str
    accessed: str
    evidence_type: str
    section_line_range: tuple[int, int]
    chunk_line_range: tuple[int, int]


@dataclass(frozen=True)
class _TextUnit:
    text: str
    start_line: int
    end_line: int
    separator_before: str


def build_rag_chunks(
    documents: Iterable[KnowledgeBaseDocument],
    *,
    policy: ChunkingPolicy = ChunkingPolicy(),
) -> tuple[RagChunk, ...]:
    ordered_documents = sorted(documents, key=lambda document: document.repository_relative_path)
    chunks: list[RagChunk] = []
    for document in ordered_documents:
        chunks.extend(_chunk_document(document, policy))
    return tuple(chunks)


def _chunk_document(document: KnowledgeBaseDocument, policy: ChunkingPolicy) -> tuple[RagChunk, ...]:
    document_hash = _hash_text(document.markdown)
    limitation_text = _collect_document_limitations(document)
    chunks: list[RagChunk] = []

    for section in document.sections:
        section_kind = _classify_section_kind(section.heading_path)
        section_body = _section_body_text(section)
        body_start_line = section.line_range[0] + 1
        paragraph_units = list(_paragraph_units(section_body, body_start_line))
        if not paragraph_units:
            continue

        chunk_units = _pack_units(_expand_units(paragraph_units, policy.max_chunk_characters), policy.max_chunk_characters)
        for chunk_index, chunk_unit in enumerate(chunk_units, start=1):
            chunk_hash = _hash_text(
                json.dumps(
                    {
                        "applicable_limitations": limitation_text,
                        "chunk_index": chunk_index,
                        "chunk_kind": section_kind,
                        "chunk_text": chunk_unit.text,
                        "document_hash": document_hash,
                        "section_id": section.section_id,
                        "section_heading_path": section.heading_path,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            chunks.append(
                RagChunk(
                    chunk_id=f"{section.section_id}::{section_kind}::{chunk_index:03d}::{chunk_hash[:16]}",
                    chunk_hash=chunk_hash,
                    document_hash=document_hash,
                    source_id=document.repository_relative_path,
                    repository_relative_path=document.repository_relative_path,
                    knowledge_base=document.knowledge_base,
                    document_title=document.metadata.document_title,
                    section_id=section.section_id,
                    section_heading_path=section.heading_path,
                    section_heading_text=section.heading_text,
                    section_kind=section_kind,
                    chunk_kind=section_kind,
                    chunk_index=chunk_index,
                    chunk_text=chunk_unit.text,
                    applicable_limitations=limitation_text,
                    source_urls=document.metadata.source_urls,
                    source_url_text=document.metadata.source_url_text,
                    publisher=document.metadata.publisher,
                    published_updated=document.metadata.published_updated,
                    accessed=document.metadata.accessed,
                    evidence_type=document.metadata.evidence_type,
                    section_line_range=section.line_range,
                    chunk_line_range=(chunk_unit.start_line, chunk_unit.end_line),
                )
            )

    return tuple(chunks)


def _collect_document_limitations(document: KnowledgeBaseDocument) -> str:
    limitation_sections = [
        section
        for section in document.sections
        if _classify_section_kind(section.heading_path) == "limitations"
    ]
    if not limitation_sections:
        return ""
    bodies = [body for body in (_section_body_text(section) for section in limitation_sections) if body.strip()]
    return "\n\n".join(bodies)


def _classify_section_kind(heading_path: tuple[str, ...]) -> SectionKind:
    heading_text = " / ".join(heading_path).lower()
    if "limit" in heading_text:
        return "limitations"
    if "content implication" in heading_text or "interpretation" in heading_text or "editorial" in heading_text:
        return "editorial"
    return "facts"


def _section_body_text(section: KnowledgeBaseSection) -> str:
    lines = section.markdown.splitlines(keepends=True)
    body_lines = lines[1:]
    return "".join(body_lines).strip()


def _paragraph_units(text: str, start_line: int) -> Iterable[_TextUnit]:
    lines = text.splitlines(keepends=True)
    paragraph_start: int | None = None
    paragraph_lines: list[str] = []
    line_number = start_line
    for offset, line in enumerate(lines):
        current_line_number = start_line + offset
        if line.strip():
            if paragraph_start is None:
                paragraph_start = current_line_number
            paragraph_lines.append(line)
            continue
        if paragraph_start is not None:
            yield _TextUnit(
                text="".join(paragraph_lines).strip(),
                start_line=paragraph_start,
                end_line=current_line_number,
                separator_before="\n\n",
            )
            paragraph_start = None
            paragraph_lines = []
        line_number = current_line_number + 1
    if paragraph_start is not None:
        yield _TextUnit(
            text="".join(paragraph_lines).strip(),
            start_line=paragraph_start,
            end_line=start_line + len(lines),
            separator_before="\n\n",
        )


def _expand_units(units: Iterable[_TextUnit], max_chunk_characters: int) -> Iterable[_TextUnit]:
    for unit in units:
        if len(unit.text) <= max_chunk_characters:
            yield unit
            continue
        yield from _split_large_unit(unit, max_chunk_characters)


def _split_large_unit(unit: _TextUnit, max_chunk_characters: int) -> Iterable[_TextUnit]:
    sentence_texts = _split_into_sentences(unit.text)
    if len(sentence_texts) <= 1:
        yield from _slice_text(unit, max_chunk_characters)
        return

    for sentence_index, sentence_text in enumerate(sentence_texts):
        sentence_unit = _TextUnit(
            text=sentence_text,
            start_line=unit.start_line,
            end_line=unit.end_line,
            separator_before=unit.separator_before if sentence_index == 0 else " ",
        )
        if len(sentence_text) <= max_chunk_characters:
            yield sentence_unit
        else:
            yield from _slice_text(sentence_unit, max_chunk_characters)


def _slice_text(unit: _TextUnit, max_chunk_characters: int) -> Iterable[_TextUnit]:
    text = unit.text
    start_index = 0
    slice_index = 0
    while start_index < len(text):
        end_index = start_index + max_chunk_characters
        yield _TextUnit(
            text=text[start_index:end_index],
            start_line=unit.start_line,
            end_line=unit.end_line,
            separator_before=unit.separator_before if slice_index == 0 else "",
        )
        start_index = end_index
        slice_index += 1


def _split_into_sentences(text: str) -> list[str]:
    stripped_text = text.strip()
    if not stripped_text:
        return []
    pieces = re.split(r"(?<=[.!?])\s+", stripped_text)
    return [piece.strip() for piece in pieces if piece.strip()]


def _pack_units(units: Iterable[_TextUnit], max_chunk_characters: int) -> tuple[_TextUnit, ...]:
    packed_units: list[_TextUnit] = []
    current_units: list[_TextUnit] = []
    current_length = 0
    current_start_line: int | None = None
    current_end_line: int | None = None

    def flush() -> None:
        nonlocal current_units, current_length, current_start_line, current_end_line
        if not current_units:
            return
        text_parts: list[str] = []
        for index, chunk_unit in enumerate(current_units):
            if index == 0:
                text_parts.append(chunk_unit.text)
                continue
            text_parts.append(chunk_unit.separator_before + chunk_unit.text)
        packed_units.append(
            _TextUnit(
                text="".join(text_parts),
                start_line=current_start_line if current_start_line is not None else 0,
                end_line=current_end_line if current_end_line is not None else 0,
                separator_before="",
            )
        )
        current_units = []
        current_length = 0
        current_start_line = None
        current_end_line = None

    for unit in units:
        candidate_length = len(unit.text)
        if current_units:
            candidate_length += len(unit.separator_before)
        if current_units and current_length + candidate_length > max_chunk_characters:
            flush()
        if not current_units:
            current_start_line = unit.start_line
        current_units.append(unit)
        current_length += len(unit.text)
        if len(current_units) > 1:
            current_length += len(unit.separator_before)
        current_end_line = unit.end_line

    flush()
    return tuple(packed_units)


def _hash_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


__all__ = [
    "ChunkKind",
    "ChunkingPolicy",
    "DEFAULT_CHUNK_OVERLAP_CHARACTERS",
    "DEFAULT_CHUNKING_VERSION",
    "DEFAULT_MAX_CHUNK_CHARACTERS",
    "RagChunk",
    "RagChunkingError",
    "SectionKind",
    "build_rag_chunks",
]
