from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.campaign_brief import _build_section_excerpt, load_campaign_brief_snapshot, prepare_campaign_brief


def test_campaign_brief_snapshot_separates_primary_and_secondary_sources() -> None:
    snapshot = load_campaign_brief_snapshot(REPO_ROOT)

    assert len(snapshot.primary_sources) == 4
    assert len(snapshot.secondary_sources) == 2

    for card in snapshot.primary_sources:
        assert card.knowledge_base == "primary"
        assert card.repository_relative_path.startswith("knowledge_base/primary/")
        assert card.source_urls
        assert card.publisher
        assert card.published_updated
        assert card.accessed
        assert card.evidence_type
        headings = [preview.heading.lower() for preview in card.section_previews]
        assert any(heading.startswith("relevant facts") for heading in headings)
        assert any(heading.startswith("content implications") for heading in headings)
        assert any(heading.startswith("limitations") for heading in headings)
        for preview in card.section_previews:
            assert preview.line_range[0] < preview.line_range[1]
            assert preview.excerpt

    for card in snapshot.secondary_sources:
        assert card.knowledge_base == "secondary"
        assert card.repository_relative_path.startswith("knowledge_base/secondary/")
        assert card.source_urls
        assert card.publisher
        assert card.published_updated
        assert card.accessed
        assert card.evidence_type


def test_build_section_excerpt_strips_heading_and_preserves_body_markdown() -> None:
    markdown_text = """## Relevant facts

This paragraph should render as normal body text with a [source link](https://example.com).

- First list item
- Second list item
"""

    excerpt = _build_section_excerpt(markdown_text, max_length=260)

    assert not excerpt.lstrip().startswith("#")
    assert "Relevant facts" not in excerpt.splitlines()[0]
    assert "This paragraph should render as normal body text" in excerpt
    assert "- First list item" in excerpt
    assert "[source link](https://example.com)" in excerpt


def test_prepare_campaign_brief_is_deterministic_and_keeps_historical_context_separate() -> None:
    snapshot = load_campaign_brief_snapshot(REPO_ROOT)

    proposal = prepare_campaign_brief(
        snapshot,
        "packability",
        "English-speaking US audience planning everyday outings and outdoor trips",
        "Create a concise campaign brief for all three channels",
    )
    repeated_proposal = prepare_campaign_brief(
        snapshot,
        "packability",
        "English-speaking US audience planning everyday outings and outdoor trips",
        "Create a concise campaign brief for all three channels",
    )

    assert proposal == repeated_proposal
    assert proposal.angle_key == "packability"
    assert proposal.angle_label == "Packability"
    assert proposal.source_provenance_summary == (
        "Source snapshot: 4 Patagonia sources and 2 historical industry references are available."
    )
    assert proposal.source_supported_focus == (
        "The product page describes the jacket as lightweight and highly compressible.",
        "The internal zippered chest pocket doubles as a stuffsack, which supports the pack-away story.",
    )
    assert any("historical industry evidence" in item.lower() for item in proposal.editorial_guidance)
    assert "Historical industry evidence stays in the background" in proposal.proposed_brief
    assert "Claim guardrails:" in proposal.proposed_brief
    assert "Use the selected channel template to write the actual Instagram, LinkedIn, or email content." in proposal.proposed_brief


@pytest.mark.parametrize(
    ("audience", "objective", "expected_message"),
    [
        ("", "Create a campaign brief", "audience must be a non-empty string."),
        ("US hikers", "", "objective must be a non-empty string."),
    ],
)
def test_prepare_campaign_brief_requires_audience_and_objective(
    audience: str,
    objective: str,
    expected_message: str,
) -> None:
    snapshot = load_campaign_brief_snapshot(REPO_ROOT)

    with pytest.raises(ValueError, match=expected_message):
        prepare_campaign_brief(snapshot, "packability", audience, objective)
