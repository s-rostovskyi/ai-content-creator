from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal
from urllib.parse import urlsplit

from src.document_processor import (
    KnowledgeBaseDocument,
    MarkdownCorpusError,
    MalformedMarkdownDocumentError,
    load_knowledge_base_documents,
    parse_knowledge_base_document,
)

SOURCE_ROOT = Path("knowledge_base")
KNOWN_KNOWLEDGE_BASES = {"primary", "secondary"}
IGNORED_FILENAMES = {"README.md", ".gitkeep"}
PRIMARY_HOSTNAME_SUFFIX = ".patagonia.com"
PRIMARY_HOSTNAME_VALIDATION_NOTE = (
    "Hostname validation checks exact patagonia.com boundaries only; it does not "
    "prove page accessibility, factual accuracy, or authenticity."
)
MAX_SOURCE_UPLOAD_BYTES = 1_048_576


class SourceRegistryError(Exception):
    """Base error for safe source-management operations."""


class SourceValidationError(SourceRegistryError, MalformedMarkdownDocumentError):
    """Raised when a source fails schema, provenance, or content validation."""


class SourcePathError(SourceRegistryError):
    """Raised when a source identifier or target path is unsafe."""


class SourceNotFoundError(SourceRegistryError):
    """Raised when a source cannot be found."""


class SourceConflictError(SourceRegistryError):
    """Raised when a source version is stale or a collision would occur."""


class SourceWriteError(SourceRegistryError):
    """Raised when a source cannot be written or removed safely."""


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    repository_relative_path: str
    knowledge_base: Literal["primary", "secondary"]
    source_hash: str
    source_bytes: int
    document_title: str
    source_urls: tuple[str, ...]
    source_url_text: str
    publisher: str
    published_updated: str
    accessed: str
    evidence_type: str
    section_count: int


@dataclass(frozen=True)
class SourceSnapshot(SourceRecord):
    document: KnowledgeBaseDocument


@dataclass(frozen=True)
class PreparedSourceOperation:
    operation: Literal["create", "edit", "delete"]
    source_id: str
    expected_source_hash: str | None
    snapshot: SourceSnapshot

    def __post_init__(self) -> None:
        if self.source_id != self.snapshot.source_id:
            raise SourceRegistryError("Prepared source operation target does not match its snapshot.")


@dataclass(frozen=True)
class SourceChangeResult:
    operation: Literal["create", "edit", "delete"]
    source_id: str
    repository_relative_path: str
    knowledge_base: Literal["primary", "secondary"]
    previous_source_hash: str | None
    current_source_hash: str | None
    previous_source_bytes: int | None
    current_source_bytes: int | None
    changed_paths: tuple[str, ...]
    index_sync_required: bool = True
    index_sync_reason: str = "source_changed"


def list_sources(repo_root: str | Path | None = None) -> tuple[SourceRecord, ...]:
    root_path = _resolve_repo_root(repo_root)
    try:
        documents = load_knowledge_base_documents(root_path)
    except MarkdownCorpusError as exc:
        raise SourceValidationError(str(exc)) from exc

    records = [_build_source_record(root_path, document) for document in documents]
    return tuple(sorted(records, key=lambda record: record.repository_relative_path))


def read_source(source_id: str, repo_root: str | Path | None = None) -> SourceSnapshot:
    root_path = _resolve_repo_root(repo_root)
    target_path = _resolve_source_path(source_id, root_path)
    if not target_path.exists() or not target_path.is_file():
        raise SourceNotFoundError(f"Source not found: {source_id}")
    if target_path.is_symlink():
        raise SourcePathError(f"Symlinked sources are not allowed: {source_id}")

    try:
        raw_bytes = target_path.read_bytes()
    except OSError as exc:
        raise SourceValidationError(f"Cannot read source: {source_id}") from exc

    return _snapshot_from_bytes(raw_bytes, target_path, root_path)


def prepare_create_source(
    source_id: str,
    markdown_text: str,
    repo_root: str | Path | None = None,
) -> PreparedSourceOperation:
    root_path = _resolve_repo_root(repo_root)
    target_path = _resolve_source_path(source_id, root_path)
    if target_path.exists():
        raise SourceConflictError(f"Source already exists: {source_id}")

    snapshot = _snapshot_from_text(markdown_text, target_path, root_path)
    return PreparedSourceOperation(
        operation="create",
        source_id=snapshot.source_id,
        expected_source_hash=None,
        snapshot=snapshot,
    )


def prepare_edit_source(
    source_id: str,
    markdown_text: str,
    expected_source_hash: str,
    repo_root: str | Path | None = None,
) -> PreparedSourceOperation:
    root_path = _resolve_repo_root(repo_root)
    current_snapshot = read_source(source_id, root_path)
    if current_snapshot.source_hash != expected_source_hash:
        raise SourceConflictError(f"Source changed since it was previewed: {source_id}")

    snapshot = _snapshot_from_text(markdown_text, root_path / current_snapshot.repository_relative_path, root_path)
    return PreparedSourceOperation(
        operation="edit",
        source_id=snapshot.source_id,
        expected_source_hash=expected_source_hash,
        snapshot=snapshot,
    )


def prepare_delete_source(
    source_id: str,
    expected_source_hash: str,
    repo_root: str | Path | None = None,
) -> PreparedSourceOperation:
    root_path = _resolve_repo_root(repo_root)
    current_snapshot = read_source(source_id, root_path)
    if current_snapshot.source_hash != expected_source_hash:
        raise SourceConflictError(f"Source changed since it was previewed: {source_id}")

    return PreparedSourceOperation(
        operation="delete",
        source_id=current_snapshot.source_id,
        expected_source_hash=expected_source_hash,
        snapshot=current_snapshot,
    )


def apply_prepared_source_operation(
    prepared_operation: PreparedSourceOperation,
    repo_root: str | Path | None = None,
) -> SourceChangeResult:
    root_path = _resolve_repo_root(repo_root)
    target_path = _resolve_source_path(prepared_operation.source_id, root_path)
    snapshot = prepared_operation.snapshot

    if prepared_operation.operation == "create":
        return _apply_create_operation(target_path, snapshot)
    if prepared_operation.operation == "edit":
        return _apply_edit_operation(target_path, snapshot, prepared_operation.expected_source_hash, root_path)
    if prepared_operation.operation == "delete":
        return _apply_delete_operation(target_path, prepared_operation.expected_source_hash, root_path)
    raise SourceRegistryError(f"Unsupported source operation: {prepared_operation.operation}")


def _resolve_repo_root(repo_root: str | Path | None) -> Path:
    if repo_root is None:
        return Path(__file__).resolve().parents[1]
    return Path(repo_root).resolve()


def _resolve_source_path(source_id: str, repo_root: Path) -> Path:
    candidate_path = Path(source_id)
    if candidate_path.is_absolute() or candidate_path.anchor:
        raise SourcePathError(f"Source identifier must be repository-relative: {source_id}")
    if not candidate_path.parts:
        raise SourcePathError("Source identifier cannot be empty.")
    if candidate_path.parts[0] != SOURCE_ROOT.name:
        raise SourcePathError(
            f"Source identifier must begin with '{SOURCE_ROOT.as_posix()}/': {source_id}"
        )
    if len(candidate_path.parts) < 3:
        raise SourcePathError(
            f"Source identifier must include a knowledge-base directory and filename: {source_id}"
        )
    if candidate_path.parts[1] not in KNOWN_KNOWLEDGE_BASES:
        raise SourcePathError(
            f"Source identifier must point to the primary or secondary corpus: {source_id}"
        )
    if candidate_path.suffix.lower() != ".md":
        raise SourcePathError(f"Source identifier must reference a Markdown file: {source_id}")
    if candidate_path.name in IGNORED_FILENAMES:
        raise SourcePathError(f"Ignored source files cannot be managed: {source_id}")
    if any(part == ".." or part.startswith(".") for part in candidate_path.parts):
        raise SourcePathError(f"Source identifier contains a hidden or traversal path segment: {source_id}")

    resolved_target = (repo_root / candidate_path).resolve(strict=False)
    resolved_repo_root = repo_root.resolve()
    if not resolved_target.is_relative_to(resolved_repo_root):
        raise SourcePathError(f"Source identifier escapes the repository root: {source_id}")
    return repo_root / candidate_path


def _snapshot_from_bytes(raw_bytes: bytes, source_path: Path, repo_root: Path) -> SourceSnapshot:
    _validate_source_size(raw_bytes, source_path, repo_root)
    try:
        markdown_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SourceValidationError(
            f"Source is not valid UTF-8: {source_path.relative_to(repo_root)}"
        ) from exc
    return _snapshot_from_text(markdown_text, source_path, repo_root, raw_bytes=raw_bytes)


def _snapshot_from_text(
    markdown_text: str,
    source_path: Path,
    repo_root: Path,
    raw_bytes: bytes | None = None,
) -> SourceSnapshot:
    source_id = source_path.relative_to(repo_root).as_posix()
    knowledge_base = _knowledge_base_from_source_id(source_id)
    content_bytes = raw_bytes if raw_bytes is not None else _encode_markdown(markdown_text, source_id)
    _validate_source_size(content_bytes, source_path, repo_root)

    try:
        document = parse_knowledge_base_document(
            markdown_text,
            source_id,
            knowledge_base,
            repo_root,
        )
    except MalformedMarkdownDocumentError as exc:
        raise SourceValidationError(str(exc)) from exc

    _validate_primary_provenance(document)
    return SourceSnapshot(
        source_id=source_id,
        repository_relative_path=source_id,
        knowledge_base=document.knowledge_base,
        source_hash=_hash_bytes(content_bytes),
        source_bytes=len(content_bytes),
        document_title=document.metadata.document_title,
        source_urls=document.metadata.source_urls,
        source_url_text=document.metadata.source_url_text,
        publisher=document.metadata.publisher,
        published_updated=document.metadata.published_updated,
        accessed=document.metadata.accessed,
        evidence_type=document.metadata.evidence_type,
        section_count=len(document.sections),
        document=document,
    )


def _build_source_record(repo_root: Path, document: KnowledgeBaseDocument) -> SourceRecord:
    source_path = repo_root / document.repository_relative_path
    try:
        raw_bytes = source_path.read_bytes()
    except OSError as exc:
        raise SourceValidationError(f"Cannot read source: {document.repository_relative_path}") from exc

    return SourceRecord(
        source_id=document.repository_relative_path,
        repository_relative_path=document.repository_relative_path,
        knowledge_base=document.knowledge_base,
        source_hash=_hash_bytes(raw_bytes),
        source_bytes=len(raw_bytes),
        document_title=document.metadata.document_title,
        source_urls=document.metadata.source_urls,
        source_url_text=document.metadata.source_url_text,
        publisher=document.metadata.publisher,
        published_updated=document.metadata.published_updated,
        accessed=document.metadata.accessed,
        evidence_type=document.metadata.evidence_type,
        section_count=len(document.sections),
    )


def _knowledge_base_from_source_id(source_id: str) -> Literal["primary", "secondary"]:
    parts = Path(source_id).parts
    if len(parts) < 2 or parts[1] not in KNOWN_KNOWLEDGE_BASES:
        raise SourcePathError(f"Source identifier must include a knowledge-base name: {source_id}")
    return parts[1]  # type: ignore[return-value]


def _validate_primary_provenance(document: KnowledgeBaseDocument) -> None:
    if document.knowledge_base != "primary":
        return
    for source_url in document.metadata.source_urls:
        parsed = urlsplit(source_url)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        if not _is_allowed_patagonia_hostname(hostname):
            raise SourceValidationError(
                "Primary source URLs must use Patagonia hostnames; "
                f"{PRIMARY_HOSTNAME_VALIDATION_NOTE} ({document.repository_relative_path})"
            )


def _is_allowed_patagonia_hostname(hostname: str) -> bool:
    return hostname == "patagonia.com" or hostname.endswith(PRIMARY_HOSTNAME_SUFFIX)


def _hash_bytes(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


def _encode_markdown(markdown_text: str, source_id: str) -> bytes:
    try:
        return markdown_text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise SourceValidationError(f"Source is not valid UTF-8 text: {source_id}") from exc


def _validate_source_size(raw_bytes: bytes, source_path: Path, repo_root: Path) -> None:
    if len(raw_bytes) <= MAX_SOURCE_UPLOAD_BYTES:
        return
    raise SourceValidationError(
        f"Source exceeds the maximum allowed size of {MAX_SOURCE_UPLOAD_BYTES:,} bytes: {source_path.relative_to(repo_root)}"
    )


def _apply_create_operation(target_path: Path, snapshot: SourceSnapshot) -> SourceChangeResult:
    if target_path.exists():
        raise SourceConflictError(f"Source already exists: {snapshot.source_id}")

    temp_path: Path | None = None
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(snapshot.document.markdown)
    except FileExistsError as exc:
        raise SourceConflictError(f"Source already exists: {snapshot.source_id}") from exc
    except OSError as exc:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            target_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise SourceWriteError(f"Failed to create source: {snapshot.source_id}") from exc

    return SourceChangeResult(
        operation="create",
        source_id=snapshot.source_id,
        repository_relative_path=snapshot.repository_relative_path,
        knowledge_base=snapshot.knowledge_base,
        previous_source_hash=None,
        current_source_hash=snapshot.source_hash,
        previous_source_bytes=None,
        current_source_bytes=snapshot.source_bytes,
        changed_paths=(snapshot.source_id,),
        index_sync_required=True,
        index_sync_reason="source_created",
    )


def _apply_edit_operation(
    target_path: Path,
    snapshot: SourceSnapshot,
    expected_source_hash: str | None,
    repo_root: Path,
) -> SourceChangeResult:
    if expected_source_hash is None:
        raise SourceConflictError(f"Missing expected source hash for edit: {snapshot.source_id}")
    current_snapshot = read_source(snapshot.source_id, repo_root)
    if current_snapshot.source_hash != expected_source_hash:
        raise SourceConflictError(f"Source changed since it was previewed: {snapshot.source_id}")

    temp_path: Path | None = None
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            delete=False,
            dir=target_path.parent,
        ) as handle:
            handle.write(snapshot.document.markdown)
            temp_path = Path(handle.name)
        os.replace(temp_path, target_path)
    except OSError as exc:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise SourceWriteError(f"Failed to update source: {snapshot.source_id}") from exc

    return SourceChangeResult(
        operation="edit",
        source_id=snapshot.source_id,
        repository_relative_path=snapshot.repository_relative_path,
        knowledge_base=snapshot.knowledge_base,
        previous_source_hash=current_snapshot.source_hash,
        current_source_hash=snapshot.source_hash,
        previous_source_bytes=current_snapshot.source_bytes,
        current_source_bytes=snapshot.source_bytes,
        changed_paths=(snapshot.source_id,),
        index_sync_required=True,
        index_sync_reason="source_updated",
    )


def _apply_delete_operation(
    target_path: Path,
    expected_source_hash: str | None,
    repo_root: Path,
) -> SourceChangeResult:
    if expected_source_hash is None:
        raise SourceConflictError("Missing expected source hash for delete operation.")
    source_id = target_path.relative_to(repo_root).as_posix()
    current_snapshot = read_source(source_id, repo_root)
    if current_snapshot.source_hash != expected_source_hash:
        raise SourceConflictError(f"Source changed since it was previewed: {current_snapshot.source_id}")

    try:
        target_path.unlink()
    except OSError as exc:
        raise SourceWriteError(f"Failed to delete source: {current_snapshot.source_id}") from exc

    return SourceChangeResult(
        operation="delete",
        source_id=current_snapshot.source_id,
        repository_relative_path=current_snapshot.repository_relative_path,
        knowledge_base=current_snapshot.knowledge_base,
        previous_source_hash=current_snapshot.source_hash,
        current_source_hash=None,
        previous_source_bytes=current_snapshot.source_bytes,
        current_source_bytes=None,
        changed_paths=(current_snapshot.source_id,),
        index_sync_required=True,
        index_sync_reason="source_deleted",
    )


__all__ = [
    "PreparedSourceOperation",
    "SourceChangeResult",
    "SourceConflictError",
    "SourceNotFoundError",
    "SourcePathError",
    "SourceRecord",
    "MAX_SOURCE_UPLOAD_BYTES",
    "SourceRegistryError",
    "SourceSnapshot",
    "SourceValidationError",
    "SourceWriteError",
    "apply_prepared_source_operation",
    "list_sources",
    "prepare_create_source",
    "prepare_delete_source",
    "prepare_edit_source",
    "read_source",
]
