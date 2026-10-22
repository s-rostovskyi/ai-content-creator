"""Reusable content pipeline helpers for generation, revision, approval, and export."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
from typing import Callable, Literal
from uuid import uuid4

from src.knowledge_base import ContextBundle, ContextSourceManifestEntry
from src.llm_integration import GeneratedText, UsageMetrics, generate_response
from src.prompt_templates import build_prompt

Channel = Literal["instagram", "linkedin", "email"]
DraftOrigin = Literal["generation", "revision", "manual_edit"]
SUPPORTED_CHANNELS = frozenset({"instagram", "linkedin", "email"})

_SECTION_HEADING_PATTERN = re.compile(r"^### (CHANNEL COPY|REVIEWER NOTES)\s*$")


class ContentPipelineError(Exception):
    """Base error for pipeline orchestration failures."""


class DraftFormatError(ContentPipelineError):
    """Raised when model output cannot be parsed into the required sections."""


class GenerationLimitExceededError(ContentPipelineError):
    """Raised when the session has no paid attempts remaining."""


class MissingDraftError(ContentPipelineError):
    """Raised when an operation requires a current draft but none exists."""


class ApprovalError(ContentPipelineError):
    """Raised when approval or export cannot proceed safely."""


class ExportError(ContentPipelineError):
    """Raised when export cannot complete."""


@dataclass(frozen=True)
class ParsedSections:
    channel_copy: str
    reviewer_notes: str


@dataclass(frozen=True)
class ResponseMetadata:
    response_id: str
    model: str
    elapsed_seconds: float
    usage: UsageMetrics | None


@dataclass(frozen=True)
class PipelineDraft:
    revision_number: int
    origin: DraftOrigin
    channel: Channel | str
    campaign_brief: str
    raw_response: str | None
    channel_copy: str
    reviewer_notes: str
    source_manifest: tuple[ContextSourceManifestEntry, ...]
    response_metadata: ResponseMetadata | None


@dataclass(frozen=True)
class ApprovalRecord:
    approved_revision: int
    approved_copy_fingerprint: str
    approved_by: str
    approved_at: str


@dataclass(frozen=True)
class ExportRecord:
    markdown_path: Path
    json_path: Path


@dataclass
class PipelineSession:
    channel: Channel | str
    campaign_brief: str
    context_bundle: ContextBundle
    max_paid_attempts: int = 3
    paid_attempts_used: int = 0
    current_draft: PipelineDraft | None = None
    approval: ApprovalRecord | None = None
    history: list[PipelineDraft] = field(default_factory=list)

    @property
    def remaining_paid_attempts(self) -> int:
        return max(self.max_paid_attempts - self.paid_attempts_used, 0)


GenerationFunction = Callable[..., GeneratedText]


def create_pipeline_session(
    channel: Channel | str,
    campaign_brief: str,
    context_bundle: ContextBundle,
    *,
    max_paid_attempts: int = 3,
) -> PipelineSession:
    if channel not in SUPPORTED_CHANNELS:
        raise ContentPipelineError(f"Unsupported channel: {channel!r}.")
    if not isinstance(campaign_brief, str) or not campaign_brief.strip():
        raise ContentPipelineError("campaign_brief must be a non-empty string.")
    if not isinstance(context_bundle, ContextBundle):
        raise ContentPipelineError("context_bundle must be a ContextBundle.")
    if isinstance(max_paid_attempts, bool) or not isinstance(max_paid_attempts, int):
        raise ContentPipelineError("max_paid_attempts must be an integer.")
    if max_paid_attempts < 1:
        raise ContentPipelineError("max_paid_attempts must be at least 1.")
    return PipelineSession(
        channel=channel,
        campaign_brief=campaign_brief,
        context_bundle=context_bundle,
        max_paid_attempts=max_paid_attempts,
    )


def generate_initial_draft(
    session: PipelineSession,
    *,
    generation_function: GenerationFunction = generate_response,
    max_output_tokens: int = 2000,
    timeout_seconds: float = 60.0,
) -> PipelineDraft:
    if session.current_draft is not None:
        raise ContentPipelineError("A current draft already exists.")
    _consume_paid_attempt(session)
    prompt_parts = build_prompt(session.channel, session.campaign_brief, session.context_bundle)
    response = generation_function(
        instructions=prompt_parts.trusted_instructions,
        user_input=prompt_parts.user_input_text,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
    )
    parsed_sections = parse_generated_sections(response.generated_text)
    draft = _build_draft(
        session=session,
        origin="generation",
        parsed_sections=parsed_sections,
        raw_response=response.generated_text,
        response=response,
    )
    _store_current_draft(session, draft)
    return draft


def revise_current_draft(
    session: PipelineSession,
    human_feedback: str,
    *,
    generation_function: GenerationFunction = generate_response,
    max_output_tokens: int = 2000,
    timeout_seconds: float = 60.0,
) -> PipelineDraft:
    current_draft = _require_current_draft(session)
    if not isinstance(human_feedback, str) or not human_feedback.strip():
        raise ContentPipelineError("human_feedback must be a non-empty string.")

    _consume_paid_attempt(session)
    revision_feedback = _compose_revision_feedback(current_draft.channel_copy, human_feedback)
    prompt_parts = build_prompt(
        session.channel,
        session.campaign_brief,
        session.context_bundle,
        feedback=revision_feedback,
    )
    response = generation_function(
        instructions=prompt_parts.trusted_instructions,
        user_input=prompt_parts.user_input_text,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
    )
    parsed_sections = parse_generated_sections(response.generated_text)
    draft = _build_draft(
        session=session,
        origin="revision",
        parsed_sections=parsed_sections,
        raw_response=response.generated_text,
        response=response,
    )
    _store_current_draft(session, draft)
    return draft


def edit_current_draft(
    session: PipelineSession,
    revised_channel_copy: str,
    *,
    revised_reviewer_notes: str | None = None,
) -> PipelineDraft:
    current_draft = _require_current_draft(session)
    if not isinstance(revised_channel_copy, str) or not revised_channel_copy.strip():
        raise ContentPipelineError("revised_channel_copy must be a non-empty string.")

    draft = PipelineDraft(
        revision_number=current_draft.revision_number + 1,
        origin="manual_edit",
        channel=session.channel,
        campaign_brief=session.campaign_brief,
        raw_response=current_draft.raw_response,
        channel_copy=revised_channel_copy,
        reviewer_notes=current_draft.reviewer_notes if revised_reviewer_notes is None else revised_reviewer_notes,
        source_manifest=current_draft.source_manifest,
        response_metadata=current_draft.response_metadata,
    )
    _store_current_draft(session, draft)
    return draft


def approve_current_draft(
    session: PipelineSession,
    *,
    approved_copy: str,
    approved_revision: int,
    reviewer_name: str = "Human reviewer",
    approved_at: str | None = None,
) -> ApprovalRecord:
    current_draft = _require_current_draft(session)
    if current_draft.channel_copy != approved_copy:
        raise ApprovalError("Approval must match the exact current channel copy.")
    if current_draft.revision_number != approved_revision:
        raise ApprovalError("Approval must target the exact current revision number.")
    if not isinstance(reviewer_name, str) or not reviewer_name.strip():
        raise ApprovalError("reviewer_name must be a non-empty string.")

    approval = ApprovalRecord(
        approved_revision=current_draft.revision_number,
        approved_copy_fingerprint=_fingerprint(current_draft.channel_copy),
        approved_by=reviewer_name.strip(),
        approved_at=_normalize_timestamp(approved_at),
    )
    session.approval = approval
    return approval


def export_approved_current_draft(
    session: PipelineSession,
    *,
    output_directory: str | Path | None = None,
) -> ExportRecord:
    current_draft = _require_current_draft(session)
    try:
        approval = _require_approval(session)
    except ApprovalError as exc:
        raise ExportError("The current draft must be approved before export.") from exc
    if approval.approved_revision != current_draft.revision_number:
        raise ExportError("Approved revision does not match the current draft.")
    if approval.approved_copy_fingerprint != _fingerprint(current_draft.channel_copy):
        raise ExportError("Approved copy does not match the current draft.")

    target_directory = (
        Path(output_directory)
        if output_directory is not None
        else Path(__file__).resolve().parents[1] / "outputs"
    )

    try:
        target_directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ExportError("Could not prepare export directory.") from exc
    export_stem = _build_export_stem(current_draft)
    markdown_path, json_path = _reserve_export_paths(target_directory, export_stem)
    created_paths: list[Path] = []

    try:
        _write_text_exclusive(markdown_path, current_draft.channel_copy + "\n")
        created_paths.append(markdown_path)
        _write_text_exclusive(
            json_path,
            json.dumps(_build_export_sidecar(session, approval), indent=2, ensure_ascii=False) + "\n",
        )
        created_paths.append(json_path)
    except ExportError:
        _cleanup_created_export_files(created_paths)
        raise
    except OSError as exc:
        _cleanup_created_export_files(created_paths)
        raise ExportError("Could not export approved draft.") from exc

    return ExportRecord(markdown_path=markdown_path, json_path=json_path)


def parse_generated_sections(raw_response: str) -> ParsedSections:
    if not isinstance(raw_response, str) or not raw_response.strip():
        raise DraftFormatError("Model output must be a non-empty string.")

    lines = raw_response.splitlines()
    start_index = 0
    end_index = len(lines)
    while start_index < end_index and not lines[start_index].strip():
        start_index += 1
    while end_index > start_index and not lines[end_index - 1].strip():
        end_index -= 1

    trimmed_lines = lines[start_index:end_index]
    if not trimmed_lines:
        raise DraftFormatError("Model output must contain both required sections.")

    heading_positions: list[tuple[int, str]] = []
    for index, line in enumerate(trimmed_lines):
        match = _SECTION_HEADING_PATTERN.match(line.strip())
        if match is not None:
            heading_positions.append((index, match.group(1)))

    if len(heading_positions) != 2:
        raise DraftFormatError(
            "Model output must contain exactly one CHANNEL COPY section and one REVIEWER NOTES section."
        )
    if heading_positions[0] != (0, "CHANNEL COPY") or heading_positions[1][1] != "REVIEWER NOTES":
        raise DraftFormatError("Model output must start with CHANNEL COPY and then REVIEWER NOTES.")

    copy_lines = trimmed_lines[heading_positions[0][0] + 1 : heading_positions[1][0]]
    notes_lines = trimmed_lines[heading_positions[1][0] + 1 :]
    channel_copy = "\n".join(copy_lines).strip()
    reviewer_notes = "\n".join(notes_lines).strip()
    if not channel_copy:
        raise DraftFormatError("CHANNEL COPY section cannot be empty.")
    if not reviewer_notes:
        raise DraftFormatError("REVIEWER NOTES section cannot be empty.")

    return ParsedSections(channel_copy=channel_copy, reviewer_notes=reviewer_notes)


def _consume_paid_attempt(session: PipelineSession) -> None:
    if session.remaining_paid_attempts <= 0:
        raise GenerationLimitExceededError(
            f"Paid attempt limit reached: {session.max_paid_attempts} attempts per session."
        )
    session.paid_attempts_used += 1


def _build_draft(
    *,
    session: PipelineSession,
    origin: DraftOrigin,
    parsed_sections: ParsedSections,
    raw_response: str,
    response: GeneratedText,
) -> PipelineDraft:
    response_metadata = ResponseMetadata(
        response_id=response.response_id,
        model=response.model,
        elapsed_seconds=response.elapsed_seconds,
        usage=response.usage,
    )
    revision_number = 1 if session.current_draft is None else session.current_draft.revision_number + 1
    return PipelineDraft(
        revision_number=revision_number,
        origin=origin,
        channel=session.channel,
        campaign_brief=session.campaign_brief,
        raw_response=raw_response,
        channel_copy=parsed_sections.channel_copy,
        reviewer_notes=parsed_sections.reviewer_notes,
        source_manifest=session.context_bundle.source_manifest,
        response_metadata=response_metadata,
    )


def _store_current_draft(session: PipelineSession, draft: PipelineDraft) -> None:
    session.current_draft = draft
    session.approval = None
    session.history.append(draft)


def _compose_revision_feedback(current_copy: str, human_feedback: str) -> str:
    return "\n\n".join(
        (
            "## Current channel copy",
            current_copy.strip(),
            "## Human feedback",
            human_feedback.strip(),
        )
    )


def _require_current_draft(session: PipelineSession) -> PipelineDraft:
    if session.current_draft is None:
        raise MissingDraftError("A current draft is required for this action.")
    return session.current_draft


def _require_approval(session: PipelineSession) -> ApprovalRecord:
    if session.approval is None:
        raise ApprovalError("The current draft must be approved before export.")
    return session.approval


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_timestamp(approved_at: str | None) -> str:
    if approved_at is None:
        return datetime.now(timezone.utc).isoformat()
    return approved_at


def _build_export_stem(draft: PipelineDraft) -> str:
    timestamp_part = _export_timestamp_token()
    unique_part = uuid4().hex[:8]
    return f"{draft.channel}-rev{draft.revision_number}-{timestamp_part}-{unique_part}"


def _export_timestamp_token() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _reserve_export_paths(directory: Path, stem: str) -> tuple[Path, Path]:
    markdown_path = directory / f"{stem}.md"
    json_path = directory / f"{stem}.json"
    return markdown_path, json_path


def _write_text_exclusive(path: Path, text: str) -> None:
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(text)
    except FileExistsError as exc:
        raise ExportError(f"Export file already exists: {path}") from exc
    except OSError as exc:
        raise ExportError(f"Could not write export file: {path}") from exc


def _cleanup_created_export_files(created_paths: list[Path]) -> None:
    for path in reversed(created_paths):
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        except OSError:
            continue


def _build_export_sidecar(session: PipelineSession, approval: ApprovalRecord) -> dict[str, object]:
    draft = _require_current_draft(session)
    return {
        "channel": draft.channel,
        "campaign_brief": draft.campaign_brief,
        "revision_number": draft.revision_number,
        "origin": draft.origin,
        "raw_response": draft.raw_response,
        "channel_copy": draft.channel_copy,
        "reviewer_notes": draft.reviewer_notes,
        "source_manifest": [asdict(entry) for entry in draft.source_manifest],
        "response_metadata": asdict(draft.response_metadata) if draft.response_metadata is not None else None,
        "approval": asdict(approval),
    }


__all__ = [
    "ApprovalError",
    "ApprovalRecord",
    "Channel",
    "ContentPipelineError",
    "DraftFormatError",
    "ExportError",
    "ExportRecord",
    "GenerationLimitExceededError",
    "MissingDraftError",
    "ParsedSections",
    "PipelineDraft",
    "PipelineSession",
    "ResponseMetadata",
    "approve_current_draft",
    "create_pipeline_session",
    "edit_current_draft",
    "export_approved_current_draft",
    "generate_initial_draft",
    "parse_generated_sections",
    "revise_current_draft",
]
