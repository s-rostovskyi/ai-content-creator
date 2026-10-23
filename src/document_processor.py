from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
from typing import Iterable
from urllib.parse import urlsplit

from markdown_it import MarkdownIt
from markdown_it.token import Token

PARSER = MarkdownIt("commonmark")

KNOWLEDGE_BASE_DIRECTORIES = (
    ("primary", "knowledge_base/primary"),
    ("secondary", "knowledge_base/secondary"),
)
IGNORED_FILENAMES = {"README.md", ".gitkeep"}
REQUIRED_METADATA_KEYS = {
    "source url",
    "publisher",
    "published/updated",
    "accessed",
    "knowledge base",
    "evidence type",
}
URL_PATTERN = re.compile(r"https?://[^\s;]+")


class MarkdownCorpusError(Exception):
    """Base error for Markdown knowledge-base loading failures."""


class MissingKnowledgeBaseDirectoryError(MarkdownCorpusError):
    """Raised when an expected knowledge-base directory is absent."""


class MalformedMarkdownDocumentError(MarkdownCorpusError):
    """Raised when a document does not match the required KB schema."""


@dataclass(frozen=True)
class KnowledgeBaseMetadata:
    document_title: str
    source_urls: tuple[str, ...]
    source_url_text: str
    publisher: str
    published_updated: str
    accessed: str
    knowledge_base: str
    evidence_type: str


@dataclass(frozen=True)
class KnowledgeBaseSection:
    section_id: str
    repository_relative_path: str
    knowledge_base: str
    document_metadata: KnowledgeBaseMetadata
    heading_path: tuple[str, ...]
    heading_level: int
    heading_text: str
    markdown: str
    line_range: tuple[int, int]  # Zero-based, end-exclusive.


@dataclass(frozen=True)
class KnowledgeBaseDocument:
    repository_relative_path: str
    knowledge_base: str
    metadata: KnowledgeBaseMetadata
    sections: tuple[KnowledgeBaseSection, ...]
    markdown: str


@dataclass(frozen=True)
class _HeadingNode:
    level: int
    text: str
    start_line: int
    end_line: int


def load_knowledge_base_documents(repo_root: str | Path | None = None) -> tuple[KnowledgeBaseDocument, ...]:
    root_path = _resolve_repo_root(repo_root)
    documents: list[KnowledgeBaseDocument] = []

    for knowledge_base_name, relative_directory in KNOWLEDGE_BASE_DIRECTORIES:
        directory_path = root_path / relative_directory
        if not directory_path.exists():
            raise MissingKnowledgeBaseDirectoryError(
                f"Missing knowledge-base directory: {directory_path}"
            )
        if not directory_path.is_dir():
            raise MissingKnowledgeBaseDirectoryError(
                f"Knowledge-base path is not a directory: {directory_path}"
            )

        markdown_files = _collect_markdown_files(directory_path, root_path)
        for markdown_path in markdown_files:
            documents.append(
                _parse_markdown_document(markdown_path, root_path, knowledge_base_name)
            )

    return tuple(documents)



def parse_knowledge_base_document(
    markdown_text: str,
    source_path: str | Path,
    knowledge_base_name: str,
    repo_root: str | Path | None = None,
) -> KnowledgeBaseDocument:
    root_path = _resolve_repo_root(repo_root)
    candidate_path = _resolve_repository_relative_path(source_path, root_path)
    return _parse_markdown_document_from_text(markdown_text, candidate_path, root_path, knowledge_base_name)


def _resolve_repo_root(repo_root: str | Path | None) -> Path:
    if repo_root is None:
        return Path(__file__).resolve().parents[1]
    return Path(repo_root).resolve()


def _resolve_repository_relative_path(source_path: str | Path, repo_root: Path) -> Path:
    candidate_path = Path(source_path)
    if candidate_path.is_absolute():
        resolved_candidate = candidate_path.resolve()
    else:
        resolved_candidate = (repo_root / candidate_path).resolve()
    if not resolved_candidate.is_relative_to(repo_root):
        raise MalformedMarkdownDocumentError(
            f"Document path must stay inside the repository root: {candidate_path}"
        )
    return resolved_candidate


def _collect_markdown_files(directory_path: Path, repo_root: Path) -> list[Path]:
    files: list[Path] = []
    resolved_directory = directory_path.resolve()
    resolved_repo_root = repo_root.resolve()
    for path in directory_path.rglob("*.md"):
        if not _is_safe_corpus_path(path, resolved_directory, resolved_repo_root):
            continue
        relative_parts = path.relative_to(repo_root).parts
        if path.name in IGNORED_FILENAMES:
            continue
        if any(part.startswith(".") for part in relative_parts):
            continue
        if path.is_symlink():
            continue
        files.append(path)
    return sorted(files, key=lambda candidate: candidate.relative_to(repo_root).as_posix())


def _parse_markdown_document(
    source_path: Path,
    repo_root: Path,
    knowledge_base_name: str,
) -> KnowledgeBaseDocument:
    try:
        markdown = source_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise MalformedMarkdownDocumentError(
            f"Document is not valid UTF-8: {source_path}"
        ) from exc
    except OSError as exc:
        raise MarkdownCorpusError(f"Cannot read document: {source_path}") from exc

    return _parse_markdown_document_from_text(markdown, source_path, repo_root, knowledge_base_name)


def _parse_markdown_document_from_text(
    markdown: str,
    source_path: Path,
    repo_root: Path,
    knowledge_base_name: str,
) -> KnowledgeBaseDocument:
    try:
        tokens = PARSER.parse(markdown)
    except Exception as exc:  # pragma: no cover - defensive around parser internals
        raise MalformedMarkdownDocumentError(f"Cannot parse Markdown document: {source_path}") from exc

    heading_nodes = _extract_heading_nodes(tokens)
    if not heading_nodes:
        raise MalformedMarkdownDocumentError(
            f"Document is missing a required title heading: {source_path}"
        )
    if heading_nodes[0].level != 1:
        raise MalformedMarkdownDocumentError(
            f"Document title must be an H1 heading: {source_path}"
        )

    lines = markdown.splitlines(keepends=True)
    title_node = heading_nodes[0]
    metadata_lines = lines[title_node.end_line : heading_nodes[1].start_line if len(heading_nodes) > 1 else len(lines)]
    metadata = _parse_document_metadata(metadata_lines, source_path, knowledge_base_name, title_node.text)
    if metadata.knowledge_base != knowledge_base_name:
        raise MalformedMarkdownDocumentError(
            f"Knowledge base metadata must match the containing directory: {source_path}"
        )

    section_nodes = [node for node in heading_nodes[1:] if node.level >= 2]
    if not section_nodes:
        raise MalformedMarkdownDocumentError(
            f"Document must contain at least one content section: {source_path}"
        )

    sections = _build_sections(section_nodes, lines, source_path, repo_root, metadata.document_title, metadata)
    return KnowledgeBaseDocument(
        repository_relative_path=source_path.relative_to(repo_root).as_posix(),
        knowledge_base=knowledge_base_name,
        metadata=metadata,
        sections=tuple(sections),
        markdown=markdown,
    )


def _extract_heading_nodes(tokens: list[Token]) -> list[_HeadingNode]:
    heading_nodes: list[_HeadingNode] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.type == "heading_open":
            if token.map is None:
                raise MalformedMarkdownDocumentError("Heading token is missing source mapping")
            if index + 1 >= len(tokens) or tokens[index + 1].type != "inline":
                raise MalformedMarkdownDocumentError("Heading token is missing inline content")
            level = _heading_level(token)
            text = tokens[index + 1].content.strip()
            heading_nodes.append(
                _HeadingNode(
                    level=level,
                    text=text,
                    start_line=token.map[0],
                    end_line=token.map[1],
                )
            )
        index += 1
    return heading_nodes


def _heading_level(token: Token) -> int:
    if not token.tag.startswith("h"):
        raise MalformedMarkdownDocumentError(f"Unexpected heading token tag: {token.tag}")
    try:
        return int(token.tag[1:])
    except ValueError as exc:  # pragma: no cover - defensive
        raise MalformedMarkdownDocumentError(f"Invalid heading level: {token.tag}") from exc


def _parse_document_metadata(
    metadata_lines: Iterable[str],
    source_path: Path,
    knowledge_base_name: str,
    document_title: str,
) -> KnowledgeBaseMetadata:
    extracted_fields: dict[str, str] = {}
    for line in metadata_lines:
        stripped_line = line.strip()
        if not stripped_line:
            continue
        if not stripped_line.startswith("- "):
            raise MalformedMarkdownDocumentError(
                f"Metadata must be written as bullet lines before the first section: {source_path}"
            )
        match = re.fullmatch(r"- (?P<key>[^:]+): (?P<value>.*)", stripped_line)
        if match is None:
            raise MalformedMarkdownDocumentError(
                f"Invalid metadata line in document: {source_path}"
            )
        key = match.group("key").strip().lower()
        value = match.group("value").strip()
        if key in extracted_fields:
            raise MalformedMarkdownDocumentError(
                f"Duplicate metadata field '{key}' in document: {source_path}"
            )
        if key in REQUIRED_METADATA_KEYS and not value:
            raise MalformedMarkdownDocumentError(
                f"Metadata field '{key}' cannot be blank in document: {source_path}"
            )
        extracted_fields[key] = value

    missing_keys = sorted(REQUIRED_METADATA_KEYS - extracted_fields.keys())
    if missing_keys:
        raise MalformedMarkdownDocumentError(
            f"Missing metadata field(s) {', '.join(missing_keys)} in document: {source_path}"
        )

    source_urls = _extract_urls(extracted_fields["source url"])
    if not source_urls:
        raise MalformedMarkdownDocumentError(
            f"Source URL metadata must contain at least one syntactically valid URL: {source_path}"
        )

    knowledge_base_value = extracted_fields["knowledge base"].strip().lower()
    if knowledge_base_value not in {"primary", "secondary"}:
        raise MalformedMarkdownDocumentError(
            f"Knowledge base metadata must be primary or secondary: {source_path}"
        )

    _validate_accessed_date(extracted_fields["accessed"], source_path)

    return KnowledgeBaseMetadata(
        document_title=document_title,
        source_urls=tuple(source_urls),
        source_url_text=extracted_fields["source url"],
        publisher=extracted_fields["publisher"],
        published_updated=extracted_fields["published/updated"],
        accessed=extracted_fields["accessed"],
        knowledge_base=knowledge_base_value,
        evidence_type=extracted_fields["evidence type"],
    )


def _extract_urls(value: str) -> list[str]:
    urls: list[str] = []
    for match in URL_PATTERN.findall(value):
        cleaned = match.rstrip(").,;]")
        parsed = urlsplit(cleaned)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        if cleaned not in urls:
            urls.append(cleaned)
    return urls


def _validate_accessed_date(value: str, source_path: Path) -> None:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise MalformedMarkdownDocumentError(
            f"Accessed date must use YYYY-MM-DD format: {source_path}"
        ) from exc


def _is_safe_corpus_path(path: Path, resolved_directory: Path, resolved_repo_root: Path) -> bool:
    try:
        resolved_path = path.resolve(strict=True)
    except OSError:
        return False
    if path.is_symlink():
        return False
    if not resolved_path.is_relative_to(resolved_directory):
        return False
    if not resolved_path.is_relative_to(resolved_repo_root):
        return False
    return True


def _build_sections(
    section_nodes: list[_HeadingNode],
    lines: list[str],
    source_path: Path,
    repo_root: Path,
    document_title: str,
    metadata: KnowledgeBaseMetadata,
) -> list[KnowledgeBaseSection]:
    sections: list[KnowledgeBaseSection] = []
    heading_stack: list[_HeadingNode] = [_HeadingNode(level=1, text=document_title, start_line=0, end_line=0)]

    for index, current_node in enumerate(section_nodes):
        while heading_stack and heading_stack[-1].level >= current_node.level:
            heading_stack.pop()
        heading_stack.append(current_node)

        next_start_line = section_nodes[index + 1].start_line if index + 1 < len(section_nodes) else len(lines)
        section_markdown = "".join(lines[current_node.start_line:next_start_line])
        heading_path = tuple(node.text for node in heading_stack)
        relative_path = source_path.relative_to(repo_root).as_posix()
        section_identifier = f"{relative_path}::{index + 1:03d}::{_slugify_heading_path(heading_path)}"

        sections.append(
            KnowledgeBaseSection(
                section_id=section_identifier,
                repository_relative_path=relative_path,
                knowledge_base=metadata.knowledge_base,
                document_metadata=metadata,
                heading_path=heading_path,
                heading_level=current_node.level,
                heading_text=current_node.text,
                markdown=section_markdown,
                line_range=(current_node.start_line, next_start_line),
            )
        )

    return sections


def _slugify_heading_path(heading_path: tuple[str, ...]) -> str:
    slug = "/".join(heading_path).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "section"


__all__ = [
    "KnowledgeBaseDocument",
    "KnowledgeBaseSection",
    "KnowledgeBaseMetadata",
    "MalformedMarkdownDocumentError",
    "MarkdownCorpusError",
    "MissingKnowledgeBaseDirectoryError",
    "load_knowledge_base_documents",
    "parse_knowledge_base_document",
]
