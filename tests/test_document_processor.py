import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.document_processor import (
    MalformedMarkdownDocumentError,
    MissingKnowledgeBaseDirectoryError,
    load_knowledge_base_documents,
)
from src.source_registry import list_sources


def _write_markdown(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _write_valid_document(path: Path, *, knowledge_base: str, title: str = "Valid Example") -> None:
    _write_markdown(
        path,
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
        ),
    )


def test_loads_real_corpus_with_expected_counts() -> None:
    documents = load_knowledge_base_documents(REPO_ROOT)

    primary_documents = [document for document in documents if document.knowledge_base == "primary"]
    secondary_documents = [document for document in documents if document.knowledge_base == "secondary"]

    assert len(primary_documents) == 4
    assert len(secondary_documents) == 2
    assert [document.repository_relative_path for document in documents] == sorted(
        document.repository_relative_path for document in documents
    )

    for document in documents:
        assert document.metadata.document_title
        assert document.metadata.source_urls
        assert document.metadata.publisher
        assert document.metadata.accessed == "2026-10-22"
        assert document.sections
        for section in document.sections:
            assert section.repository_relative_path == document.repository_relative_path
            assert section.document_metadata == document.metadata
            assert section.markdown.strip()


def test_ignores_nested_hidden_sources_in_document_discovery_and_registry_listing(tmp_path: Path) -> None:
    hidden_corpus = tmp_path / "hidden-corpus"
    hidden_primary_dir = hidden_corpus / "knowledge_base" / "primary"
    hidden_secondary_dir = hidden_corpus / "knowledge_base" / "secondary"
    hidden_primary_dir.mkdir(parents=True)
    hidden_secondary_dir.mkdir(parents=True)
    (hidden_secondary_dir / ".hidden").mkdir(parents=True)

    _write_markdown(
        hidden_secondary_dir / "visible.md",
        textwrap.dedent(
            """
            # Visible Example

            - Source URL: https://example.com/visible
            - Publisher: Example Publisher
            - Published/updated: Not stated
            - Accessed: 2026-10-22
            - Knowledge base: secondary
            - Evidence type: industry research

            ## Relevant facts

            - Visible control fact.
            """
        ),
    )
    _write_markdown(
        hidden_secondary_dir / ".hidden" / "ignored.md",
        textwrap.dedent(
            """
            # Hidden Example

            - Source URL: https://example.com/ignored
            - Publisher: Example Publisher
            - Published/updated: Not stated
            - Accessed: 2026-10-22
            - Knowledge base: secondary
            - Evidence type: industry research

            ## Relevant facts

            - Hidden fact.
            """
        ),
    )

    discovered_documents = load_knowledge_base_documents(hidden_corpus)
    assert [document.repository_relative_path for document in discovered_documents] == [
        "knowledge_base/secondary/visible.md",
    ]
    assert [record.repository_relative_path for record in list_sources(hidden_corpus)] == [
        "knowledge_base/secondary/visible.md",
    ]

def test_preserves_nested_files_metadata_heading_hierarchy_and_non_overlapping_sections(tmp_path: Path) -> None:
    primary_dir = tmp_path / "knowledge_base" / "primary"
    secondary_dir = tmp_path / "knowledge_base" / "secondary"
    nested_dir = primary_dir / "nested"
    hidden_dir = secondary_dir / ".hidden"
    nested_dir.mkdir(parents=True)
    hidden_dir.mkdir(parents=True)

    _write_markdown(primary_dir / "README.md", "# Ignore me\n")
    _write_markdown(primary_dir / ".gitkeep", "")
    _write_markdown(secondary_dir / ".hidden.md", "# Hidden\n")
    _write_markdown(
        nested_dir / "a.md",
        textwrap.dedent(
            """
            # Nested Example

            - Source URL: https://example.com/a
            - Publisher: Example Publisher
            - Published/updated: Not stated
            - Accessed: 2026-10-22
            - Knowledge base: primary
            - Evidence type: published brand content

            ## Relevant facts

            - Example fact with [source](https://example.com/a) preserved.

            ### Content implications — interpretation

            - Example interpretation.

            ## Limitations

            - Example limitation.
            """
        ),
    )
    _write_markdown(
        secondary_dir / "b.md",
        textwrap.dedent(
            """
            # Secondary Example

            - Source URL: https://example.com/b
            - Publisher: Example Publisher
            - Published/updated: Not stated
            - Accessed: 2026-10-22
            - Knowledge base: secondary
            - Evidence type: industry research

            ## Relevant facts

            - Example secondary fact.
            """
        ),
    )

    documents = load_knowledge_base_documents(tmp_path)

    assert [document.repository_relative_path for document in documents] == [
        "knowledge_base/primary/nested/a.md",
        "knowledge_base/secondary/b.md",
    ]
    assert len(documents) == 2

    primary_document = documents[0]
    assert primary_document.metadata.source_urls == ("https://example.com/a",)
    assert primary_document.sections[0].heading_path == ("Nested Example", "Relevant facts")
    assert primary_document.sections[1].heading_path == (
        "Nested Example",
        "Relevant facts",
        "Content implications — interpretation",
    )
    assert "### Content implications — interpretation" not in primary_document.sections[0].markdown
    assert "Example interpretation." not in primary_document.sections[0].markdown
    assert "## Limitations" not in primary_document.sections[1].markdown
    assert primary_document.sections[0].line_range[1] <= primary_document.sections[1].line_range[0]

    covered_lines = [
        line_number
        for section in primary_document.sections
        for line_number in range(section.line_range[0], section.line_range[1])
    ]
    assert len(covered_lines) == len(set(covered_lines))
    assert "https://example.com/a" in primary_document.sections[0].markdown


def test_deterministic_ordering_across_runs() -> None:
    first_run = load_knowledge_base_documents(REPO_ROOT)
    second_run = load_knowledge_base_documents(REPO_ROOT)

    assert [document.repository_relative_path for document in first_run] == [
        document.repository_relative_path for document in second_run
    ]
    assert [section.section_id for document in first_run for section in document.sections] == [
        section.section_id for document in second_run for section in document.sections
    ]


def test_rejects_missing_directory(tmp_path: Path) -> None:
    (tmp_path / "knowledge_base" / "primary").mkdir(parents=True)
    with pytest.raises(MissingKnowledgeBaseDirectoryError):
        load_knowledge_base_documents(tmp_path)


def test_rejects_folder_metadata_mismatch(tmp_path: Path) -> None:
    primary_dir = tmp_path / "knowledge_base" / "primary"
    secondary_dir = tmp_path / "knowledge_base" / "secondary"
    primary_dir.mkdir(parents=True)
    secondary_dir.mkdir(parents=True)

    _write_markdown(
        primary_dir / "mismatch.md",
        textwrap.dedent(
            """
            # Mismatch Example

            - Source URL: https://example.com/mismatch
            - Publisher: Example Publisher
            - Published/updated: Not stated
            - Accessed: 2026-10-22
            - Knowledge base: secondary
            - Evidence type: published brand content

            ## Relevant facts

            - Example fact.
            """
        ),
    )
    _write_valid_document(secondary_dir / "valid.md", knowledge_base="secondary")

    with pytest.raises(MalformedMarkdownDocumentError, match="mismatch.md"):
        load_knowledge_base_documents(tmp_path)


@pytest.mark.parametrize(
    ("filename", "document_text"),
    [
        (
            "blank.md",
            textwrap.dedent(
                """
                # Blank Example

                - Source URL: https://example.com/blank
                - Publisher:
                - Published/updated: Not stated
                - Accessed: 2026-10-22
                - Knowledge base: primary
                - Evidence type: published brand content

                ## Relevant facts

                - Example fact.
                """
            ),
        ),
        (
            "duplicate.md",
            textwrap.dedent(
                """
                # Duplicate Example

                - Source URL: https://example.com/duplicate
                - Publisher: Example Publisher
                - Published/updated: Not stated
                - Accessed: 2026-10-22
                - Knowledge base: primary
                - Evidence type: published brand content
                - Evidence type: competitor statement

                ## Relevant facts

                - Example fact.
                """
            ),
        ),
    ],
)
def test_rejects_blank_values_and_duplicate_required_keys(tmp_path: Path, filename: str, document_text: str) -> None:
    primary_dir = tmp_path / "knowledge_base" / "primary"
    secondary_dir = tmp_path / "knowledge_base" / "secondary"
    primary_dir.mkdir(parents=True)
    secondary_dir.mkdir(parents=True)

    _write_markdown(primary_dir / filename, document_text)
    _write_valid_document(secondary_dir / "valid.md", knowledge_base="secondary")

    with pytest.raises(MalformedMarkdownDocumentError):
        load_knowledge_base_documents(tmp_path)
