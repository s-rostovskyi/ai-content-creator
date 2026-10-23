from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.document_processor import load_knowledge_base_documents
from src.embedding_integration import OpenAIEmbeddingSettings
from src.rag_chunking import build_rag_chunks
from src.rag_index import build_corpus_snapshot, open_vector_index, write_vector_index
from src.rag_retrieval import (
    RetrievalConfigurationError,
    RetrievalStaleCorpusError,
    build_retrieval_query,
    plan_rag_context_retrieval,
    render_rag_retrieval_result,
    retrieve_rag_context,
)

PRIMARY_URL = "https://www.patagonia.com/product/mens-nano-puff-insulated-jacket/84212.html"
SECONDARY_URL = "https://example.com/outdoor-context"


@dataclass(frozen=True)
class _FakeEmbeddingItem:
    index: int
    embedding: list[float]


class _FakeEmbeddingsService:
    def __init__(self, *, model: str, vector: list[float] | None = None) -> None:
        self.model = model
        self.vector = list(vector or [1.0, 0.0])
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        inputs = list(kwargs["input"])
        data = [_FakeEmbeddingItem(index=index, embedding=list(self.vector)) for index in range(len(inputs))]
        return SimpleNamespace(
            model=self.model,
            data=data,
            usage=SimpleNamespace(prompt_tokens=sum(len(text) for text in inputs), total_tokens=sum(len(text) for text in inputs)),
        )


class _FakeEmbeddingsClient:
    def __init__(self, *, model: str, vector: list[float] | None = None) -> None:
        self.embeddings = _FakeEmbeddingsService(model=model, vector=vector)



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
        )
        + chr(10),
        encoding="utf-8",
    )



def _build_corpus(root: Path, *, primary_fact_alpha: str = "Primary alpha fact.", primary_fact_beta: str = "Primary beta fact.", secondary_fact: str = "Secondary fact.", primary_editorial: str = "Primary editorial interpretation.", secondary_editorial: str = "Secondary editorial interpretation.", primary_limitations: str = "- Primary limitations stay attached to each chunk.", secondary_limitations: str = "- Secondary limitations stay attached to each chunk.") -> None:
    _write_document(
        root / "knowledge_base" / "primary" / "alpha.md",
        title="Alpha",
        source_url=PRIMARY_URL,
        knowledge_base="primary",
        facts=primary_fact_alpha,
        editorial=primary_editorial,
        limitations=primary_limitations,
        publisher="Patagonia, US website",
    )
    _write_document(
        root / "knowledge_base" / "primary" / "beta.md",
        title="Beta",
        source_url=PRIMARY_URL,
        knowledge_base="primary",
        facts=primary_fact_beta,
        editorial=primary_editorial,
        limitations=primary_limitations,
        publisher="Patagonia, US website",
    )
    _write_document(
        root / "knowledge_base" / "secondary" / "gamma.md",
        title="Gamma",
        source_url=SECONDARY_URL,
        knowledge_base="secondary",
        facts=secondary_fact,
        editorial=secondary_editorial,
        limitations=secondary_limitations,
        publisher="Example Publisher",
    )



def _chunk_vectors(chunks, *, primary_fact: tuple[float, float], primary_editorial: tuple[float, float], secondary: tuple[float, float]) -> dict[str, list[float]]:
    vectors: dict[str, list[float]] = {}
    for chunk in chunks:
        if chunk.knowledge_base == "primary" and chunk.chunk_kind == "facts":
            vector = primary_fact
        elif chunk.knowledge_base == "primary":
            vector = primary_editorial
        else:
            vector = secondary
        vectors[chunk.chunk_id] = [float(vector[0]), float(vector[1])]
    return vectors



def _build_index(root: Path, *, primary_fact=(1.0, 0.0), primary_editorial=(0.92, 0.08), secondary=(0.0, 1.0), model: str = "text-embedding-3-small") -> tuple[Path, object]:
    documents = load_knowledge_base_documents(root)
    chunks = build_rag_chunks(documents)
    snapshot = build_corpus_snapshot(documents)
    index_path = root / ".rag" / "rag_index.sqlite3"
    write_vector_index(
        index_path,
        corpus_snapshot=snapshot,
        chunks=chunks,
        vectors_by_chunk_id=_chunk_vectors(
            chunks,
            primary_fact=primary_fact,
            primary_editorial=primary_editorial,
            secondary=secondary,
        ),
        embedding_model_id=model,
        vector_dimensions=2,
    )
    return index_path, snapshot



def test_build_retrieval_query_is_deterministic() -> None:
    query = build_retrieval_query("instagram", "Lead with packability.", "Please make it warmer.")

    assert query == (
        "## Retrieval query\n"
        "Channel: instagram\n"
        "Campaign brief:\n"
        "Lead with packability.\n"
        "Revision feedback:\n"
        "Please make it warmer.\n"
        "End of retrieval query."
    )



def test_plan_reports_model_and_existing_index_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _build_corpus(tmp_path)
    _build_index(tmp_path)
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    plan = plan_rag_context_retrieval(
        repo_root=tmp_path,
        index_path=tmp_path / ".rag" / "rag_index.sqlite3",
        channel="instagram",
        campaign_brief="Lead with packability.",
    )

    assert plan.embedding_model_id == "text-embedding-3-small"
    assert plan.existing_index_matches is True
    assert plan.existing_index_reason == "ready"
    assert plan.query_character_count == len(build_retrieval_query("instagram", "Lead with packability."))
    assert not (tmp_path / ".rag" / "rag_index.sqlite3.new").exists()



def test_live_retrieval_keeps_primary_and_secondary_pools_separate(tmp_path: Path) -> None:
    _build_corpus(tmp_path)
    index_path, snapshot = _build_index(tmp_path)
    client = _FakeEmbeddingsClient(model="text-embedding-3-small")
    settings = OpenAIEmbeddingSettings(api_key="test-key", model="text-embedding-3-small")

    result = retrieve_rag_context(
        repo_root=tmp_path,
        index_path=index_path,
        channel="instagram",
        campaign_brief="Lead with packability.",
        settings=settings,
        client=client,
        primary_top_k=4,
        secondary_top_k=4,
        primary_minimum_similarity=0.0,
        secondary_minimum_similarity=0.0,
    )

    assert result.corpus_snapshot.snapshot_id == snapshot.snapshot_id
    assert len(client.embeddings.calls) == 1
    assert client.embeddings.calls[0]["input"][0] == build_retrieval_query("instagram", "Lead with packability.")
    assert all(result.chunk.knowledge_base == "primary" for result in result.primary_results)
    assert all(result.chunk.knowledge_base == "secondary" for result in result.secondary_results)
    assert result.context_bundle is not None
    assert result.context_bundle.retrieval_measurements.primary_fact_count > 0
    assert result.manifest.included_sources == result.context_bundle.source_manifest
    assert result.manifest.corpus_snapshot_id == snapshot.snapshot_id
    assert result.manifest.embedding_model_id == "text-embedding-3-small"


def test_primary_fact_chunk_is_promoted_above_editorial_chunks_by_lexical_signal(tmp_path: Path) -> None:
    _build_corpus(
        tmp_path,
        primary_fact_alpha="The internal chest pocket doubles as a stuffsack.",
        primary_fact_beta="Primary beta fact.",
        primary_editorial="Editorial guidance says packability should lead.",
    )
    index_path, _ = _build_index(
        tmp_path,
        primary_fact=(0.70, 0.71),
        primary_editorial=(0.72, 0.69),
        secondary=(0.0, 1.0),
    )
    client = _FakeEmbeddingsClient(model="text-embedding-3-small", vector=[1.0, 0.0])
    settings = OpenAIEmbeddingSettings(api_key="test-key", model="text-embedding-3-small")

    result = retrieve_rag_context(
        repo_root=tmp_path,
        index_path=index_path,
        channel="instagram",
        campaign_brief="Lead with packability and the internal chest pocket that doubles as a stuffsack.",
        settings=settings,
        client=client,
        primary_top_k=3,
        secondary_top_k=2,
        primary_minimum_similarity=0.0,
        secondary_minimum_similarity=0.0,
    )

    assert result.primary_results[0].chunk.chunk_kind == "facts"
    assert "stuffsack" in result.primary_results[0].chunk.chunk_text.lower()
    assert result.context_bundle is not None
    assert "stuffsack" in result.context_bundle.primary_context.lower()
    assert any(reason.endswith(":ranked_out") for reason in result.manifest.omission_reasons)



def test_paraphrased_query_still_selects_primary_fact_without_exact_phrase_match(tmp_path: Path) -> None:
    _build_corpus(
        tmp_path,
        primary_fact_alpha="The internal chest pocket doubles as a stuffsack.",
        primary_fact_beta="Primary beta fact.",
        primary_editorial="Editorial guidance says packability should lead.",
    )
    index_path, _ = _build_index(
        tmp_path,
        primary_fact=(0.76, 0.65),
        primary_editorial=(0.74, 0.67),
        secondary=(0.0, 1.0),
    )
    client = _FakeEmbeddingsClient(model="text-embedding-3-small", vector=[0.75, 0.64])
    settings = OpenAIEmbeddingSettings(api_key="test-key", model="text-embedding-3-small")

    result = retrieve_rag_context(
        repo_root=tmp_path,
        index_path=index_path,
        channel="instagram",
        campaign_brief="Keep it easy to pack away for travel.",
        settings=settings,
        client=client,
        primary_top_k=3,
        secondary_top_k=2,
        primary_minimum_similarity=0.0,
        secondary_minimum_similarity=0.0,
    )

    assert result.primary_results[0].chunk.chunk_kind == "facts"
    assert "stuffsack" in result.context_bundle.primary_context.lower()



def test_live_retrieval_blocks_when_no_primary_facts_are_retrieved(tmp_path: Path) -> None:
    _build_corpus(tmp_path)
    index_path, _ = _build_index(tmp_path, primary_fact=(0.0, 1.0), primary_editorial=(0.0, 1.0), secondary=(1.0, 0.0))
    client = _FakeEmbeddingsClient(model="text-embedding-3-small")
    settings = OpenAIEmbeddingSettings(api_key="test-key", model="text-embedding-3-small")

    result = retrieve_rag_context(
        repo_root=tmp_path,
        index_path=index_path,
        channel="instagram",
        campaign_brief="Lead with packability.",
        settings=settings,
        client=client,
        primary_minimum_similarity=0.5,
        secondary_minimum_similarity=0.5,
    )

    assert result.blocked_reason == "No primary factual evidence met the configured similarity threshold."
    assert result.primary_results == ()
    assert result.secondary_results
    assert result.secondary_results[0].chunk.knowledge_base == "secondary"
    assert result.context_bundle is None
    assert result.manifest.included_sources == ()
    assert "no_primary_factual_evidence" in result.manifest.omission_reasons
    assert any(reason.endswith(":unsupported_chunk_kind") for reason in result.manifest.omission_reasons)



def test_budget_preserves_limitations_without_truncating_claims(tmp_path: Path) -> None:
    _build_corpus(
        tmp_path,
        primary_fact_alpha="Alpha fact keeps its full claim and stays intact.",
        primary_fact_beta="Beta fact should be omitted by the budget.",
        primary_editorial="Primary editorial interpretation remains separate.",
    )
    index_path, _ = _build_index(tmp_path)
    client = _FakeEmbeddingsClient(model="text-embedding-3-small")
    settings = OpenAIEmbeddingSettings(api_key="test-key", model="text-embedding-3-small")

    result = retrieve_rag_context(
        repo_root=tmp_path,
        index_path=index_path,
        channel="instagram",
        campaign_brief="Lead with packability.",
        settings=settings,
        client=client,
        primary_top_k=4,
        secondary_top_k=1,
        primary_minimum_similarity=0.0,
        secondary_minimum_similarity=0.1,
        max_context_characters=900,
    )

    assert result.context_bundle is not None
    assert "Alpha fact keeps its full claim and stays intact." in result.context_bundle.primary_context
    assert "- Primary limitations stay attached to each chunk." in result.context_bundle.primary_context
    assert "Beta fact should be omitted by the budget." not in result.context_bundle.primary_context
    assert result.context_bundle.retrieval_measurements.serialized_context_characters <= 900
    assert any(reason.endswith(":budget_exceeded") for reason in result.manifest.omission_reasons)



def test_manifest_matches_included_context(tmp_path: Path) -> None:
    _build_corpus(tmp_path)
    index_path, _ = _build_index(tmp_path)
    client = _FakeEmbeddingsClient(model="text-embedding-3-small")
    settings = OpenAIEmbeddingSettings(api_key="test-key", model="text-embedding-3-small")

    result = retrieve_rag_context(
        repo_root=tmp_path,
        index_path=index_path,
        channel="instagram",
        campaign_brief="Lead with packability.",
        settings=settings,
        client=client,
        primary_top_k=3,
        secondary_top_k=2,
        primary_minimum_similarity=0.0,
        secondary_minimum_similarity=0.0,
    )

    assert result.context_bundle is not None
    assert result.manifest.included_sources == result.context_bundle.source_manifest
    assert {entry.repository_relative_path for entry in result.manifest.included_sources} == {
        entry.repository_relative_path for entry in result.context_bundle.source_manifest
    }
    assert result.manifest.query_usage is not None
    assert result.manifest.query_elapsed_seconds >= 0



def test_model_mismatch_blocks_before_request(tmp_path: Path) -> None:
    _build_corpus(tmp_path)
    index_path, _ = _build_index(tmp_path)
    client = _FakeEmbeddingsClient(model="text-embedding-3-small")
    settings = OpenAIEmbeddingSettings(api_key="test-key", model="another-model")

    with pytest.raises(RetrievalConfigurationError):
        retrieve_rag_context(
            repo_root=tmp_path,
            index_path=index_path,
            channel="instagram",
            campaign_brief="Lead with packability.",
            settings=settings,
            client=client,
        )

    assert client.embeddings.calls == []



def test_sources_changing_during_retrieval_invalidate_the_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _build_corpus(tmp_path)
    index_path, _ = _build_index(tmp_path)
    client = _FakeEmbeddingsClient(model="text-embedding-3-small")
    settings = OpenAIEmbeddingSettings(api_key="test-key", model="text-embedding-3-small")

    first_call = True

    def _changing_documents(repo_root=None):
        nonlocal first_call
        if first_call:
            first_call = False
            return load_knowledge_base_documents(repo_root)
        _write_document(
            tmp_path / "knowledge_base" / "primary" / "alpha.md",
            title="Alpha",
            source_url=PRIMARY_URL,
            knowledge_base="primary",
            facts="Primary alpha fact changed during retrieval.",
            editorial="Primary editorial interpretation remains separate.",
            limitations="- Primary limitations stay attached to each chunk.",
            publisher="Patagonia, US website",
        )
        return load_knowledge_base_documents(repo_root)

    monkeypatch.setattr("src.rag_retrieval.load_knowledge_base_documents", _changing_documents)

    with pytest.raises(RetrievalStaleCorpusError):
        retrieve_rag_context(
            repo_root=tmp_path,
            index_path=index_path,
            channel="instagram",
            campaign_brief="Lead with packability.",
            settings=settings,
            client=client,
        )

    assert len(client.embeddings.calls) == 1



def _load_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "retrieve_rag_context.py"
    spec = importlib.util.spec_from_file_location("retrieve_rag_context_script", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module



def test_cli_defaults_to_dry_run_and_switches_to_live(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module()
    calls: list[str] = []

    def _plan(**kwargs):
        calls.append("plan")
        return SimpleNamespace(
            repo_root=Path("/tmp/repo"),
            index_path=Path("/tmp/repo/.rag/rag_index.sqlite3"),
            query_digest="digest",
            query_character_count=12,
            embedding_model_id=None,
            corpus_snapshot=SimpleNamespace(snapshot_id="snapshot"),
            existing_index_path=None,
            existing_index_matches=None,
            existing_index_reason="missing",
            primary_top_k=3,
            secondary_top_k=3,
            primary_minimum_similarity=0.18,
            secondary_minimum_similarity=0.12,
            max_context_characters=6000,
        )

    def _live(**kwargs):
        calls.append("live")
        return SimpleNamespace(
            repo_root=Path("/tmp/repo"),
            index_path=Path("/tmp/repo/.rag/rag_index.sqlite3"),
            query_digest="digest",
            query_character_count=12,
            corpus_snapshot=SimpleNamespace(snapshot_id="snapshot"),
            embedding_model_id="text-embedding-3-small",
            query_usage=None,
            query_elapsed_seconds=0.1,
            primary_results=(),
            secondary_results=(),
            blocked_reason=None,
            context_bundle=None,
            manifest=SimpleNamespace(
                included_sources=(),
                omission_reasons=(),
                requested_model_id="text-embedding-3-small",
                returned_model_id="text-embedding-3-small",
                corpus_snapshot_id="snapshot",
                embedding_model_id="text-embedding-3-small",
                query_digest="digest",
                query_character_count=12,
                query_usage=None,
                query_elapsed_seconds=0.1,
            ),
        )

    monkeypatch.setattr(module, "plan_rag_context_retrieval", _plan)
    monkeypatch.setattr(module, "retrieve_rag_context", _live)

    assert module.main(["--channel", "instagram", "--brief", "Lead with packability."]) == 0
    assert module.main(["--live", "--channel", "instagram", "--brief", "Lead with packability."]) == 0
    assert calls == ["plan", "live"]






def test_render_rag_retrieval_result_reports_compact_audit_details(tmp_path: Path) -> None:
    _build_corpus(tmp_path)
    index_path, _ = _build_index(tmp_path)
    client = _FakeEmbeddingsClient(model="text-embedding-3-small")
    settings = OpenAIEmbeddingSettings(api_key="test-key", model="text-embedding-3-small")

    result = retrieve_rag_context(
        repo_root=tmp_path,
        index_path=index_path,
        channel="instagram",
        campaign_brief="Lead with packability.",
        settings=settings,
        client=client,
        primary_top_k=3,
        secondary_top_k=3,
        primary_minimum_similarity=0.0,
        secondary_minimum_similarity=0.0,
    )

    output = render_rag_retrieval_result(result)

    assert "Requested embedding model: text-embedding-3-small" in output
    assert "Returned embedding model: text-embedding-3-small" in output
    assert "Query usage: prompt_tokens=" in output
    assert f"Primary selected chunks: {result.context_bundle.retrieval_measurements.primary_selected_count}" in output
    assert f"Secondary selected chunks: {result.context_bundle.retrieval_measurements.secondary_selected_count}" in output
    assert f"Distinct sources: {result.context_bundle.retrieval_measurements.included_source_count}" in output
    assert (
        f"Serialized context characters: {result.context_bundle.retrieval_measurements.serialized_context_characters} / "
        f"{result.context_bundle.retrieval_measurements.max_serialized_characters}"
    ) in output
    assert "Included chunks:" in output
    assert result.manifest.included_sources[0].repository_relative_path in output
    assert result.manifest.included_sources[0].chunk_ids[0] in output
    assert "score=" in output



def test_live_retrieval_can_save_evidence_with_context_parity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _build_corpus(tmp_path)
    index_path, _ = _build_index(tmp_path)
    client = _FakeEmbeddingsClient(model="text-embedding-3-small")
    settings = OpenAIEmbeddingSettings(api_key="test-key", model="text-embedding-3-small")

    result = retrieve_rag_context(
        repo_root=tmp_path,
        index_path=index_path,
        channel="instagram",
        campaign_brief="Lead with packability.",
        settings=settings,
        client=client,
        primary_top_k=3,
        secondary_top_k=3,
        primary_minimum_similarity=0.0,
        secondary_minimum_similarity=0.0,
    )

    module = _load_script_module()
    monkeypatch.setattr(module, "retrieve_rag_context", lambda **kwargs: result)
    evidence_path = tmp_path / "evidence" / "retrieval.json"

    assert module.main([
        "--live",
        "--channel",
        "instagram",
        "--brief",
        "Lead with packability.",
        "--save-evidence",
        str(evidence_path),
    ]) == 0

    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert payload["retrieval_status"] == "success"
    assert payload["query"]["text"] == result.query_text
    assert payload["query"]["digest"] == result.query_digest
    assert payload["manifest"]["corpus_snapshot_id"] == result.manifest.corpus_snapshot_id
    assert payload["manifest"]["query_usage"]["prompt_tokens"] == result.manifest.query_usage.prompt_tokens
    assert payload["measurements"]["serialized_context_characters"] == result.context_bundle.retrieval_measurements.serialized_context_characters
    assert payload["measurements"]["max_serialized_characters"] == result.context_bundle.retrieval_measurements.max_serialized_characters
    assert payload["retrieved_context"]["primary"] == result.context_bundle.primary_context
    assert payload["retrieved_context"]["secondary"] == result.context_bundle.secondary_context
    assert payload["source_manifest"] == payload["manifest"]["included_sources"]
    assert payload["included_chunks"]
    assert payload["included_chunks"][0]["chunk_text"]
    assert payload["included_chunks"][0]["applicable_limitations"]
    assert payload["ranked_candidates"]["primary"]
    assert payload["ranked_candidates"]["secondary"]



def test_save_evidence_rejects_existing_destination_before_live_retrieval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_script_module()
    existing_path = tmp_path / "existing.json"
    existing_path.write_text("{}", encoding="utf-8")

    def _unexpected(**kwargs):
        raise AssertionError("live retrieval should not be called when evidence destination already exists")

    monkeypatch.setattr(module, "retrieve_rag_context", _unexpected)

    assert (
        module.main([
            "--live",
            "--channel",
            "instagram",
            "--brief",
            "Lead with packability.",
            "--save-evidence",
            str(existing_path),
        ])
        == 1
    )



def test_blocked_retrieval_evidence_records_blocked_status(tmp_path: Path) -> None:
    _build_corpus(tmp_path)
    index_path, _ = _build_index(tmp_path, primary_fact=(0.0, 1.0), primary_editorial=(0.0, 1.0), secondary=(1.0, 0.0))
    client = _FakeEmbeddingsClient(model="text-embedding-3-small")
    settings = OpenAIEmbeddingSettings(api_key="test-key", model="text-embedding-3-small")

    result = retrieve_rag_context(
        repo_root=tmp_path,
        index_path=index_path,
        channel="instagram",
        campaign_brief="Lead with packability.",
        settings=settings,
        client=client,
        primary_minimum_similarity=0.5,
        secondary_minimum_similarity=0.5,
    )

    assert result.blocked_reason is not None
    module = _load_script_module()
    evidence_path = tmp_path / "blocked" / "retrieval.json"
    module._save_rag_retrieval_evidence(
        evidence_path,
        result,
        channel="instagram",
        retrieval_settings={
            "primary_top_k": 3,
            "secondary_top_k": 3,
            "primary_minimum_similarity": 0.5,
            "secondary_minimum_similarity": 0.5,
            "max_context_characters": 6000,
            "timeout_seconds": 30.0,
        },
    )

    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert payload["retrieval_status"] == "blocked"
    assert payload["blocked_reason"] == result.blocked_reason
    assert payload["included_chunks"] == []
    assert payload["retrieved_context"]["primary"] == ""
    assert payload["retrieved_context"]["secondary"] == ""
    assert payload["measurements"]["primary_selected_count"] == 0
    assert payload["measurements"]["secondary_selected_count"] == 0
    assert payload["measurements"]["serialized_context_characters"] == 0
