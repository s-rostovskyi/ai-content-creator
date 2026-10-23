from hashlib import sha256
from pathlib import Path

from src.document_processor import load_knowledge_base_documents
from src.rag_chunking import ChunkingPolicy, build_rag_chunks

PRIMARY_URL = "https://www.patagonia.com/product/mens-nano-puff-insulated-jacket/84212.html"
SECONDARY_URL = "https://example.com/outdoor-context"


def _write_document(
    path: Path,
    *,
    title: str,
    source_url: str,
    knowledge_base: str,
    facts: str,
    editorial: str,
    limitations: str,
    evidence_type: str = "official statement",
    publisher: str = "Example Publisher",
    accessed: str = "2026-10-22",
    published_updated: str = "Not stated",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        chr(10).join(
            [
                f"# {title}",
                "",
                f"- Source URL: {source_url}",
                f"- Publisher: {publisher}",
                f"- Published/updated: {published_updated}",
                f"- Accessed: {accessed}",
                f"- Knowledge base: {knowledge_base}",
                f"- Evidence type: {evidence_type}",
                "",
                "## Relevant facts",
                "",
                facts,
                "",
                "## Content implications",
                "",
                editorial,
                "",
                "## Limitations",
                "",
                limitations,
            ]
        ) + chr(10),
        encoding="utf-8",
    )


def _build_primary_doc(root: Path, *, limitation_note: str) -> Path:
    (root / "knowledge_base" / "secondary").mkdir(parents=True, exist_ok=True)
    target = root / "knowledge_base" / "primary" / "example.md"
    _write_document(
        target,
        title="Example Primary Document",
        source_url=PRIMARY_URL,
        knowledge_base="primary",
        facts="Fact one with a compact supporting sentence.",
        editorial="Editorial note one with a short interpretation.",
        limitations=f"- {limitation_note}",
        publisher="Patagonia, US website",
    )
    return target


def _build_long_section_doc(root: Path) -> Path:
    (root / "knowledge_base" / "secondary").mkdir(parents=True, exist_ok=True)
    target = root / "knowledge_base" / "primary" / "long-section.md"
    long_tail = " ".join(["This run-on sentence keeps going for deterministic fallback splitting"] * 8)
    _write_document(
        target,
        title="Long Section Example",
        source_url=PRIMARY_URL,
        knowledge_base="primary",
        facts="Short intro paragraph." + chr(10) + chr(10) + f"Sentence one. Sentence two. {long_tail}.",
        editorial="Editorial note with enough detail to remain small.",
        limitations="- Long sections still keep the same document limitations.",
        publisher="Patagonia, US website",
    )
    return target


def test_chunking_preserves_provenance_limitations_and_stable_ids(tmp_path: Path) -> None:
    _build_primary_doc(tmp_path, limitation_note="Do not infer availability or pricing.")
    documents = load_knowledge_base_documents(tmp_path)

    chunks = build_rag_chunks(documents, policy=ChunkingPolicy(max_chunk_characters=200))
    repeat_chunks = build_rag_chunks(documents, policy=ChunkingPolicy(max_chunk_characters=200))

    assert [chunk.chunk_kind for chunk in chunks] == ["facts", "editorial", "limitations"]
    assert [chunk.chunk_id for chunk in chunks] == [chunk.chunk_id for chunk in repeat_chunks]
    expected_hash = sha256((tmp_path / "knowledge_base" / "primary" / "example.md").read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    assert all(chunk.document_hash == expected_hash for chunk in chunks)
    assert chunks[0].applicable_limitations == "- Do not infer availability or pricing."
    assert chunks[1].applicable_limitations == "- Do not infer availability or pricing."
    assert chunks[2].applicable_limitations == "- Do not infer availability or pricing."
    assert chunks[0].section_heading_path[-1] == "Relevant facts"
    assert chunks[1].section_heading_path[-1].startswith("Content implications")
    assert chunks[2].section_heading_path[-1] == "Limitations"

    changed_root = tmp_path / "changed"
    _build_primary_doc(changed_root, limitation_note="Do not infer availability, pricing, or discounts.")
    changed_chunks = build_rag_chunks(load_knowledge_base_documents(changed_root), policy=ChunkingPolicy(max_chunk_characters=200))

    assert [chunk.chunk_text for chunk in chunks[:2]] == [chunk.chunk_text for chunk in changed_chunks[:2]]
    assert [chunk.chunk_id for chunk in chunks[:2]] != [chunk.chunk_id for chunk in changed_chunks[:2]]


def test_chunking_splits_long_sections_at_boundaries_and_fallbacks(tmp_path: Path) -> None:
    _build_long_section_doc(tmp_path)
    documents = load_knowledge_base_documents(tmp_path)

    chunks = build_rag_chunks(documents, policy=ChunkingPolicy(max_chunk_characters=120))

    assert len(chunks) > 1
    assert all(len(chunk.chunk_text) <= 120 for chunk in chunks)
    assert len({chunk.section_id for chunk in chunks}) == 3
    assert any("Short intro paragraph." in chunk.chunk_text for chunk in chunks)
    assert any("Sentence one." in chunk.chunk_text for chunk in chunks)
    assert any("deterministic fallback splitting" in chunk.chunk_text for chunk in chunks)
    section_ranges = {chunk.section_id: chunk.section_line_range for chunk in chunks}
    assert all(chunk.chunk_line_range[0] >= section_ranges[chunk.section_id][0] for chunk in chunks)
    assert all(chunk.chunk_line_range[1] <= section_ranges[chunk.section_id][1] for chunk in chunks)
