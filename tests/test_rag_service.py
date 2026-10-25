from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import json
import sqlite3

import pytest

from src.document_processor import load_knowledge_base_documents
from src.embedding_integration import OpenAIEmbeddingRequestError, OpenAIEmbeddingSettings
from src.rag_index import IndexBuildError, open_vector_index
from src.rag_chunking import ChunkingPolicy
from src.rag_service import (
    bootstrap_rag_index_from_seed,
    build_rag_index,
    package_rag_index_seed,
    plan_embedding_batches,
    plan_rag_index_build,
    render_rag_build_plan,
    resolve_runtime_index_path,
)

PRIMARY_URL = "https://www.patagonia.com/product/mens-nano-puff-insulated-jacket/84212.html"
SECONDARY_URL = "https://example.com/outdoor-context"


@dataclass(frozen=True)
class _FakeEmbeddingItem:
    index: int
    embedding: list[float]


class _FakeEmbeddingsService:
    def __init__(self, *, model: str, fail_on_call: int | None = None) -> None:
        self.model = model
        self.fail_on_call = fail_on_call
        self.calls: list[dict[str, object]] = []
        self.call_count = 0

    def create(self, **kwargs):
        if self.fail_on_call is not None and self.call_count >= self.fail_on_call:
            raise RuntimeError("simulated embedding failure")
        self.calls.append(kwargs)
        inputs = list(kwargs["input"])
        self.call_count += 1
        data = [
            _FakeEmbeddingItem(index=index, embedding=[float(self.call_count), float(index + 1)])
            for index in range(len(inputs))
        ]
        usage = SimpleNamespace(prompt_tokens=sum(len(text) for text in inputs), total_tokens=sum(len(text) for text in inputs) + 1)
        return SimpleNamespace(model=self.model, data=data, usage=usage)


class _FakeEmbeddingsClient:
    def __init__(self, *, model: str, fail_on_call: int | None = None) -> None:
        self.embeddings = _FakeEmbeddingsService(model=model, fail_on_call=fail_on_call)



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



def _build_corpus(root: Path, *, primary_fact: str = "Primary fact.", secondary_fact: str = "Secondary fact.") -> None:
    _write_document(
        root / "knowledge_base" / "primary" / "alpha.md",
        title="Alpha",
        source_url=PRIMARY_URL,
        knowledge_base="primary",
        facts=primary_fact,
        editorial="Primary editorial context.",
        limitations="- Primary limitations stay attached to each chunk.",
        publisher="Patagonia, US website",
    )
    _write_document(
        root / "knowledge_base" / "secondary" / "beta.md",
        title="Beta",
        source_url=SECONDARY_URL,
        knowledge_base="secondary",
        facts=secondary_fact,
        editorial="Secondary editorial context.",
        limitations="- Secondary limitations stay attached to each chunk.",
        publisher="Example Publisher",
    )



def test_plan_embedding_batches_respects_exact_limits() -> None:
    plans = plan_embedding_batches(
        [("a", "aaaa"), ("b", "bbbb"), ("c", "cc")],
        max_batch_size=2,
        max_input_characters=4,
        max_total_characters=8,
    )

    assert len(plans) == 2
    assert plans[0].chunk_ids == ("a", "b")
    assert plans[0].total_input_characters == 8
    assert plans[1].chunk_ids == ("c",)
    assert plans[1].total_input_characters == 2



def test_dry_run_reports_counts_batches_and_path_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _build_corpus(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_EMBEDDING_MODEL", raising=False)
    monkeypatch.setattr("src.rag_service.load_embedding_settings", lambda *_args, **_kwargs: pytest.fail("dry-run should not load credentials"))
    monkeypatch.setattr("src.rag_service.embed_texts", lambda *_args, **_kwargs: pytest.fail("dry-run should not create requests"))

    plan = plan_rag_index_build(
        repo_root=tmp_path,
        index_path=Path("runtime/rag.sqlite3"),
        embedding_model_id="offline-model",
    )

    assert plan.index_path == (tmp_path / "runtime" / "rag.sqlite3").resolve()
    assert plan.chunk_count == 6
    assert plan.chunk_counts_by_knowledge_base == (("primary", 3), ("secondary", 3))
    assert plan.pending_embedding_count == 6
    assert plan.reusable_embedding_count == 0
    assert len(plan.planned_batches) == 1
    assert plan.existing_index_matches is False
    assert "primary=3" in render_rag_build_plan(plan)
    assert not plan.index_path.exists()



def test_build_reuses_embeddings_when_corpus_is_unchanged(tmp_path: Path) -> None:
    _build_corpus(tmp_path)
    settings = OpenAIEmbeddingSettings(api_key="test-key", model="offline-model")
    client = _FakeEmbeddingsClient(model="offline-model")
    index_path = tmp_path / ".rag" / "rag_index.sqlite3"

    initial = build_rag_index(
        repo_root=tmp_path,
        index_path=index_path,
        settings=settings,
        client=client,
    )
    assert initial.embedded_chunk_count == 6
    assert len(client.embeddings.calls) == 1

    reuse_client = _FakeEmbeddingsClient(model="offline-model")
    reused = build_rag_index(
        repo_root=tmp_path,
        index_path=index_path,
        settings=settings,
        client=reuse_client,
    )

    assert reused.reused_embedding_count == 6
    assert reused.embedded_chunk_count == 0
    assert len(reuse_client.embeddings.calls) == 0
    assert open_vector_index(index_path).chunk_count == 6
    assert reused.manifest_path.exists()
    assert reused.completed_batches == tuple()



def test_build_reembeds_only_changed_document_and_excludes_deleted_chunks(tmp_path: Path) -> None:
    _build_corpus(tmp_path)
    settings = OpenAIEmbeddingSettings(api_key="test-key", model="offline-model")
    index_path = tmp_path / ".rag" / "rag_index.sqlite3"
    initial_client = _FakeEmbeddingsClient(model="offline-model")
    build_rag_index(repo_root=tmp_path, index_path=index_path, settings=settings, client=initial_client)

    _write_document(
        tmp_path / "knowledge_base" / "primary" / "alpha.md",
        title="Alpha",
        source_url=PRIMARY_URL,
        knowledge_base="primary",
        facts="Primary fact changed.",
        editorial="Primary editorial context.",
        limitations="- Primary limitations stay attached to each chunk.",
        publisher="Patagonia, US website",
    )
    edit_client = _FakeEmbeddingsClient(model="offline-model")
    edit_result = build_rag_index(repo_root=tmp_path, index_path=index_path, settings=settings, client=edit_client)

    assert edit_result.embedded_chunk_count == 3
    assert edit_result.reused_embedding_count == 3
    assert len(edit_client.embeddings.calls) == 1
    assert open_vector_index(index_path).chunk_count == 6

    (tmp_path / "knowledge_base" / "secondary" / "beta.md").unlink()
    delete_client = _FakeEmbeddingsClient(model="offline-model")
    delete_result = build_rag_index(repo_root=tmp_path, index_path=index_path, settings=settings, client=delete_client)

    assert delete_result.embedded_chunk_count == 0
    assert delete_result.reused_embedding_count == 3
    assert len(delete_client.embeddings.calls) == 0
    assert open_vector_index(index_path).chunk_count == 3



def test_plan_reports_model_and_policy_mismatch(tmp_path: Path) -> None:
    _build_corpus(tmp_path)
    settings = OpenAIEmbeddingSettings(api_key="test-key", model="offline-model")
    index_path = tmp_path / ".rag" / "rag_index.sqlite3"
    client = _FakeEmbeddingsClient(model="offline-model")
    build_rag_index(repo_root=tmp_path, index_path=index_path, settings=settings, client=client)

    model_plan = plan_rag_index_build(
        repo_root=tmp_path,
        index_path=index_path,
        embedding_model_id="different-model",
    )
    policy_plan = plan_rag_index_build(
        repo_root=tmp_path,
        index_path=index_path,
        embedding_model_id="offline-model",
        chunking_policy=ChunkingPolicy(max_chunk_characters=150),
    )

    assert model_plan.existing_index_matches is False
    assert model_plan.existing_index_reason == "model_mismatch"
    assert policy_plan.existing_index_matches is False
    assert policy_plan.existing_index_reason == "policy_mismatch"



def test_batch_failure_and_corpus_change_preserve_previous_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _build_corpus(tmp_path)
    settings = OpenAIEmbeddingSettings(api_key="test-key", model="offline-model")
    index_path = tmp_path / ".rag" / "rag_index.sqlite3"
    client = _FakeEmbeddingsClient(model="offline-model")
    build_rag_index(
        repo_root=tmp_path,
        index_path=index_path,
        settings=settings,
        client=client,
        max_batch_size=1,
    )

    failing_settings = OpenAIEmbeddingSettings(api_key="test-key", model="offline-model-v2")
    failing_client = _FakeEmbeddingsClient(model="offline-model-v2", fail_on_call=1)
    with pytest.raises(OpenAIEmbeddingRequestError, match="OpenAI embedding request failed"):
        build_rag_index(
            repo_root=tmp_path,
            index_path=index_path,
            settings=failing_settings,
            client=failing_client,
            max_batch_size=1,
        )
    assert open_vector_index(index_path).chunk_count == 6

    first_call = True

    def _fake_documents(repo_root=None):
        nonlocal first_call
        if first_call:
            first_call = False
            return load_knowledge_base_documents(repo_root)
        _write_document(
            tmp_path / "knowledge_base" / "primary" / "alpha.md",
            title="Alpha",
            source_url=PRIMARY_URL,
            knowledge_base="primary",
            facts="Primary fact changed again.",
            editorial="Primary editorial context.",
            limitations="- Primary limitations stay attached to each chunk.",
            publisher="Patagonia, US website",
        )
        return load_knowledge_base_documents(repo_root)

    monkeypatch.setattr("src.rag_service.load_knowledge_base_documents", _fake_documents)
    with pytest.raises(IndexBuildError, match="Corpus changed during index build"):
        build_rag_index(repo_root=tmp_path, index_path=index_path, settings=settings, client=_FakeEmbeddingsClient(model="offline-model"))
    assert open_vector_index(index_path).chunk_count == 6



def test_dry_run_does_not_load_credentials_or_write_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _build_corpus(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_EMBEDDING_MODEL", raising=False)
    monkeypatch.setattr("src.rag_service.load_embedding_settings", lambda *_args, **_kwargs: pytest.fail("dry-run should not load credentials"))
    monkeypatch.setattr("src.rag_service.embed_texts", lambda *_args, **_kwargs: pytest.fail("dry-run should not create requests"))

    plan = plan_rag_index_build(repo_root=tmp_path, index_path=tmp_path / "nested" / "rag.sqlite3")

    assert plan.embedding_model_id is None
    assert not plan.index_path.exists()
    assert not resolve_runtime_index_path(tmp_path, "nested/rag.sqlite3").exists()



def test_manifest_and_usage_match_performed_calls(tmp_path: Path) -> None:
    _build_corpus(tmp_path)
    settings = OpenAIEmbeddingSettings(api_key="test-key", model="offline-model")
    index_path = tmp_path / ".rag" / "rag_index.sqlite3"
    client = _FakeEmbeddingsClient(model="offline-model")

    result = build_rag_index(repo_root=tmp_path, index_path=index_path, settings=settings, client=client, max_batch_size=1)

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["embedded_chunk_count"] == 6
    assert manifest["reused_embedding_count"] == 0
    assert len(result.completed_batches) == 6
    assert sum(batch.usage.prompt_tokens for batch in result.completed_batches if batch.usage is not None) > 0
    assert result.completed_batches[0].requested_model == "offline-model"
    assert result.completed_batches[0].returned_model == "offline-model"


@pytest.fixture
def seed_setup(tmp_path: Path, monkeypatch):
    from src import rag_service
    _build_corpus(tmp_path)
    index_path = tmp_path / ".rag" / "rag_index.sqlite3"
    build_rag_index(
        repo_root=tmp_path, index_path=index_path,
        settings=OpenAIEmbeddingSettings(api_key="test-key", model="offline-model"),
        client=_FakeEmbeddingsClient(model="offline-model"),
    )
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "offline-model")
    monkeypatch.setenv("RAG_INDEX_VECTOR_DIMENSIONS", "2")
    monkeypatch.setattr(rag_service, "embed_texts", lambda *a, **k: pytest.fail("bootstrap called embeddings"))
    monkeypatch.setattr(rag_service, "load_embedding_settings", lambda *a, **k: pytest.fail("bootstrap loaded credentials"))
    return tmp_path, index_path, tmp_path / "deploy" / "seed.sqlite3"


def test_seed_package_restore_and_existing_reuse(seed_setup):
    root, runtime, seed = seed_setup
    original = runtime.read_bytes()
    package = package_rag_index_seed(repo_root=root, seed_path=seed)
    assert runtime.read_bytes() == original
    runtime.unlink()
    restored = bootstrap_rag_index_from_seed(repo_root=root, seed_path=seed)
    assert restored.restored
    assert open_vector_index(runtime).records == open_vector_index(seed).records
    assert restored.corpus_snapshot == package.corpus_snapshot
    restored_bytes = runtime.read_bytes()
    seed.unlink()
    assert not bootstrap_rag_index_from_seed(repo_root=root, seed_path=seed).restored
    assert runtime.read_bytes() == restored_bytes


@pytest.mark.parametrize("damage", ["stale", "corrupt", "model", "dimensions", "version", "extra_table", "extra_metadata", "missing_vector"])
def test_seed_rejection_preserves_runtime(seed_setup, damage):
    from src.rag_service import RagServiceError
    root, runtime, seed = seed_setup
    package_rag_index_seed(repo_root=root, seed_path=seed)
    if damage == "corrupt":
        seed.write_bytes(b"not sqlite")
    else:
        with sqlite3.connect(seed) as con:
            if damage in {"stale", "model", "dimensions", "version"}:
                key, value = {
                    "stale": ("corpus_snapshot_id", "old"),
                    "model": ("embedding_model_id", "wrong-model"),
                    "dimensions": ("vector_dimensions", "3"),
                    "version": ("index_version", "future-version"),
                }[damage]
                con.execute("UPDATE metadata SET value=? WHERE key=?", (value, key))
            elif damage == "extra_table":
                con.execute("CREATE TABLE private_payload (value TEXT)")
            elif damage == "extra_metadata":
                con.execute("INSERT INTO metadata VALUES ('unexpected', 'private-data')")
            else:
                con.execute("DELETE FROM vectors WHERE chunk_id=(SELECT chunk_id FROM vectors LIMIT 1)")
    runtime.write_bytes(b"previous unavailable runtime snapshot")
    before = runtime.read_bytes()
    with pytest.raises(RagServiceError):
        bootstrap_rag_index_from_seed(repo_root=root, seed_path=seed)
    assert runtime.read_bytes() == before


def test_atomic_failure_and_sanitized_error(seed_setup, monkeypatch):
    from src import rag_service
    root, runtime, seed = seed_setup
    package_rag_index_seed(repo_root=root, seed_path=seed)
    runtime.write_bytes(b"old runtime")
    before_paths = set(runtime.parent.iterdir())
    original_replace = rag_service.os.replace
    def fail_activation(source, dest):
        if Path(dest) == runtime:
            raise OSError("sensitive diagnostic must not escape")
        return original_replace(source, dest)
    monkeypatch.setattr(rag_service.os, "replace", fail_activation)
    with pytest.raises(rag_service.RagServiceError) as error:
        bootstrap_rag_index_from_seed(repo_root=root, seed_path=seed)
    assert "sensitive" not in str(error.value)
    assert runtime.read_bytes() == b"old runtime"
    assert set(runtime.parent.iterdir()) == before_paths


def test_packaging_refuses_overwrite_or_runtime_destination(seed_setup):
    from src.rag_service import RagServiceError
    root, runtime, seed = seed_setup
    package_rag_index_seed(repo_root=root, seed_path=seed)
    before = seed.read_bytes()
    with pytest.raises(RagServiceError):
        package_rag_index_seed(repo_root=root, seed_path=seed)
    assert seed.read_bytes() == before
    with pytest.raises(RagServiceError):
        package_rag_index_seed(repo_root=root, seed_path=runtime)


def test_seed_corpus_changes_before_activation_preserve_runtime(seed_setup, monkeypatch):
    from src import rag_service
    root, runtime, seed = seed_setup
    package_rag_index_seed(repo_root=root, seed_path=seed)
    runtime.write_bytes(b"old runtime")
    original_validate = rag_service._validate_seed_index
    def change_corpus(path, repo, model, dimensions):
        index = original_validate(path, repo, model, dimensions)
        if path == seed:
            doc = root / "knowledge_base" / "primary" / "alpha.md"
            doc.write_text(doc.read_text(encoding="utf-8") + "\nCorpus changed.\n", encoding="utf-8")
        return index
    monkeypatch.setattr(rag_service, "_validate_seed_index", change_corpus)
    with pytest.raises(rag_service.RagServiceError):
        bootstrap_rag_index_from_seed(repo_root=root, seed_path=seed)
    assert runtime.read_bytes() == b"old runtime"


def test_seed_packaging_cli_is_offline(seed_setup, monkeypatch, capsys):
    from scripts import package_rag_index_seed as cli
    root, runtime, seed = seed_setup
    monkeypatch.setattr(cli, "REPO_ROOT", root)
    assert cli.main(["--seed-path", str(seed), "--embedding-model", "offline-model", "--vector-dimensions", "2"]) == 0
    assert "Chunk count:" in capsys.readouterr().out
    assert cli.main(["--seed-path", str(seed)]) == 1


def test_seed_restores_in_another_checkout(seed_setup, tmp_path):
    import shutil
    root, runtime, seed = seed_setup
    package_rag_index_seed(repo_root=root, seed_path=seed)
    other = tmp_path / "fresh-checkout"
    shutil.copytree(root / "knowledge_base", other / "knowledge_base")
    other_seed = other / "deploy" / "seed.sqlite3"
    other_seed.parent.mkdir()
    shutil.copyfile(seed, other_seed)
    result = bootstrap_rag_index_from_seed(repo_root=other, seed_path="deploy/seed.sqlite3")
    assert result.restored
    assert result.runtime_index_path == other / ".rag" / "rag_index.sqlite3"
    assert open_vector_index(result.runtime_index_path).records == open_vector_index(runtime).records
