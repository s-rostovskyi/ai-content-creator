import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.knowledge_base import (
    ContextSizeLimitExceededError,
    EmptyKnowledgeBaseError,
    assemble_context_bundle,
)


def _write_document(path: Path, knowledge_base: str, title: str = "Example") -> None:
    path.write_text(
        textwrap.dedent(
            f"""
            # {title}

            - Source URL: https://example.com/{path.stem}
            - Publisher: Example Publisher
            - Published/updated: Not stated
            - Accessed: 2026-10-22
            - Knowledge base: {knowledge_base}
            - Evidence type: published brand content

            ## Relevant facts

            - Example fact.
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def test_real_corpus_context_bundle_has_expected_counts_and_manifest_order() -> None:
    bundle = assemble_context_bundle(REPO_ROOT)

    assert bundle.corpus_measurements.primary_document_count == 5
    assert bundle.corpus_measurements.secondary_document_count == 2
    assert bundle.corpus_measurements.total_document_count == 7
    assert [entry.repository_relative_path for entry in bundle.source_manifest] == [
        "knowledge_base/primary/brand_voice.md",
        "knowledge_base/primary/past_content/examples.md",
        "knowledge_base/primary/product_facts.md",
        "knowledge_base/primary/repair_and_reuse.md",
        "knowledge_base/primary/torrentshell_85241.md",
        "knowledge_base/secondary/competitor_context.md",
        "knowledge_base/secondary/market_trends.md",
    ]
    assert all(entry.knowledge_base == "primary" for entry in bundle.source_manifest[:5])
    assert all(entry.knowledge_base == "secondary" for entry in bundle.source_manifest[5:])
    assert bundle.primary_context.startswith("# Patagonia evidence")
    assert bundle.secondary_context.startswith("# Industry/competitor evidence")


def test_repeated_assembly_is_identical_and_brief_independent_by_design() -> None:
    briefs = [
        "Launch a winter layer campaign.",
        "Adapt the message for sustainability-aware customers.",
        "Draft a LinkedIn version for the sales team.",
    ]

    bundles = [assemble_context_bundle(REPO_ROOT) for _ in briefs]

    assert bundles[0] == bundles[1] == bundles[2]


def test_serialization_preserves_source_links_dates_and_limitations() -> None:
    bundle = assemble_context_bundle(REPO_ROOT)

    assert "Source URL:" in bundle.primary_context
    assert "Accessed: 2026-10-22" in bundle.primary_context
    assert "Limitations" in bundle.primary_context
    assert "https://www.patagonia.com/product/mens-nano-puff-insulated-jacket/84212.html" in bundle.primary_context
    assert "Source URL:" in bundle.secondary_context
    assert "Limitations" in bundle.secondary_context


def test_primary_and_secondary_evidence_remain_separate() -> None:
    bundle = assemble_context_bundle(REPO_ROOT)

    assert "# Patagonia evidence" in bundle.primary_context
    assert "# Industry/competitor evidence" in bundle.secondary_context
    assert bundle.primary_context != bundle.secondary_context
    assert all(entry.knowledge_base == "primary" for entry in bundle.source_manifest[:5])
    assert all(entry.knowledge_base == "secondary" for entry in bundle.source_manifest[5:])


@pytest.mark.parametrize("empty_side", ["primary", "secondary"])
def test_empty_knowledge_base_is_rejected(tmp_path: Path, empty_side: str) -> None:
    primary_dir = tmp_path / "knowledge_base" / "primary"
    secondary_dir = tmp_path / "knowledge_base" / "secondary"
    primary_dir.mkdir(parents=True)
    secondary_dir.mkdir(parents=True)

    if empty_side == "primary":
        _write_document(secondary_dir / "secondary.md", "secondary")
    else:
        _write_document(primary_dir / "primary.md", "primary")

    with pytest.raises(EmptyKnowledgeBaseError):
        assemble_context_bundle(tmp_path)


def test_oversized_context_raises_without_partial_output(tmp_path: Path) -> None:
    primary_dir = tmp_path / "knowledge_base" / "primary"
    secondary_dir = tmp_path / "knowledge_base" / "secondary"
    primary_dir.mkdir(parents=True)
    secondary_dir.mkdir(parents=True)

    _write_document(primary_dir / "primary.md", "primary", title="Primary Large")
    _write_document(secondary_dir / "secondary.md", "secondary", title="Secondary Large")

    with pytest.raises(ContextSizeLimitExceededError, match="exceeding the limit"):
        assemble_context_bundle(tmp_path, max_serialized_characters=1)
