from pathlib import Path
import hashlib
import sys
import textwrap

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.source_registry import (
    MAX_SOURCE_UPLOAD_BYTES,
    PreparedSourceOperation,
    SourceConflictError,
    SourceNotFoundError,
    SourcePathError,
    SourceSnapshot,
    SourceValidationError,
    SourceWriteError,
    apply_prepared_source_operation,
    list_sources,
    prepare_create_source,
    prepare_delete_source,
    prepare_edit_source,
    read_source,
)


VALID_PRIMARY_URL = "https://www.patagonia.com/product/mens-nano-puff-insulated-jacket/84212.html"
VALID_SECONDARY_URL = "https://example.com/outdoor-trends"


def _write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def _valid_document(*, title: str, source_url: str, knowledge_base: str, fact: str = "Example fact.") -> str:
    return textwrap.dedent(
        f"""
        # {title}

        - Source URL: {source_url}
        - Publisher: Example Publisher
        - Published/updated: Not stated
        - Accessed: 2026-10-22
        - Knowledge base: {knowledge_base}
        - Evidence type: official statement

        ## Relevant facts

        - {fact}
        """
    ).strip() + "\n"


def _primary_source(path: str, fact: str = "Example fact.") -> str:
    return _valid_document(title="Primary Example", source_url=VALID_PRIMARY_URL, knowledge_base="primary", fact=fact)


def _secondary_source(path: str, fact: str = "Example fact.") -> str:
    return _valid_document(title="Secondary Example", source_url=VALID_SECONDARY_URL, knowledge_base="secondary", fact=fact)


def test_lists_reads_and_sorts_nested_sources(tmp_path: Path) -> None:
    primary_nested = tmp_path / "knowledge_base" / "primary" / "nested" / "a.md"
    secondary_file = tmp_path / "knowledge_base" / "secondary" / "b.md"
    _write_markdown(primary_nested, _primary_source("a", fact="Nested fact."))
    _write_markdown(secondary_file, _secondary_source("b", fact="Secondary fact."))
    _write_markdown(tmp_path / "knowledge_base" / "primary" / "README.md", "# Ignore me")
    _write_markdown(tmp_path / "knowledge_base" / "secondary" / ".gitkeep", "")

    records = list_sources(tmp_path)

    assert [record.repository_relative_path for record in records] == [
        "knowledge_base/primary/nested/a.md",
        "knowledge_base/secondary/b.md",
    ]
    assert records[0].source_hash == hashlib.sha256(primary_nested.read_bytes()).hexdigest()

    snapshot = read_source(records[0].source_id, tmp_path)
    assert isinstance(snapshot, SourceSnapshot)
    assert snapshot.source_hash == records[0].source_hash
    assert snapshot.document.metadata.document_title == "Primary Example"
    assert snapshot.document.metadata.knowledge_base == "primary"


def test_prepares_create_edit_and_delete_with_versioned_apply(tmp_path: Path) -> None:
    primary_file = tmp_path / "knowledge_base" / "primary" / "seed.md"
    secondary_file = tmp_path / "knowledge_base" / "secondary" / "seed.md"
    _write_markdown(primary_file, _primary_source("seed", fact="Seed fact."))
    _write_markdown(secondary_file, _secondary_source("seed", fact="Seed fact."))

    create_preview = prepare_create_source(
        "knowledge_base/primary/new.md",
        _primary_source("new", fact="Created fact."),
        tmp_path,
    )
    assert isinstance(create_preview, PreparedSourceOperation)
    create_result = apply_prepared_source_operation(create_preview, tmp_path)
    created_path = tmp_path / "knowledge_base" / "primary" / "new.md"
    assert created_path.exists()
    assert create_result.operation == "create"
    assert create_result.current_source_hash == create_preview.snapshot.source_hash
    assert create_result.changed_paths == ("knowledge_base/primary/new.md",)
    assert create_result.index_sync_required is True

    original_snapshot = read_source("knowledge_base/primary/seed.md", tmp_path)
    edit_preview = prepare_edit_source(
        "knowledge_base/primary/seed.md",
        _primary_source("seed", fact="Edited fact."),
        original_snapshot.source_hash,
        tmp_path,
    )
    edit_result = apply_prepared_source_operation(edit_preview, tmp_path)
    assert edit_result.operation == "edit"
    assert edit_result.previous_source_hash == original_snapshot.source_hash
    assert edit_result.current_source_hash == edit_preview.snapshot.source_hash
    assert read_source("knowledge_base/primary/seed.md", tmp_path).document.markdown.endswith("Edited fact.\n")

    delete_snapshot = read_source("knowledge_base/primary/new.md", tmp_path)
    delete_preview = prepare_delete_source(
        "knowledge_base/primary/new.md",
        delete_snapshot.source_hash,
        tmp_path,
    )
    delete_result = apply_prepared_source_operation(delete_preview, tmp_path)
    assert delete_result.operation == "delete"
    assert not created_path.exists()
    assert delete_result.previous_source_hash == delete_snapshot.source_hash
    assert delete_result.current_source_hash is None


@pytest.mark.parametrize(
    "document_text",
    [
        _valid_document(
            title="Blank Publisher",
            source_url=VALID_PRIMARY_URL,
            knowledge_base="primary",
        ).replace("- Publisher: Example Publisher", "- Publisher:"),
        _valid_document(
            title="Duplicate Evidence",
            source_url=VALID_PRIMARY_URL,
            knowledge_base="primary",
        ).replace(
            "- Evidence type: official statement",
            "- Evidence type: official statement\n- Evidence type: competitor statement",
        ),
    ],
)
def test_rejects_malformed_metadata_in_previews(tmp_path: Path, document_text: str) -> None:
    with pytest.raises(SourceValidationError):
        prepare_create_source("knowledge_base/primary/bad.md", document_text, tmp_path)


def test_rejects_invalid_utf8_on_read(tmp_path: Path) -> None:
    bad_path = tmp_path / "knowledge_base" / "primary" / "bad.md"
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_path.write_bytes(
        (
            "# Bad\n\n"
            "- Source URL: https://www.patagonia.com/product/mens-nano-puff-insulated-jacket/84212.html\n"
            "- Publisher: Example Publisher\n"
            "- Published/updated: Not stated\n"
            "- Accessed: 2026-10-22\n"
            "- Knowledge base: primary\n"
            "- Evidence type: official statement\n\n"
            "## Relevant facts\n\n"
            "- Example fact.\n"
        ).encode("utf-8") + b"\xff"
    )

    with pytest.raises(SourceValidationError):
        read_source("knowledge_base/primary/bad.md", tmp_path)


def test_rejects_domain_spoofing_in_primary_metadata(tmp_path: Path) -> None:
    spoofed = _valid_document(
        title="Spoofed Primary",
        source_url="https://www.patagonia.com.evil.com/product",
        knowledge_base="primary",
    )
    with pytest.raises(SourceValidationError):
        prepare_create_source("knowledge_base/primary/spoofed.md", spoofed, tmp_path)


def test_rejects_traversal_absolute_and_symlink_paths(tmp_path: Path) -> None:
    valid = _primary_source("safe")
    with pytest.raises(SourcePathError):
        prepare_create_source("../escape.md", valid, tmp_path)
    with pytest.raises(SourcePathError):
        prepare_create_source(str(tmp_path / "knowledge_base" / "primary" / "abs.md"), valid, tmp_path)

    outside_file = tmp_path / "outside.md"
    outside_file.write_text("outside", encoding="utf-8")
    symlink_path = tmp_path / "knowledge_base" / "primary" / "linked.md"
    symlink_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        symlink_path.symlink_to(outside_file)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is not supported in this environment.")

    with pytest.raises(SourcePathError):
        read_source("knowledge_base/primary/linked.md", tmp_path)


def test_rejects_stale_versions_and_creation_collisions(tmp_path: Path) -> None:
    target = tmp_path / "knowledge_base" / "primary" / "seed.md"
    _write_markdown(target, _primary_source("seed", fact="Original fact."))
    original_snapshot = read_source("knowledge_base/primary/seed.md", tmp_path)

    _write_markdown(target, _primary_source("seed", fact="Changed on disk."))
    with pytest.raises(SourceConflictError):
        prepare_edit_source(
            "knowledge_base/primary/seed.md",
            _primary_source("seed", fact="Edited fact."),
            original_snapshot.source_hash,
            tmp_path,
        )

    with pytest.raises(SourceConflictError):
        prepare_create_source("knowledge_base/primary/seed.md", _primary_source("seed", fact="Dup."), tmp_path)


def test_rejects_oversized_source_bytes_before_parsing(tmp_path: Path) -> None:
    oversized_markdown = "a" * (MAX_SOURCE_UPLOAD_BYTES + 1)
    with pytest.raises(SourceValidationError, match="maximum allowed size"):
        prepare_create_source("knowledge_base/secondary/too-large.md", oversized_markdown, tmp_path)


def test_apply_write_failure_preserves_existing_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "knowledge_base" / "primary" / "seed.md"
    _write_markdown(target, _primary_source("seed", fact="Original fact."))
    original_contents = target.read_text(encoding="utf-8")
    snapshot = read_source("knowledge_base/primary/seed.md", tmp_path)
    preview = prepare_edit_source(
        "knowledge_base/primary/seed.md",
        _primary_source("seed", fact="Edited fact."),
        snapshot.source_hash,
        tmp_path,
    )

    def _raise_permission_error(*args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr("src.source_registry.os.replace", _raise_permission_error)

    with pytest.raises(SourceWriteError):
        apply_prepared_source_operation(preview, tmp_path)

    assert target.read_text(encoding="utf-8") == original_contents
    assert read_source("knowledge_base/primary/seed.md", tmp_path).source_hash == snapshot.source_hash


def test_conflict_preserves_newer_source_for_edit_and_delete(tmp_path: Path) -> None:
    target = tmp_path / "knowledge_base" / "primary" / "seed.md"
    _write_markdown(target, _primary_source("seed", fact="Original fact."))

    original_snapshot = read_source("knowledge_base/primary/seed.md", tmp_path)
    edit_preview = prepare_edit_source(
        "knowledge_base/primary/seed.md",
        _primary_source("seed", fact="Edited fact."),
        original_snapshot.source_hash,
        tmp_path,
    )

    _write_markdown(target, _primary_source("seed", fact="Newer fact."))
    newer_snapshot = read_source("knowledge_base/primary/seed.md", tmp_path)

    with pytest.raises(SourceConflictError):
        apply_prepared_source_operation(edit_preview, tmp_path)

    assert read_source("knowledge_base/primary/seed.md", tmp_path).source_hash == newer_snapshot.source_hash
    assert "Newer fact." in target.read_text(encoding="utf-8")

    delete_preview = prepare_delete_source(
        "knowledge_base/primary/seed.md",
        newer_snapshot.source_hash,
        tmp_path,
    )
    _write_markdown(target, _primary_source("seed", fact="Newer fact after delete preview."))
    protected_snapshot = read_source("knowledge_base/primary/seed.md", tmp_path)

    with pytest.raises(SourceConflictError):
        apply_prepared_source_operation(delete_preview, tmp_path)

    assert target.exists()
    assert read_source("knowledge_base/primary/seed.md", tmp_path).source_hash == protected_snapshot.source_hash
