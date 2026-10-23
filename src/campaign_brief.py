from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Literal

from src.document_processor import KnowledgeBaseDocument, KnowledgeBaseSection, load_knowledge_base_documents

PRIMARY_LABEL = "Patagonia sources"
SECONDARY_LABEL = "Historical industry evidence"
DEFAULT_BRIEF_ANGLE = "packability"


@dataclass(frozen=True)
class BriefSectionPreview:
    heading: str
    excerpt: str
    line_range: tuple[int, int]


@dataclass(frozen=True)
class BriefSourceCard:
    repository_relative_path: str
    knowledge_base: Literal["primary", "secondary"]
    document_title: str
    source_urls: tuple[str, ...]
    publisher: str
    published_updated: str
    accessed: str
    evidence_type: str
    section_previews: tuple[BriefSectionPreview, ...]


@dataclass(frozen=True)
class CampaignBriefSnapshot:
    primary_sources: tuple[BriefSourceCard, ...]
    secondary_sources: tuple[BriefSourceCard, ...]


@dataclass(frozen=True)
class CampaignAngleOption:
    key: str
    label: str
    description: str
    source_supported_focus: tuple[str, ...]
    editorial_guidance: tuple[str, ...]


@dataclass(frozen=True)
class CampaignBriefProposal:
    angle_key: str
    angle_label: str
    audience: str
    objective: str
    source_provenance_summary: str
    source_supported_focus: tuple[str, ...]
    editorial_guidance: tuple[str, ...]
    proposed_brief: str


ANGLE_OPTIONS: tuple[CampaignAngleOption, ...] = (
    CampaignAngleOption(
        key="packability",
        label="Packability",
        description="Lead with lightweight carry and easy pack-away convenience.",
        source_supported_focus=(
            "The product page describes the jacket as lightweight and highly compressible.",
            "The internal zippered chest pocket doubles as a stuffsack, which supports the pack-away story.",
        ),
        editorial_guidance=(
            "Keep water-resistant wording precise and avoid implying waterproofing.",
            "Treat historical industry evidence as background only, not as current monitoring.",
        ),
    ),
    CampaignAngleOption(
        key="practical_details",
        label="Practical product details",
        description="Emphasize verified construction, fit, weather language, and functional features.",
        source_supported_focus=(
            "Use the regular fit, windproof and water-resistant wording, and the listed functional details.",
            "Mention the brick quilting, center-front zipper, handwarmer pockets, and drop-tail hem if helpful.",
        ),
        editorial_guidance=(
            "Stay concrete and specific rather than generic lifestyle language.",
            "Do not add unsupported performance claims, discounts, or availability statements.",
        ),
    ),
    CampaignAngleOption(
        key="care_repair",
        label="Care and repair",
        description="Frame the product around washing, repair, and reuse pathways.",
        source_supported_focus=(
            "Lead with the listed care instructions before mentioning any service pathways.",
            "Use Patagonia repair and Worn Wear only as current US pathways, not as a guarantee for every item.",
        ),
        editorial_guidance=(
            "Frame care and repair as practical stewardship.",
            "Keep historical industry evidence separate from Patagonia facts.",
        ),
    ),
)

ANGLE_OPTIONS_BY_KEY = {option.key: option for option in ANGLE_OPTIONS}


def get_campaign_angle_options() -> tuple[CampaignAngleOption, ...]:
    return ANGLE_OPTIONS


def load_campaign_brief_snapshot(repo_root: str | Path | None = None) -> CampaignBriefSnapshot:
    documents = load_knowledge_base_documents(repo_root)
    primary_sources = tuple(
        _build_source_card(document) for document in documents if document.knowledge_base == "primary"
    )
    secondary_sources = tuple(
        _build_source_card(document) for document in documents if document.knowledge_base == "secondary"
    )
    return CampaignBriefSnapshot(primary_sources=primary_sources, secondary_sources=secondary_sources)


def prepare_campaign_brief(
    snapshot: CampaignBriefSnapshot,
    angle_key: str,
    audience: str,
    objective: str,
) -> CampaignBriefProposal:
    normalized_audience = audience.strip()
    normalized_objective = objective.strip()
    if not normalized_audience:
        raise ValueError("audience must be a non-empty string.")
    if not normalized_objective:
        raise ValueError("objective must be a non-empty string.")

    angle = _get_angle_option(angle_key)
    source_provenance_summary = (
        f"Source snapshot: {len(snapshot.primary_sources)} Patagonia sources and {len(snapshot.secondary_sources)} historical industry references are available."
    )
    source_supported_focus = tuple(angle.source_supported_focus)
    proposed_brief = _compose_proposed_brief(
        angle=angle,
        audience=normalized_audience,
        objective=normalized_objective,
        source_supported_focus=source_supported_focus,
    )
    return CampaignBriefProposal(
        angle_key=angle.key,
        angle_label=angle.label,
        audience=normalized_audience,
        objective=normalized_objective,
        source_provenance_summary=source_provenance_summary,
        source_supported_focus=source_supported_focus,
        editorial_guidance=angle.editorial_guidance,
        proposed_brief=proposed_brief,
    )


def _compose_proposed_brief(
    *,
    angle: CampaignAngleOption,
    audience: str,
    objective: str,
    source_supported_focus: tuple[str, ...],
) -> str:
    focus_lines = "\n".join(f"- {line}" for line in source_supported_focus)
    guidance_lines = "\n".join(f"- {line}" for line in angle.editorial_guidance)
    return (
        f"Audience: {audience}\n\n"
        f"Objective: {objective}\n\n"
        f"Angle: {angle.label}\n\n"
        "Source-supported focus:\n"
        f"{focus_lines}\n\n"
        "Editorial guidance:\n"
        f"{guidance_lines}\n\n"
        "Claim guardrails:\n"
        "- No prices, discounts, availability, unsupported performance claims, or facts from other styles or seasons.\n"
        "- Historical industry evidence stays in the background and is not current market monitoring or channel performance data.\n\n"
        "Campaign brief:\n"
        f"Use the selected channel template to write the actual Instagram, LinkedIn, or email content. "
        f"Center the {angle.label.lower()} angle, stay within the verified product focus above, and keep the same audience and objective in view."
    )


def _build_source_card(document: KnowledgeBaseDocument) -> BriefSourceCard:
    section_previews = tuple(
        preview
        for preview in (
            _build_section_preview(document, ("relevant facts",)),
            _build_section_preview(document, ("content implications", "content implications interpretation")),
            _build_section_preview(document, ("limitations",)),
        )
        if preview is not None
    )
    return BriefSourceCard(
        repository_relative_path=document.repository_relative_path,
        knowledge_base=document.knowledge_base,  # type: ignore[arg-type]
        document_title=document.metadata.document_title,
        source_urls=document.metadata.source_urls,
        publisher=document.metadata.publisher,
        published_updated=document.metadata.published_updated,
        accessed=document.metadata.accessed,
        evidence_type=document.metadata.evidence_type,
        section_previews=section_previews,
    )


def _build_section_preview(
    document: KnowledgeBaseDocument,
    headings: tuple[str, ...],
) -> BriefSectionPreview | None:
    section = _find_section(document, headings)
    if section is None:
        return None
    return BriefSectionPreview(
        heading=section.heading_text,
        excerpt=_build_section_excerpt(section.markdown, max_length=260),
        line_range=section.line_range,
    )


def _find_section(document: KnowledgeBaseDocument, headings: tuple[str, ...]) -> KnowledgeBaseSection | None:
    for target_heading in headings:
        normalized_target = _normalize_heading(target_heading)
        for section in document.sections:
            normalized_heading = _normalize_heading(section.heading_text)
            if normalized_heading.startswith(normalized_target):
                return section
    return document.sections[0] if document.sections else None


def _build_section_excerpt(markdown_text: str, *, max_length: int) -> str:
    lines = _strip_leading_heading(markdown_text.splitlines())
    if not lines:
        return ""

    blocks = _split_markdown_blocks(lines)
    excerpt_blocks: list[str] = []
    for block in blocks:
        candidate_blocks = excerpt_blocks + [block]
        candidate = "\n\n".join(candidate_blocks).strip()
        if candidate and len(candidate) <= max_length:
            excerpt_blocks.append(block)
            continue
        if not excerpt_blocks:
            return _truncate_block(block, max_length)
        break

    excerpt = "\n\n".join(excerpt_blocks).strip()
    if len(excerpt) > max_length:
        return _truncate_block(excerpt, max_length)
    return excerpt


def _strip_leading_heading(lines: list[str]) -> list[str]:
    body_lines = list(lines)
    if body_lines and body_lines[0].lstrip().startswith("#"):
        body_lines = body_lines[1:]
    while body_lines and not body_lines[0].strip():
        body_lines.pop(0)
    return body_lines


def _split_markdown_blocks(lines: list[str]) -> list[str]:
    blocks: list[str] = []
    current_block: list[str] = []
    for line in lines:
        if not line.strip():
            if current_block:
                blocks.append("\n".join(current_block).strip())
                current_block = []
            continue
        current_block.append(line.rstrip())
    if current_block:
        blocks.append("\n".join(current_block).strip())
    return [block for block in blocks if block]


def _truncate_block(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    limit = max(1, max_length - 3)
    cutoff = text.rfind(" ", 0, limit)
    if cutoff <= 0:
        cutoff = limit
    return text[:cutoff].rstrip() + "..."


def _normalize_heading(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _get_angle_option(angle_key: str) -> CampaignAngleOption:
    try:
        return ANGLE_OPTIONS_BY_KEY[angle_key]
    except KeyError as exc:
        available_angles = ", ".join(option.key for option in ANGLE_OPTIONS)
        raise ValueError(f"Unsupported campaign angle: {angle_key!r}. Available angles: {available_angles}.") from exc


__all__ = [
    "ANGLE_OPTIONS",
    "BriefSectionPreview",
    "BriefSourceCard",
    "CampaignAngleOption",
    "CampaignBriefProposal",
    "CampaignBriefSnapshot",
    "DEFAULT_BRIEF_ANGLE",
    "PRIMARY_LABEL",
    "SECONDARY_LABEL",
    "get_campaign_angle_options",
    "load_campaign_brief_snapshot",
    "prepare_campaign_brief",
]
