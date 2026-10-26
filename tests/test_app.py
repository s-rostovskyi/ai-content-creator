from pathlib import Path
from types import SimpleNamespace
import gc
from contextlib import nullcontext
import shutil
import sys
import tempfile

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

streamlit = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

import src.campaign_brief as campaign_brief
import src.content_pipeline as pipeline
import src.knowledge_base as knowledge_base
import src.source_registry as source_registry
import src.ui_state as ui_state
import src.rag_context_provider as rag_context_provider
import src.rag_service as rag_service

BRIEF = ui_state.DEFAULT_BRIEF
DEFAULT_TEST_CHANNEL = "instagram"
PRIMARY_URL = "https://example.com/primary"
SECONDARY_URL = "https://example.com/secondary"

@pytest.fixture(autouse=True)
def _default_source_management_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_MANAGEMENT_ENABLED", "false")
    monkeypatch.delenv("RAG_INDEX_BUILD_ENABLED", raising=False)


@pytest.fixture(autouse=True)
def _default_rag_index_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_describe_status(self, *, channel: str, campaign_brief: str, revision_feedback: str = ""):
        del revision_feedback
        return rag_context_provider.RagIndexStatus(
            state="ready",
            message="RAG index ready.",
            details=f"Index available for {channel}.",
            index_path=REPO_ROOT / ".rag" / "rag_index.sqlite3",
            corpus_snapshot_id="test-snapshot",
            existing_index_matches=True,
            existing_index_reason="ready",
            embedding_model_id="text-embedding-3-small",
        )

    monkeypatch.setattr(rag_context_provider.LiveRagContextProvider, "describe_status", fake_describe_status)


def _on_page(at: AppTest, section: str) -> AppTest:
    """Navigate through the visible selector before using that page's controls."""
    if at.radio(key="studio_section_widget").value != section:
        at.radio(key="studio_section_widget").set_value(section).run()
        assert not at.exception
    return at


def _editor_copy_key(channel: str = DEFAULT_TEST_CHANNEL) -> str:
    return ui_state.editor_copy_key(channel)


def _editor_notes_key(channel: str = DEFAULT_TEST_CHANNEL) -> str:
    return ui_state.editor_notes_key(channel)


def _revision_feedback_key(channel: str = DEFAULT_TEST_CHANNEL) -> str:
    return ui_state.revision_feedback_key(channel)


def _export_record_key(channel: str = DEFAULT_TEST_CHANNEL) -> str:
    return ui_state.export_record_key(channel)


def _approval_confirm_key(channel: str = DEFAULT_TEST_CHANNEL, revision: int = 1) -> str:
    return ui_state.approval_confirm_key(channel, revision)


def _workspace_view_key(channel: str = DEFAULT_TEST_CHANNEL) -> str:
    return ui_state.workspace_view_key(channel)


def _workspace_view_widget_key(channel: str = DEFAULT_TEST_CHANNEL) -> str:
    return ui_state.workspace_view_widget_key(channel)


def _active_channel(at: AppTest) -> str:
    session = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    return session.channel


def _words(count: int) -> str:
    return " ".join(f"w{index}" for index in range(1, count + 1))


def _instagram_copy(word_count: int) -> str:
    return _words(word_count)


def _prepare_temp_repo(monkeypatch, tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    shutil.copytree(REPO_ROOT / "knowledge_base", repo_root / "knowledge_base")

    original_list_sources = source_registry.list_sources
    original_read_source = source_registry.read_source
    original_prepare_create_source = source_registry.prepare_create_source
    original_prepare_edit_source = source_registry.prepare_edit_source
    original_prepare_delete_source = source_registry.prepare_delete_source
    original_apply_prepared_source_operation = source_registry.apply_prepared_source_operation
    original_load_campaign_brief_snapshot = campaign_brief.load_campaign_brief_snapshot
    original_assemble_context_bundle = knowledge_base.assemble_context_bundle

    monkeypatch.setattr(source_registry, "list_sources", lambda repo_root_arg=None: original_list_sources(repo_root))
    monkeypatch.setattr(source_registry, "read_source", lambda source_id, repo_root_arg=None: original_read_source(source_id, repo_root))
    monkeypatch.setattr(
        source_registry,
        "prepare_create_source",
        lambda source_id, markdown_text, repo_root_arg=None: original_prepare_create_source(source_id, markdown_text, repo_root),
    )
    monkeypatch.setattr(
        source_registry,
        "prepare_edit_source",
        lambda source_id, markdown_text, expected_source_hash, repo_root_arg=None: original_prepare_edit_source(
            source_id, markdown_text, expected_source_hash, repo_root
        ),
    )
    monkeypatch.setattr(
        source_registry,
        "prepare_delete_source",
        lambda source_id, expected_source_hash, repo_root_arg=None: original_prepare_delete_source(
            source_id, expected_source_hash, repo_root
        ),
    )
    monkeypatch.setattr(
        source_registry,
        "apply_prepared_source_operation",
        lambda prepared_operation, repo_root_arg=None: original_apply_prepared_source_operation(prepared_operation, repo_root),
    )
    monkeypatch.setattr(
        campaign_brief,
        "load_campaign_brief_snapshot",
        lambda repo_root_arg=None: original_load_campaign_brief_snapshot(repo_root),
    )
    monkeypatch.setattr(
        knowledge_base,
        "assemble_context_bundle",
        lambda repo_root_arg=None, max_serialized_characters=40000: original_assemble_context_bundle(
            repo_root, max_serialized_characters=max_serialized_characters
        ),
    )
    return repo_root


def _make_app_test(monkeypatch, tmp_path: Path, *, enable_source_management: bool = False) -> tuple[AppTest, Path]:
    repo_root = _prepare_temp_repo(monkeypatch, tmp_path)
    if enable_source_management:
        monkeypatch.setenv("SOURCE_MANAGEMENT_ENABLED", "true")
    else:
        monkeypatch.setenv("SOURCE_MANAGEMENT_ENABLED", "false")
    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    return at, repo_root


def _patch_fake_generation(monkeypatch) -> None:
    def fake_generate(session, **kwargs):
        draft = _fake_channel_draft(session.channel)
        session.current_draft = draft
        session.history = [draft]
        return draft

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)


def _fake_draft(revision_number: int = 1, channel: str = DEFAULT_TEST_CHANNEL):
    return SimpleNamespace(
        channel=channel,
        revision_number=revision_number,
        channel_copy=f"Generated copy v{revision_number}",
        reviewer_notes=f"Generated notes v{revision_number}",
        source_manifest=(),
        response_metadata=None,
        raw_response=f"raw response v{revision_number}",
    )


def _run_loaded_campaign(at: AppTest) -> None:
    at.button(key="load_campaign_button").click().run()


def _run_generation(at: AppTest) -> None:
    _on_page(at, "Campaign").button(key="generate_button").click().run()


def _prepare_brief(at: AppTest) -> None:
    at.button(key="prepare_brief_button").click().run()


def _use_prepared_brief(at: AppTest) -> None:
    at.button(key="use_prepared_brief_button").click().run()


def _load_campaign(at: AppTest, *, channel: str | None = None, brief: str | None = None) -> None:
    _on_page(at, "Campaign")
    if channel is not None:
        at.selectbox(key=ui_state.CAMPAIGN_CHANNEL_INPUT_KEY).set_value(channel)
    if brief is not None:
        at.text_area(key=ui_state.CAMPAIGN_BRIEF_INPUT_KEY).set_value(brief)
    at.button(key="load_campaign_button").click().run()


def _fake_channel_draft(
    channel: str,
    *,
    revision_number: int = 1,
    copy: str | None = None,
    notes: str | None = None,
    response_id: str | None = None,
):
    return SimpleNamespace(
        channel=channel,
        revision_number=revision_number,
        channel_copy=copy or f"{ui_state.channel_display_name(channel)} copy v{revision_number}",
        reviewer_notes=notes or f"{ui_state.channel_display_name(channel)} notes v{revision_number}",
        source_manifest=(),
        response_metadata=SimpleNamespace(
            response_id=response_id or f"resp-{channel}-v{revision_number}",
            model=f"model-{channel}",
            elapsed_seconds=1.25 * revision_number,
            usage=None,
        ),
        raw_response=f"raw {channel} v{revision_number}",
    )



def _words(count: int) -> str:
    return " ".join(f"w{index}" for index in range(1, count + 1))


def _instagram_copy(word_count: int) -> str:
    return _words(word_count)


def _prepare_temp_repo(monkeypatch, tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    shutil.copytree(REPO_ROOT / "knowledge_base", repo_root / "knowledge_base")

    original_list_sources = source_registry.list_sources
    original_read_source = source_registry.read_source
    original_prepare_create_source = source_registry.prepare_create_source
    original_prepare_edit_source = source_registry.prepare_edit_source
    original_prepare_delete_source = source_registry.prepare_delete_source
    original_apply_prepared_source_operation = source_registry.apply_prepared_source_operation
    original_load_campaign_brief_snapshot = campaign_brief.load_campaign_brief_snapshot
    original_assemble_context_bundle = knowledge_base.assemble_context_bundle

    monkeypatch.setattr(source_registry, "list_sources", lambda repo_root_arg=None: original_list_sources(repo_root))
    monkeypatch.setattr(source_registry, "read_source", lambda source_id, repo_root_arg=None: original_read_source(source_id, repo_root))
    monkeypatch.setattr(
        source_registry,
        "prepare_create_source",
        lambda source_id, markdown_text, repo_root_arg=None: original_prepare_create_source(source_id, markdown_text, repo_root),
    )
    monkeypatch.setattr(
        source_registry,
        "prepare_edit_source",
        lambda source_id, markdown_text, expected_source_hash, repo_root_arg=None: original_prepare_edit_source(
            source_id, markdown_text, expected_source_hash, repo_root
        ),
    )
    monkeypatch.setattr(
        source_registry,
        "prepare_delete_source",
        lambda source_id, expected_source_hash, repo_root_arg=None: original_prepare_delete_source(
            source_id, expected_source_hash, repo_root
        ),
    )
    monkeypatch.setattr(
        source_registry,
        "apply_prepared_source_operation",
        lambda prepared_operation, repo_root_arg=None: original_apply_prepared_source_operation(prepared_operation, repo_root),
    )
    monkeypatch.setattr(
        campaign_brief,
        "load_campaign_brief_snapshot",
        lambda repo_root_arg=None: original_load_campaign_brief_snapshot(repo_root),
    )
    monkeypatch.setattr(
        knowledge_base,
        "assemble_context_bundle",
        lambda repo_root_arg=None, max_serialized_characters=40000: original_assemble_context_bundle(
            repo_root, max_serialized_characters=max_serialized_characters
        ),
    )
    return repo_root


def _make_app_test(monkeypatch, tmp_path: Path, *, enable_source_management: bool = False) -> tuple[AppTest, Path]:
    repo_root = _prepare_temp_repo(monkeypatch, tmp_path)
    if enable_source_management:
        monkeypatch.setenv("SOURCE_MANAGEMENT_ENABLED", "true")
    else:
        monkeypatch.delenv("SOURCE_MANAGEMENT_ENABLED", raising=False)
    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    return at, repo_root


def _patch_fake_generation(monkeypatch) -> None:
    def fake_generate(session, **kwargs):
        draft = _fake_channel_draft(session.channel)
        session.current_draft = draft
        session.history = [draft]
        return draft

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)





def test_header_image_renders_from_repo_relative_path() -> None:
    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()

    assert any(caption.value == "AI-generated landscape" for caption in at.caption)
    del at
    gc.collect()


def test_header_image_fallback_without_asset(monkeypatch) -> None:
    original_is_file = Path.is_file

    def fake_is_file(self):
        if self.name == "outdoor-header-v1.png":
            return False
        return original_is_file(self)

    monkeypatch.setattr(Path, "is_file", fake_is_file)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()

    assert not any(caption.value == "AI-generated landscape" for caption in at.caption)
    assert at.exception == []
    del at
    gc.collect()

def test_initial_state_does_not_generate_and_keeps_default_channel(monkeypatch) -> None:
    def fail_generation(*args, **kwargs):
        raise AssertionError("generation should not run on initial load")

    monkeypatch.setattr(pipeline, "generate_initial_draft", fail_generation)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()

    assert len(at.selectbox) == 3
    assert at.selectbox(key=ui_state.CAMPAIGN_CHANNEL_INPUT_KEY).value == "instagram"
    assert at.selectbox(key=ui_state.BRIEF_INSIGHT_ANGLE_KEY).value == "packability"
    assert at.text_area(key=ui_state.CAMPAIGN_BRIEF_INPUT_KEY).value == BRIEF
    assert len(at.download_button) == 0
    del at
    gc.collect()


def test_explicit_generation_requires_button_click(monkeypatch) -> None:
    calls = {"generate": 0}

    def fake_generate(session, **kwargs):
        calls["generate"] += 1
        session.paid_attempts_used += 1
        draft = _fake_draft()
        session.current_draft = draft
        session.history = [draft]
        return draft

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()

    _run_loaded_campaign(at)
    _run_generation(at)
    assert any(status.state == "complete" and status.label == "Generating draft completed." for status in at.status)
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Review").run()

    assert calls["generate"] == 1
    assert any("Remaining generation attempts: 2 of 3" in caption.value for caption in at.caption)
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Edit").run()
    assert _on_page(at, "Campaign").text_area(key=_editor_copy_key()).value == "Generated copy v1"
    assert _on_page(at, "Campaign").text_area(key=_editor_notes_key()).value == "Generated notes v1"
    assert len(at.download_button) == 0
    del at
    gc.collect()


def test_revision_updates_remaining_attempts_immediately(monkeypatch) -> None:
    calls = {"generate": 0, "revise": 0}

    def fake_generate(session, **kwargs):
        calls["generate"] += 1
        session.paid_attempts_used += 1
        draft = _fake_draft()
        session.current_draft = draft
        session.history = [draft]
        return draft

    def fake_revise(session, human_feedback, **kwargs):
        calls["revise"] += 1
        session.paid_attempts_used += 1
        draft = _fake_draft(revision_number=2)
        session.current_draft = draft
        session.history.append(draft)
        return draft

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)
    monkeypatch.setattr(pipeline, "revise_current_draft", fake_revise)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    _run_loaded_campaign(at)
    _run_generation(at)
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Review").run()
    at.text_area(key=_revision_feedback_key()).set_value("Please tighten the opening.")
    at.button(key="revise_button").click().run()

    assert calls == {"generate": 1, "revise": 1}
    assert at.session_state[ui_state.PIPELINE_SESSION_KEY].current_draft.revision_number == 2
    assert any("Remaining generation attempts: 1 of 3" in caption.value for caption in at.caption)
    del at
    gc.collect()


def test_revision_failure_preserves_draft_and_attempts(monkeypatch) -> None:
    calls = {"generate": 0, "revise": 0}

    def fake_generate(session, **kwargs):
        calls["generate"] += 1
        session.paid_attempts_used += 1
        draft = _fake_draft()
        session.current_draft = draft
        session.history = [draft]
        return draft

    def fake_revise(session, human_feedback, **kwargs):
        calls["revise"] += 1
        session.paid_attempts_used += 1
        raise pipeline.ContentPipelineError("Could not revise draft.")

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)
    monkeypatch.setattr(pipeline, "revise_current_draft", fake_revise)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    _load_campaign(at)
    _run_generation(at)
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Review").run()
    at.text_area(key=_revision_feedback_key()).set_value("Please tighten the opening.")
    at.button(key="revise_button").click().run()
    assert any(status.state == "error" for status in at.status)

    assert calls == {"generate": 1, "revise": 1}
    session = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert session.current_draft.revision_number == 1
    assert session.approval is None
    assert any("Remaining generation attempts: 1 of 3" in caption.value for caption in at.caption)
    assert any("Context mode: full_corpus" in caption.value for caption in at.caption)
    assert any("Error: Could not revise draft." in error.value for error in at.error)
    assert _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).value == "Review"
    assert at.checkbox(key=_approval_confirm_key(revision=1)).value is False
    del at
    gc.collect()


def test_revision_renders_revised_response_and_keeps_single_request(monkeypatch) -> None:
    calls = {"generate": 0, "revise": 0}

    def fake_generate(session, **kwargs):
        calls["generate"] += 1
        session.paid_attempts_used += 1
        draft = SimpleNamespace(
            channel="instagram",
            revision_number=1,
            channel_copy="Initial copy word count",
            reviewer_notes="Initial notes",
            context_mode="rag",
            source_manifest=(
                SimpleNamespace(
                    repository_relative_path="knowledge_base/primary/initial.md",
                    document_title="Initial facts",
                    knowledge_base="primary",
                    source_urls=(PRIMARY_URL,),
                    source_url_text=PRIMARY_URL,
                    publisher="Patagonia, US website",
                    published_updated="2026-10-23",
                    accessed="2026-10-23",
                    evidence_type="official statement",
                ),
            ),
            retrieval_provenance={
                "corpus_snapshot_id": "snapshot-initial",
                "retrieval_settings": {"primary_top_k": 3, "secondary_top_k": 3, "primary_minimum_similarity": 0.18, "secondary_minimum_similarity": 0.12},
                "manifest": {
                    "corpus_snapshot_id": "snapshot-initial",
                    "requested_model_id": "text-embedding-3-small",
                    "returned_model_id": "text-embedding-3-small",
                    "query_usage": {"prompt_tokens": 9, "total_tokens": 9},
                    "query_elapsed_seconds": 0.111,
                    "included_sources": [
                        {
                            "repository_relative_path": "knowledge_base/primary/initial.md",
                            "knowledge_base": "primary",
                            "document_title": "Initial facts",
                            "source_urls": [PRIMARY_URL],
                            "source_url_text": PRIMARY_URL,
                            "publisher": "Patagonia, US website",
                            "published_updated": "2026-10-23",
                            "accessed": "2026-10-23",
                            "evidence_type": "official statement",
                            "chunk_ids": ["initial-facts-1"],
                            "chunk_scores": [0.91],
                            "chunk_kinds": ["facts"],
                        }
                    ],
                },
                "measurements": {
                    "primary_selected_count": 1,
                    "primary_fact_count": 1,
                    "secondary_selected_count": 0,
                    "secondary_fact_count": 0,
                    "included_source_count": 1,
                    "serialized_context_characters": 96,
                    "max_serialized_characters": 6000,
                },
                "included_chunks": [
                    {
                        "source_path": "knowledge_base/primary/initial.md",
                        "chunk_id": "initial-facts-1",
                        "knowledge_base": "primary",
                        "chunk_kind": "facts",
                        "similarity": 0.91,
                        "section_heading_path": ["Initial facts"],
                        "chunk_line_range": [1, 5],
                        "applicable_limitations": "",
                        "chunk_text": "Initial facts context.",
                    }
                ],
                "ranked_candidates": {"primary": [], "secondary": []},
            },
            response_metadata=SimpleNamespace(
                response_id="resp_initial",
                model="model-initial",
                elapsed_seconds=1.0,
                usage=None,
            ),
            raw_response="raw initial",
        )
        session.current_draft = draft
        session.history = [draft]
        return draft

    def fake_revise(session, human_feedback, **kwargs):
        calls["revise"] += 1
        session.paid_attempts_used += 1
        draft = SimpleNamespace(
            channel="instagram",
            revision_number=2,
            channel_copy="Revised copy with more words",
            reviewer_notes="Revised notes",
            context_mode="rag",
            source_manifest=(
                SimpleNamespace(
                    repository_relative_path="knowledge_base/primary/revised.md",
                    document_title="Revised facts",
                    knowledge_base="primary",
                    source_urls=(SECONDARY_URL,),
                    source_url_text=SECONDARY_URL,
                    publisher="Example Publisher",
                    published_updated="2026-10-23",
                    accessed="2026-10-23",
                    evidence_type="analysis",
                ),
            ),
            retrieval_provenance={
                "corpus_snapshot_id": "snapshot-revised",
                "retrieval_settings": {"primary_top_k": 3, "secondary_top_k": 3, "primary_minimum_similarity": 0.18, "secondary_minimum_similarity": 0.12},
                "manifest": {
                    "corpus_snapshot_id": "snapshot-revised",
                    "requested_model_id": "text-embedding-3-small",
                    "returned_model_id": "text-embedding-3-small",
                    "query_usage": {"prompt_tokens": 11, "total_tokens": 11},
                    "query_elapsed_seconds": 0.222,
                    "included_sources": [
                        {
                            "repository_relative_path": "knowledge_base/primary/revised.md",
                            "knowledge_base": "primary",
                            "document_title": "Revised facts",
                            "source_urls": [SECONDARY_URL],
                            "source_url_text": SECONDARY_URL,
                            "publisher": "Example Publisher",
                            "published_updated": "2026-10-23",
                            "accessed": "2026-10-23",
                            "evidence_type": "analysis",
                            "chunk_ids": ["revised-facts-1"],
                            "chunk_scores": [0.88],
                            "chunk_kinds": ["editorial"],
                        }
                    ],
                },
                "measurements": {
                    "primary_selected_count": 1,
                    "primary_fact_count": 1,
                    "secondary_selected_count": 0,
                    "secondary_fact_count": 0,
                    "included_source_count": 1,
                    "serialized_context_characters": 104,
                    "max_serialized_characters": 6000,
                },
                "included_chunks": [
                    {
                        "source_path": "knowledge_base/primary/revised.md",
                        "chunk_id": "revised-facts-1",
                        "knowledge_base": "primary",
                        "chunk_kind": "editorial",
                        "similarity": 0.88,
                        "section_heading_path": ["Revised facts"],
                        "chunk_line_range": [1, 6],
                        "applicable_limitations": "",
                        "chunk_text": "Revised facts context.",
                    }
                ],
                "ranked_candidates": {"primary": [], "secondary": []},
            },
            response_metadata=SimpleNamespace(
                response_id="resp_revised",
                model="model-revised",
                elapsed_seconds=2.0,
                usage=None,
            ),
            raw_response="raw revised",
        )
        session.current_draft = draft
        session.history.append(draft)
        return draft

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)
    monkeypatch.setattr(pipeline, "revise_current_draft", fake_revise)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    _load_campaign(at)
    _run_generation(at)
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Review").run()
    at.text_area(key=_revision_feedback_key()).set_value("Please revise the opening and keep the verified product details.")
    at.button(key="revise_button").click().run()

    assert calls == {"generate": 1, "revise": 1}
    assert any("RAG | Revision 2 | Not approved" in item.value for item in at.markdown)
    assert any(m.label == "RAG context (chars)" and m.value == "104 / 6,000" for m in at.metric)
    session = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert session.current_draft.revision_number == 2
    assert len(session.current_draft.channel_copy.split()) == 5
    assert session.current_draft.reviewer_notes == "Revised notes"
    assert session.current_draft.response_metadata.response_id == "resp_revised"
    assert any("Remaining generation attempts: 1 of 3" in caption.value for caption in at.caption)
    assert any("Context mode: rag" in caption.value for caption in at.caption)
    assert any("Corpus snapshot: snapshot-revised" in caption.value for caption in at.caption)
    assert any("knowledge_base/primary/revised.md" in markdown.value for markdown in at.markdown)
    assert any("Revised facts" in markdown.value for markdown in at.markdown)
    assert _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).value == "Review"
    assert at.checkbox(key=_approval_confirm_key(revision=2)).value is False

    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Edit").run()
    assert _on_page(at, "Campaign").text_area(key=_editor_copy_key()).value == "Revised copy with more words"
    assert _on_page(at, "Campaign").text_area(key=_editor_notes_key()).value == "Revised notes"

    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Review").run()
    at.checkbox(key=_approval_confirm_key(revision=2)).check().run()
    at.button(key="approve_button").click().run()
    assert session.approval is not None
    assert session.approval.approved_revision == 2

    at.run()
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Edit").run()
    assert calls["revise"] == 1
    assert _on_page(at, "Campaign").text_area(key=_editor_copy_key()).value == "Revised copy with more words"
    assert _on_page(at, "Campaign").text_area(key=_editor_notes_key()).value == "Revised notes"
    del at
    gc.collect()


def test_manual_save_updates_revision_and_clears_review_state(monkeypatch) -> None:
    def fake_generate(session, **kwargs):
        draft = _fake_draft()
        session.current_draft = draft
        session.history = [draft]
        return draft

    def fake_export(session, **kwargs):
        temp_dir = Path(tempfile.gettempdir()) / "patagonia-content-studio-tests"
        temp_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = temp_dir / "rag-index-failure.md"
        json_path = temp_dir / "rag-index-failure.json"
        markdown_path.write_text(session.current_draft.channel_copy + "\n", encoding="utf-8")
        json_path.write_text('{"review": true}\n', encoding="utf-8")
        return SimpleNamespace(markdown_path=markdown_path, json_path=json_path)

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)
    monkeypatch.setattr(pipeline, "export_approved_current_draft", fake_export)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    _run_loaded_campaign(at)
    _run_generation(at)
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Review").run()
    at.checkbox(key=_approval_confirm_key()).check().run()
    at.button(key="approve_button").click().run()

    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Edit").run()
    _on_page(at, "Campaign").text_area(key=_editor_copy_key()).set_value("Edited copy").run()
    at.button(key="save_edit_button").click().run()

    assert len(at.exception) == 0
    session = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert session.current_draft.revision_number == 2
    assert session.current_draft.channel_copy == "Edited copy"
    assert session.approval is None
    assert at.session_state.get(_export_record_key()) is None
    assert len(at.download_button) == 0
    assert _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).value == "Edit"
    assert any("Saved revision: 2" in caption.value for caption in at.caption)
    assert any("Revision 2 | Not approved" in item.value for item in at.markdown)
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Review").run()
    assert at.checkbox(key=_approval_confirm_key(revision=2)).value is False
    del at
    gc.collect()


def test_manual_save_reviewer_notes_enables_revision_approval(monkeypatch) -> None:
    calls = {"generate": 0, "revise": 0}

    def fake_generate(session, **kwargs):
        calls["generate"] += 1
        draft = _fake_draft()
        session.current_draft = draft
        session.history = [draft]
        return draft

    def fake_export(session, **kwargs):
        temp_dir = Path(tempfile.gettempdir()) / "patagonia-content-studio-tests"
        temp_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = temp_dir / "notes-save.md"
        json_path = temp_dir / "notes-save.json"
        markdown_path.write_text(session.current_draft.channel_copy + "\n", encoding="utf-8")
        json_path.write_text("{\"review\": true}\n", encoding="utf-8")
        return SimpleNamespace(markdown_path=markdown_path, json_path=json_path)

    def fail_revision(*args, **kwargs):
        raise AssertionError("revision should not run")

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)
    monkeypatch.setattr(pipeline, "revise_current_draft", fail_revision)
    monkeypatch.setattr(pipeline, "export_approved_current_draft", fake_export)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    _run_loaded_campaign(at)
    _run_generation(at)
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Edit").run()

    _on_page(at, "Campaign").text_area(key=_editor_notes_key()).set_value("Updated reviewer notes.").run()
    at.button(key="save_edit_button").click().run()

    session = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert calls == {"generate": 1, "revise": 0}
    assert session.current_draft.revision_number == 2
    assert session.current_draft.reviewer_notes == "Updated reviewer notes."
    assert _on_page(at, "Campaign").text_area(key=_editor_notes_key()).value == "Updated reviewer notes."
    assert _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).value == "Edit"
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Review").run()
    assert at.checkbox(key=_approval_confirm_key(revision=2)).disabled is False
    assert at.checkbox(key=_approval_confirm_key(revision=2)).value is False

    at.checkbox(key=_approval_confirm_key(revision=2)).check().run()
    at.button(key="approve_button").click().run()

    assert calls == {"generate": 1, "revise": 0}
    assert session.approval is not None
    assert session.approval.approved_revision == 2
    del at
    gc.collect()

def test_campaign_load_messages_are_compact_and_show_preview(monkeypatch) -> None:
    def fake_generate(session, **kwargs):
        draft = _fake_draft()
        session.current_draft = draft
        session.history = [draft]
        return draft

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    _load_campaign(at)

    assert any(success.value == "Instagram campaign loaded." for success in at.success)
    assert any(
        caption.value == f"Loaded campaign: {ui_state.loaded_campaign_preview('instagram', BRIEF)}"
        for caption in at.caption
    )
    del at
    gc.collect()


def test_prepare_brief_creates_proposal_without_loading_campaign(monkeypatch) -> None:
    def fail_generation(*args, **kwargs):
        raise AssertionError("generation should not run when preparing a brief")

    monkeypatch.setattr(pipeline, "generate_initial_draft", fail_generation)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    at.selectbox(key=ui_state.BRIEF_INSIGHT_ANGLE_KEY).set_value("care_repair")
    at.text_input(key=ui_state.BRIEF_INSIGHT_AUDIENCE_KEY).set_value("US hikers planning weekend trips")
    at.text_area(key=ui_state.BRIEF_INSIGHT_OBJECTIVE_KEY).set_value("Create a concise editorial brief for all channels.")
    _prepare_brief(at)

    proposal = at.session_state[ui_state.BRIEF_INSIGHT_PROPOSAL_KEY]
    assert proposal.angle_key == "care_repair"
    assert proposal.audience == "US hikers planning weekend trips"
    assert proposal.objective == "Create a concise editorial brief for all channels."
    assert at.text_area(key=ui_state.BRIEF_INSIGHT_PROPOSAL_TEXT_KEY).value == proposal.proposed_brief
    assert at.session_state[ui_state.PIPELINE_SESSION_KEY] is None
    assert at.session_state[ui_state.CAMPAIGN_BRIEF_INPUT_KEY] == BRIEF
    assert len(at.download_button) == 0
    del at
    gc.collect()


def test_use_prepared_brief_updates_input_without_replacing_loaded_session(monkeypatch) -> None:
    calls = {"generate": 0}

    def fake_generate(session, **kwargs):
        calls["generate"] += 1
        session.paid_attempts_used += 1
        draft = _fake_channel_draft(session.channel)
        session.current_draft = draft
        session.history = [draft]
        return draft

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    _load_campaign(at)
    _run_generation(at)
    session_before = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    draft_before = session_before.current_draft

    at.selectbox(key=ui_state.BRIEF_INSIGHT_ANGLE_KEY).set_value("packability")
    at.text_input(key=ui_state.BRIEF_INSIGHT_AUDIENCE_KEY).set_value("English-speaking US audience")
    at.text_area(key=ui_state.BRIEF_INSIGHT_OBJECTIVE_KEY).set_value("Prepare a reusable brief for all channels.")
    _prepare_brief(at)
    proposal = at.session_state[ui_state.BRIEF_INSIGHT_PROPOSAL_KEY]
    at.text_area(key=ui_state.BRIEF_INSIGHT_PROPOSAL_TEXT_KEY).set_value(
        proposal.proposed_brief + "\nAdd one short closing line for the channel."
    )
    _use_prepared_brief(at)

    assert calls["generate"] == 1
    assert at.session_state[ui_state.PIPELINE_SESSION_KEY] is session_before
    assert session_before.current_draft is draft_before
    assert at.session_state[ui_state.CAMPAIGN_BRIEF_INPUT_KEY] == proposal.proposed_brief + "\nAdd one short closing line for the channel."
    assert at.session_state[ui_state.CAMPAIGN_BRIEF_KEY] == BRIEF
    assert ui_state.get_pending_campaign_replacement(at.session_state) is None
    del at
    gc.collect()


def test_campaign_reload_preserves_unchanged_session_and_per_channel_work(monkeypatch) -> None:
    calls = {"generate": 0, "export": 0}
    temp_dir = Path(tempfile.gettempdir()) / "patagonia-content-studio-tests"
    temp_dir.mkdir(parents=True, exist_ok=True)

    def fake_generate(session, **kwargs):
        calls["generate"] += 1
        session.paid_attempts_used += 1
        draft = _fake_channel_draft(session.channel)
        session.current_draft = draft
        session.history = [draft]
        return draft

    def fake_export(session, **kwargs):
        calls["export"] += 1
        markdown_path = temp_dir / f"{session.channel}-rev{session.current_draft.revision_number}.md"
        json_path = temp_dir / f"{session.channel}-rev{session.current_draft.revision_number}.json"
        markdown_path.write_text(session.current_draft.channel_copy + "\n", encoding="utf-8")
        json_path.write_text("{\"review\": true}\n", encoding="utf-8")
        return SimpleNamespace(markdown_path=markdown_path, json_path=json_path)

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)
    monkeypatch.setattr(pipeline, "export_approved_current_draft", fake_export)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    _load_campaign(at)
    _run_generation(at)
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Review").run()
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Review").run()
    at.checkbox(key=_approval_confirm_key(revision=1)).check().run()
    at.button(key="approve_button").click().run()

    instagram_session = at.session_state[ui_state.channel_session_key("instagram")]
    instagram_draft = instagram_session.current_draft
    instagram_export = at.session_state[ui_state.export_record_key("instagram")]

    _load_campaign(at, channel="linkedin", brief=BRIEF)
    _run_generation(at)

    linkedin_session = at.session_state[ui_state.channel_session_key("linkedin")]
    assert linkedin_session is at.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert linkedin_session is not instagram_session
    assert linkedin_session.current_draft.channel_copy == "LinkedIn copy v1"

    _load_campaign(at, channel="instagram", brief=BRIEF)

    assert calls == {"generate": 2, "export": 1}
    assert at.session_state[ui_state.channel_session_key("instagram")] is instagram_session
    assert at.session_state[ui_state.channel_session_key("linkedin")] is linkedin_session
    assert instagram_session.current_draft is instagram_draft
    assert at.session_state[ui_state.export_record_key("instagram")] is instagram_export
    assert at.session_state.get(ui_state.export_record_key("linkedin")) is None
    assert at.session_state[ui_state.PIPELINE_SESSION_KEY] is instagram_session
    assert _on_page(at, "Campaign").radio(key=_workspace_view_widget_key("instagram")).value == "Review"
    assert len(at.download_button) == 2
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key("instagram")).set_value("Edit").run()
    assert _on_page(at, "Campaign").text_area(key=_editor_copy_key("instagram")).value == "Instagram copy v1"
    assert _on_page(at, "Campaign").text_area(key=_editor_notes_key("instagram")).value == "Instagram notes v1"
    assert any("Instagram:** Approved" in item.value for item in at.markdown)
    assert any("LinkedIn:** Draft" in item.value for item in at.markdown)
    del at
    gc.collect()


def test_channel_switch_preserves_unsaved_editor_state_and_feedback(monkeypatch) -> None:
    calls = {"generate": 0}

    def fake_generate(session, **kwargs):
        calls["generate"] += 1
        session.paid_attempts_used += 1
        draft = _fake_channel_draft(session.channel)
        session.current_draft = draft
        session.history = [draft]
        return draft

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    _load_campaign(at)
    _run_generation(at)
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key("instagram")).set_value("Edit").run()
    _on_page(at, "Campaign").text_area(key=_editor_copy_key("instagram")).set_value("Unsaved Instagram copy").run()
    _on_page(at, "Campaign").text_area(key=_editor_notes_key("instagram")).set_value("Unsaved Instagram notes").run()
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key("instagram")).set_value("Review").run()
    at.text_area(key=_revision_feedback_key("instagram")).set_value("Tighten the opening.").run()
    assert ui_state.editor_is_dirty(at.session_state, "instagram") is True

    _load_campaign(at, channel="linkedin", brief=BRIEF)
    _run_generation(at)
    _load_campaign(at, channel="instagram", brief=BRIEF)

    assert calls["generate"] == 2
    assert _on_page(at, "Campaign").radio(key=_workspace_view_widget_key("instagram")).value == "Review"
    assert at.text_area(key=_revision_feedback_key("instagram")).value == "Tighten the opening."
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key("instagram")).set_value("Edit").run()
    assert _on_page(at, "Campaign").text_area(key=_editor_copy_key("instagram")).value == "Unsaved Instagram copy"
    assert _on_page(at, "Campaign").text_area(key=_editor_notes_key("instagram")).value == "Unsaved Instagram notes"
    assert ui_state.editor_is_dirty(at.session_state, "instagram") is True
    assert at.session_state[ui_state.editor_working_copy_key("linkedin")] == "LinkedIn copy v1"
    assert at.session_state[ui_state.editor_working_notes_key("linkedin")] == "LinkedIn notes v1"
    del at
    gc.collect()


def test_campaign_reload_preserves_unchanged_session(monkeypatch) -> None:
    def fake_generate(session, **kwargs):
        draft = _fake_channel_draft(session.channel)
        session.current_draft = draft
        session.history = [draft]
        return draft

    def fake_export(session, **kwargs):
        temp_dir = Path(tempfile.gettempdir()) / "patagonia-content-studio-tests"
        temp_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = temp_dir / f"reload-{session.current_draft.revision_number}.md"
        json_path = temp_dir / f"reload-{session.current_draft.revision_number}.json"
        markdown_path.write_text(session.current_draft.channel_copy + "\n", encoding="utf-8")
        json_path.write_text("{\"review\": true}\n", encoding="utf-8")
        return SimpleNamespace(markdown_path=markdown_path, json_path=json_path)

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)
    monkeypatch.setattr(pipeline, "export_approved_current_draft", fake_export)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    _load_campaign(at)
    _run_generation(at)
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Review").run()
    at.checkbox(key=_approval_confirm_key()).check().run()
    at.button(key="approve_button").click().run()

    session_before = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    draft_before = session_before.current_draft
    approval_before = session_before.approval
    export_before = at.session_state[_export_record_key()]

    _load_campaign(at)

    session_after = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert session_after is session_before
    assert session_after.current_draft is draft_before
    assert session_after.approval is approval_before
    assert at.session_state[_export_record_key()] is export_before
    assert len(at.download_button) == 2
    assert any("Loaded campaign:" in caption.value and "Instagram" in caption.value for caption in at.caption)
    del at
    gc.collect()


def test_campaign_brief_replacement_requires_confirmation_and_cancel_preserves_work(monkeypatch) -> None:
    def fake_generate(session, **kwargs):
        draft = _fake_channel_draft(session.channel)
        session.current_draft = draft
        session.history = [draft]
        return draft

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    _load_campaign(at)
    _run_generation(at)
    instagram_session = at.session_state[ui_state.PIPELINE_SESSION_KEY]

    _load_campaign(at, channel="email", brief=BRIEF)
    _run_generation(at)
    email_session = at.session_state[ui_state.PIPELINE_SESSION_KEY]

    _load_campaign(at, channel="linkedin", brief="A different shared campaign brief")

    assert ui_state.get_pending_campaign_replacement(at.session_state) == {
        "channel": "linkedin",
        "brief": "A different shared campaign brief",
    }
    assert at.session_state[ui_state.PIPELINE_SESSION_KEY] is email_session
    assert instagram_session.current_draft is not None
    assert email_session.current_draft is not None
    at.button(key="cancel_campaign_replace_button").click().run()
    assert ui_state.get_pending_campaign_replacement(at.session_state) is None
    assert at.session_state[ui_state.PIPELINE_SESSION_KEY] is email_session
    assert ui_state.get_channel_session(at.session_state, "instagram") is instagram_session
    assert ui_state.get_channel_session(at.session_state, "email") is email_session
    assert instagram_session.current_draft.channel_copy == "Instagram copy v1"
    assert email_session.current_draft.channel_copy == "Email newsletter copy v1"
    del at
    gc.collect()


def test_campaign_brief_replacement_confirmation_resets_all_work(monkeypatch) -> None:
    def fake_generate(session, **kwargs):
        draft = _fake_channel_draft(session.channel)
        session.current_draft = draft
        session.history = [draft]
        return draft

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    _load_campaign(at)
    _run_generation(at)

    assert at.session_state[ui_state.channel_session_key("instagram")].current_draft is not None

    _load_campaign(at, channel="email", brief="A brand-new campaign brief")
    at.checkbox(key="replace_campaign_confirm").check().run()
    at.button(key="replace_campaign_button").click().run()

    session_after = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert session_after.channel == "email"
    assert session_after.current_draft is None
    assert session_after.approval is None
    assert ui_state.get_channel_session(at.session_state, "instagram") is None
    assert ui_state.get_channel_session(at.session_state, "linkedin") is None
    assert ui_state.get_pending_campaign_replacement(at.session_state) is None
    assert at.session_state[ui_state.CAMPAIGN_BRIEF_INPUT_KEY] == "A brand-new campaign brief"
    del at
    gc.collect()


def test_campaign_brief_replacement_validation_failure_preserves_work(monkeypatch) -> None:
    def fake_generate(session, **kwargs):
        draft = _fake_channel_draft(session.channel)
        session.current_draft = draft
        session.history = [draft]
        return draft

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    _load_campaign(at)
    _run_generation(at)

    session_before = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    _load_campaign(at, channel="linkedin", brief="   ")
    at.checkbox(key="replace_campaign_confirm").check().run()
    at.button(key="replace_campaign_button").click().run()

    assert at.session_state[ui_state.PIPELINE_SESSION_KEY] is session_before
    assert session_before.current_draft is not None
    assert ui_state.get_pending_campaign_replacement(at.session_state) == {
        "channel": "linkedin",
        "brief": "",
    }
    assert any("campaign_brief must be a non-empty string" in error.value for error in at.error)
    del at
    gc.collect()


def test_format_validation_renders_without_api_calls_and_preserves_approval_state_on_rerender(monkeypatch) -> None:
    calls = {"generate": 0}

    def fake_generate(session, **kwargs):
        calls["generate"] += 1
        draft = _fake_channel_draft("instagram", copy=_instagram_copy(60), notes="Generated notes")
        session.current_draft = draft
        session.history = [draft]
        return draft

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    _load_campaign(at)
    _run_generation(at)
    assert any("Instagram caption: 60 words; 0 hashtags." in caption.value for caption in at.caption)
    approval_before = SimpleNamespace(
        approved_revision=1,
        approved_copy_fingerprint="fingerprint",
        approved_by="Reviewer",
        approved_at="2026-10-23T00:00:00+00:00",
    )
    session = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    session.approval = approval_before

    at.run()

    assert calls == {"generate": 1}
    assert session.approval is approval_before
    assert sum(1 for caption in at.caption if "Instagram caption: 60 words; 0 hashtags." in caption.value) >= 1
    assert any("passing format checks does not verify factual accuracy." in caption.value for caption in at.caption)
    del at
    gc.collect()


def test_saved_draft_validation_updates_after_manual_save(monkeypatch) -> None:
    calls = {"generate": 0}

    def fake_generate(session, **kwargs):
        calls["generate"] += 1
        draft = _fake_channel_draft("instagram", copy=_instagram_copy(60), notes="Generated notes")
        session.current_draft = draft
        session.history = [draft]
        return draft

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    _load_campaign(at)
    _run_generation(at)
    assert any("Instagram caption: 60 words; 0 hashtags." in caption.value for caption in at.caption)
    initial_caption_count = sum(1 for caption in at.caption if "Instagram caption: 60 words; 0 hashtags." in caption.value)
    assert initial_caption_count >= 1

    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Edit").run()
    _on_page(at, "Campaign").text_area(key=_editor_copy_key()).set_value(_instagram_copy(121)).run()
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Draft").run()
    assert any("Instagram caption: 60 words; 0 hashtags." in caption.value for caption in at.caption)
    assert ui_state.editor_is_dirty(at.session_state, "instagram") is True

    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Edit").run()
    at.button(key="save_edit_button").click().run()

    session = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert calls == {"generate": 1}
    assert session.current_draft.revision_number == 2
    assert _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).value == "Edit"
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Draft").run()
    assert any("Instagram caption: 121 words; 0 hashtags." in caption.value for caption in at.caption)
    assert any("Instagram captions must be 60-120 words; current draft is 121." in warning.value for warning in at.warning)
    assert ui_state.editor_is_dirty(at.session_state, "instagram") is False
    del at
    gc.collect()



def test_manage_sources_are_read_only_when_disabled(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_MANAGEMENT_ENABLED", "false")
    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()

    _on_page(at, "Sources")
    assert any("Source management is read-only in this deployment." in info.value for info in at.info)
    assert not any(button.label == "Preview create" for button in at.button)
    assert not any(button.label == "Preview edit" for button in at.button)
    assert not any(button.label == "Preview delete" for button in at.button)
    del at
    gc.collect()


def test_source_create_uploader_uses_backend_limit_and_rejects_oversized_uploads(tmp_path, monkeypatch) -> None:
    at, _repo_root = _make_app_test(monkeypatch, tmp_path, enable_source_management=True)

    uploader = _on_page(at, "Sources").file_uploader(key="source_create_upload")
    assert uploader.proto.max_upload_size_mb == 1

    oversized_bytes = b"\xff" * (source_registry.MAX_SOURCE_UPLOAD_BYTES + 1)
    _on_page(at, "Sources").file_uploader(key="source_create_upload").set_value(("generated-source.md", oversized_bytes, "text/markdown"))
    _on_page(at, "Sources").selectbox(key="source_create_knowledge_base").set_value("secondary")
    _on_page(at, "Sources").text_input(key="source_create_filename").set_value("generated-source")
    _on_page(at, "Sources").button(key="source_create_preview_button").click().run()

    assert any("at most 1,048,576 bytes" in error.value for error in at.error)
    assert not any(button.key == "source_create_apply_button" for button in at.button)
    del at
    gc.collect()


def test_source_create_preview_and_apply_refreshes_inventory_and_preserves_campaign_state(tmp_path, monkeypatch) -> None:
    _patch_fake_generation(monkeypatch)
    at, repo_root = _make_app_test(monkeypatch, tmp_path, enable_source_management=True)
    _load_campaign(at)
    _run_generation(at)
    session_before = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    uploaded_source = repo_root / "knowledge_base" / "secondary" / "competitor_context.md"

    _on_page(at, "Sources").file_uploader(key="source_create_upload").set_value(("generated-source.md", uploaded_source.read_bytes(), "text/markdown"))
    _on_page(at, "Sources").selectbox(key="source_create_knowledge_base").set_value("secondary")
    _on_page(at, "Sources").text_input(key="source_create_filename").set_value("generated-source")
    _on_page(at, "Sources").button(key="source_create_preview_button").click().run()

    assert any(
        "Create preview ready for knowledge_base/secondary/generated-source.md." in success.value for success in at.success
    )

    _on_page(at, "Sources").button(key="source_create_apply_button").click().run()

    session_after = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert session_after is session_before
    assert session_after.current_draft is not None
    assert session_after.current_draft.channel_copy == "Instagram copy v1"
    inventory_after = ui_state.get_source_inventory(at.session_state)
    assert inventory_after is not None
    assert sum(1 for record in inventory_after if record.knowledge_base == "secondary") == 3
    del at
    gc.collect()


def test_source_edit_preview_requires_fresh_preview_and_blocks_generation_until_refreshed(tmp_path, monkeypatch) -> None:
    _patch_fake_generation(monkeypatch)
    at, repo_root = _make_app_test(monkeypatch, tmp_path, enable_source_management=True)
    _load_campaign(at)
    _run_generation(at)
    session_before = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    source_id = "knowledge_base/secondary/competitor_context.md"
    original_markdown = (repo_root / source_id).read_text(encoding="utf-8")
    first_edit = original_markdown + "\n\nTesting note one."
    second_edit = first_edit + "\n\nTesting note two."

    _on_page(at, "Sources").selectbox(key="source_edit_source").set_value(source_id).run()
    _on_page(at, "Sources").text_area(key="source_edit_markdown").set_value(first_edit).run()
    _on_page(at, "Sources").button(key="source_edit_preview_button").click().run()
    assert any("Edit preview ready for knowledge_base/secondary/competitor_context.md." in success.value for success in at.success)

    _on_page(at, "Sources").text_area(key="source_edit_markdown").set_value(second_edit).run()
    assert any("changed after the last preview" in warning.value for warning in at.warning)
    assert not any(button.key == "source_edit_apply_button" for button in at.button)

    _on_page(at, "Sources").text_area(key="source_edit_markdown").set_value(first_edit).run()
    _on_page(at, "Sources").button(key="source_edit_preview_button").click().run()
    _on_page(at, "Sources").button(key="source_edit_apply_button").click().run()

    session_after = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert session_after is session_before
    assert any("Saved knowledge_base/secondary/competitor_context.md." in success.value for success in at.success)
    inventory_after = ui_state.get_source_inventory(at.session_state)
    assert inventory_after is not None
    assert sum(1 for record in inventory_after if record.knowledge_base == "secondary") == 2
    assert _on_page(at, "Campaign").button(key="generate_button").disabled is True
    assert any("older source snapshot" in warning.value for warning in at.warning)

    del at
    gc.collect()


def test_source_management_offline_flow_refreshes_context_and_restores_snapshot(tmp_path, monkeypatch) -> None:
    _patch_fake_generation(monkeypatch)
    at, repo_root = _make_app_test(monkeypatch, tmp_path, enable_source_management=True)
    _load_campaign(at)
    _run_generation(at)

    session_before = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    source_inventory_before = ui_state.get_source_inventory(at.session_state) or ()
    source_signature_before = ui_state.get_source_inventory_signature(at.session_state)
    context_before = at.session_state[ui_state.CONTEXT_BUNDLE_KEY]
    initial_total_documents = context_before.corpus_measurements.total_document_count
    initial_secondary_count = sum(1 for record in source_inventory_before if record.knowledge_base == "secondary")
    uploaded_source = repo_root / "knowledge_base" / "secondary" / "competitor_context.md"
    generated_source_id = "knowledge_base/secondary/generated-source.md"

    _on_page(at, "Sources").file_uploader(key="source_create_upload").set_value(("generated-source.md", uploaded_source.read_bytes(), "text/markdown"))
    _on_page(at, "Sources").selectbox(key="source_create_knowledge_base").set_value("secondary")
    _on_page(at, "Sources").text_input(key="source_create_filename").set_value("generated-source")
    _on_page(at, "Sources").button(key="source_create_preview_button").click().run()
    _on_page(at, "Sources").button(key="source_create_apply_button").click().run()
    at.run()

    assert at.session_state[ui_state.PIPELINE_SESSION_KEY] is session_before
    assert at.session_state[ui_state.CONTEXT_BUNDLE_KEY] is not context_before
    inventory_after_create = ui_state.get_source_inventory(at.session_state) or ()
    context_after_create = at.session_state[ui_state.CONTEXT_BUNDLE_KEY]
    assert context_after_create.corpus_measurements.total_document_count == initial_total_documents + 1
    assert sum(1 for record in inventory_after_create if record.knowledge_base == "secondary") == initial_secondary_count + 1
    assert ui_state.campaign_sources_are_stale(
        at.session_state,
        session_before.channel,
        ui_state.get_source_inventory_signature(at.session_state),
    ) is True
    assert _on_page(at, "Campaign").button(key="generate_button").disabled is True

    _on_page(at, "Sources").selectbox(key="source_edit_source").set_value(generated_source_id).run()
    edited_markdown = (repo_root / generated_source_id).read_text(encoding="utf-8") + "\n\nTemporary edit note."
    _on_page(at, "Sources").text_area(key="source_edit_markdown").set_value(edited_markdown).run()
    _on_page(at, "Sources").button(key="source_edit_preview_button").click().run()
    _on_page(at, "Sources").button(key="source_edit_apply_button").click().run()
    at.run()

    assert at.session_state[ui_state.PIPELINE_SESSION_KEY] is session_before
    assert at.session_state[ui_state.CONTEXT_BUNDLE_KEY] is not context_after_create
    inventory_after_edit = ui_state.get_source_inventory(at.session_state) or ()
    context_after_edit = at.session_state[ui_state.CONTEXT_BUNDLE_KEY]
    assert context_after_edit.corpus_measurements.total_document_count == initial_total_documents + 1
    assert any(record.repository_relative_path == generated_source_id for record in inventory_after_edit)
    assert ui_state.campaign_sources_are_stale(
        at.session_state,
        session_before.channel,
        ui_state.get_source_inventory_signature(at.session_state),
    ) is True
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Review").run()
    assert at.button(key="revise_button").disabled is True

    _on_page(at, "Sources").selectbox(key="source_delete_source").set_value(generated_source_id).run()
    _on_page(at, "Sources").button(key="source_delete_preview_button").click().run()
    _on_page(at, "Sources").checkbox(key="source_delete_confirm").check().run()
    _on_page(at, "Sources").button(key="source_delete_apply_button").click().run()
    at.session_state["source_delete_confirm"] = False

    assert at.session_state[ui_state.PIPELINE_SESSION_KEY] is session_before
    assert at.session_state[ui_state.CONTEXT_BUNDLE_KEY] is not context_after_edit
    inventory_after_delete = ui_state.get_source_inventory(at.session_state) or ()
    context_after_delete = at.session_state[ui_state.CONTEXT_BUNDLE_KEY]
    assert context_after_delete.corpus_measurements.total_document_count == initial_total_documents
    assert ui_state.get_source_inventory_signature(at.session_state) == source_signature_before
    assert sum(1 for record in inventory_after_delete if record.knowledge_base == "secondary") == initial_secondary_count
    assert not (repo_root / generated_source_id).exists()
    assert _on_page(at, "Campaign").button(key="generate_button").disabled is True
    del at
    gc.collect()


def test_source_delete_preview_and_confirmation_refreshes_inventory_and_preserves_campaign_state(tmp_path, monkeypatch) -> None:
    _patch_fake_generation(monkeypatch)
    at, repo_root = _make_app_test(monkeypatch, tmp_path, enable_source_management=True)
    _load_campaign(at)
    _run_generation(at)
    session_before = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    source_id = "knowledge_base/secondary/market_trends.md"

    _on_page(at, "Sources").selectbox(key="source_delete_source").set_value(source_id).run()
    _on_page(at, "Sources").button(key="source_delete_preview_button").click().run()
    assert any("Delete preview ready for knowledge_base/secondary/market_trends.md." in success.value for success in at.success)

    _on_page(at, "Sources").checkbox(key="source_delete_confirm").check().run()
    _on_page(at, "Sources").button(key="source_delete_apply_button").click().run()

    session_after = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert session_after is session_before
    assert any("Deleted knowledge_base/secondary/market_trends.md." in success.value for success in at.success)
    inventory_after = ui_state.get_source_inventory(at.session_state)
    assert inventory_after is not None
    assert sum(1 for record in inventory_after if record.knowledge_base == "secondary") == 1
    assert _on_page(at, "Campaign").button(key="generate_button").disabled is True
    del at
    gc.collect()


def test_source_create_preview_is_invalidated_by_uploaded_content_change(tmp_path, monkeypatch) -> None:
    at, repo_root = _make_app_test(monkeypatch, tmp_path, enable_source_management=True)
    uploaded_source = repo_root / "knowledge_base" / "secondary" / "competitor_context.md"
    original_bytes = uploaded_source.read_bytes()
    alternate_bytes = (repo_root / "knowledge_base" / "primary" / "brand_voice.md").read_bytes()

    _on_page(at, "Sources").file_uploader(key="source_create_upload").set_value(("generated-source.md", original_bytes, "text/markdown"))
    _on_page(at, "Sources").selectbox(key="source_create_knowledge_base").set_value("secondary")
    _on_page(at, "Sources").text_input(key="source_create_filename").set_value("generated-source")
    _on_page(at, "Sources").button(key="source_create_preview_button").click().run()

    assert any(
        "Create preview ready for knowledge_base/secondary/generated-source.md." in success.value for success in at.success
    )

    _on_page(at, "Sources").file_uploader(key="source_create_upload").set_value(("generated-source.md", alternate_bytes, "text/markdown")).run()
    assert any("changed after the last preview" in warning.value for warning in at.warning)
    assert not any(button.key == "source_create_apply_button" for button in at.button)

    assert not any(button.key == "source_create_apply_button" for button in at.button)

    assert not (repo_root / "knowledge_base" / "secondary" / "generated-source.md").exists()
    del at
    gc.collect()


def test_source_create_preview_is_invalidated_by_kb_change(tmp_path, monkeypatch) -> None:
    at, repo_root = _make_app_test(monkeypatch, tmp_path, enable_source_management=True)
    uploaded_source = repo_root / "knowledge_base" / "secondary" / "competitor_context.md"
    uploaded_bytes = uploaded_source.read_bytes()

    _on_page(at, "Sources").file_uploader(key="source_create_upload").set_value(("generated-source.md", uploaded_bytes, "text/markdown"))
    _on_page(at, "Sources").selectbox(key="source_create_knowledge_base").set_value("secondary")
    _on_page(at, "Sources").text_input(key="source_create_filename").set_value("generated-source")
    _on_page(at, "Sources").button(key="source_create_preview_button").click().run()

    _on_page(at, "Sources").selectbox(key="source_create_knowledge_base").set_value("primary").run()
    assert any("changed after the last preview" in warning.value for warning in at.warning)
    assert not any(button.key == "source_create_apply_button" for button in at.button)

    assert not any(button.key == "source_create_apply_button" for button in at.button)

    assert not (repo_root / "knowledge_base" / "primary" / "generated-source.md").exists()
    del at
    gc.collect()


def test_source_delete_preview_is_invalidated_by_selected_source_change(tmp_path, monkeypatch) -> None:
    at, repo_root = _make_app_test(monkeypatch, tmp_path, enable_source_management=True)
    source_id = "knowledge_base/secondary/market_trends.md"
    alternate_source_id = "knowledge_base/secondary/competitor_context.md"

    _on_page(at, "Sources").selectbox(key="source_delete_source").set_value(source_id).run()
    _on_page(at, "Sources").button(key="source_delete_preview_button").click().run()
    assert any("Delete preview ready for knowledge_base/secondary/market_trends.md." in success.value for success in at.success)

    _on_page(at, "Sources").selectbox(key="source_delete_source").set_value(alternate_source_id).run()
    assert any("changed after the last preview" in warning.value for warning in at.warning)
    assert not any(button.key == "source_delete_apply_button" for button in at.button)

    _on_page(at, "Sources").selectbox(key="source_delete_source").set_value(source_id).run()
    assert not any(button.key == "source_delete_apply_button" for button in at.button)

    _on_page(at, "Sources").button(key="source_delete_preview_button").click().run()
    _on_page(at, "Sources").checkbox(key="source_delete_confirm").check().run()
    _on_page(at, "Sources").button(key="source_delete_apply_button").click().run()

    assert not (repo_root / source_id).exists()
    del at
    gc.collect()


def test_stale_campaign_blocks_generation_and_revision_handlers(tmp_path, monkeypatch) -> None:
    _patch_fake_generation(monkeypatch)
    at, repo_root = _make_app_test(monkeypatch, tmp_path, enable_source_management=True)
    _load_campaign(at)
    _run_generation(at)
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Edit").run()

    session = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    edited_source = repo_root / "knowledge_base" / "secondary" / "market_trends.md"
    edited_source.write_text(edited_source.read_text(encoding="utf-8") + "\n\nTemporary stale-source note.\n", encoding="utf-8")
    at.run()


    import app as app_module
    warnings: list[str] = []
    generate_called = False
    revise_called = False

    def fake_warning(message, **kwargs):
        warnings.append(str(message))

    def fake_generate(*args, **kwargs):
        nonlocal generate_called
        generate_called = True
        raise AssertionError("generate_initial_draft should not run for a stale campaign")

    def fake_revise(*args, **kwargs):
        nonlocal revise_called
        revise_called = True
        raise AssertionError("revise_current_draft should not run for a stale campaign")

    monkeypatch.setattr(app_module.st, "session_state", at.session_state)
    monkeypatch.setattr(app_module.st, "warning", fake_warning)
    monkeypatch.setattr(app_module.st, "success", lambda *args, **kwargs: None)
    monkeypatch.setattr(app_module.st, "spinner", lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(app_module, "generate_initial_draft", fake_generate)
    monkeypatch.setattr(app_module, "revise_current_draft", fake_revise)

    assert ui_state.campaign_sources_are_stale(at.session_state, session.channel, ui_state.get_source_inventory_signature(at.session_state)) is True

    app_module._run_generation(session)
    app_module._run_revision(session, "Make it better.")

    assert generate_called is False
    assert revise_called is False
    assert any("older source snapshot" in warning for warning in warnings)
    del at
    gc.collect()


def test_source_management_disabled_rejects_server_side_mutations(tmp_path, monkeypatch) -> None:
    at, repo_root = _make_app_test(monkeypatch, tmp_path, enable_source_management=True)

    import app as app_module

    prepared_operation = source_registry.prepare_create_source(
        "knowledge_base/secondary/generated-source.md",
        (repo_root / "knowledge_base" / "secondary" / "competitor_context.md").read_text(encoding="utf-8"),
        repo_root,
    )
    monkeypatch.setattr(app_module, "SOURCE_MANAGEMENT_ENABLED", False)

    with pytest.raises(source_registry.SourceRegistryError, match="Source management is disabled"):
        app_module._apply_prepared_source_operation(prepared_operation, action="creating the source")

    del at
    gc.collect()




def _make_rag_build_plan(
    repo_root: Path,
    *,
    state: str = "ready",
    snapshot_id: str = "snapshot-123",
    embedding_model_id: str | None = "text-embedding-3-small",
    chunk_count: int = 6,
    reusable_embedding_count: int = 4,
    pending_embedding_count: int = 2,
    planned_batches: tuple[object, ...] | None = None,
):
    if planned_batches is None:
        planned_batches = (
            SimpleNamespace(chunk_ids=("chunk-1", "chunk-2"), total_input_characters=128),
            SimpleNamespace(chunk_ids=("chunk-3", "chunk-4"), total_input_characters=128),
        )
    return SimpleNamespace(
        repo_root=repo_root,
        index_path=repo_root / ".rag" / "rag_index.sqlite3",
        embedding_model_id=embedding_model_id,
        chunking_policy=SimpleNamespace(max_chunk_characters=4000, overlap_characters=200),
        corpus_snapshot=SimpleNamespace(snapshot_id=snapshot_id),
        chunk_count=chunk_count,
        chunk_counts_by_knowledge_base=(("primary", 3), ("secondary", 3)),
        input_character_sizes=(64, 64, 64, 64, 64, 64),
        pending_embedding_count=pending_embedding_count,
        reusable_embedding_count=reusable_embedding_count,
        planned_batches=planned_batches,
        existing_index_path=repo_root / ".rag" / "rag_index.sqlite3" if state != "missing" else None,
        existing_index_matches={"ready": True, "missing": None, "stale": False, "incompatible": False}[state],
        existing_index_reason={"ready": "match", "missing": "missing", "stale": "snapshot_mismatch", "incompatible": "model_mismatch"}[state],
        vector_dimensions=1536,
    )



def _make_rag_build_result(repo_root: Path):
    completed_batches = (
        SimpleNamespace(
            chunk_ids=("chunk-1", "chunk-2"),
            input_character_sizes=(128, 128),
            total_input_characters=256,
            requested_model="text-embedding-3-small",
            returned_model="text-embedding-3-small",
            vector_dimensions=1536,
            usage=SimpleNamespace(prompt_tokens=32, total_tokens=48),
            elapsed_seconds=0.25,
        ),
    )
    return SimpleNamespace(
        repo_root=repo_root,
        index_path=repo_root / ".rag" / "rag_index.sqlite3",
        manifest_path=repo_root / ".rag" / "rag_build_manifest.json",
        corpus_snapshot=SimpleNamespace(snapshot_id="snapshot-123"),
        embedding_model_id="text-embedding-3-small",
        chunking_policy=SimpleNamespace(max_chunk_characters=4000, overlap_characters=200),
        vector_dimensions=1536,
        chunk_count=6,
        chunk_counts_by_knowledge_base=(("primary", 3), ("secondary", 3)),
        reused_embedding_count=4,
        embedded_chunk_count=2,
        planned_batches=(SimpleNamespace(chunk_ids=("chunk-1", "chunk-2"), total_input_characters=256),),
        completed_batches=completed_batches,
        existing_index_path=repo_root / ".rag" / "rag_index.sqlite3",
        build_elapsed_seconds=1.234,
    )



def _make_rag_index_app_test(
    monkeypatch,
    tmp_path: Path,
    *,
    plan_provider,
    build_provider,
    enable_source_management: bool = True,
):
    repo_root = _prepare_temp_repo(monkeypatch, tmp_path)
    if enable_source_management:
        monkeypatch.setenv("SOURCE_MANAGEMENT_ENABLED", "true")
    else:
        monkeypatch.setenv("SOURCE_MANAGEMENT_ENABLED", "false")
    import app as app_module

    monkeypatch.setattr(app_module, "REPO_ROOT", repo_root)
    monkeypatch.setattr(app_module, "SOURCE_MANAGEMENT_ENABLED", enable_source_management)
    monkeypatch.setattr(app_module.rag_service, "plan_rag_index_build", plan_provider)
    monkeypatch.setattr(app_module.rag_service, "build_rag_index", build_provider)
    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    return at, repo_root, app_module


@pytest.mark.parametrize(
    ("state", "message_fragment"),
    [
        ("ready", "RAG index ready."),
        ("missing", "No local RAG index was found"),
        ("stale", "older source snapshot"),
        ("incompatible", "does not match the configured embedding model or settings"),
    ],
)
def test_rag_index_status_from_build_plan_maps_expected_messages(tmp_path, monkeypatch, state, message_fragment) -> None:
    repo_root = _prepare_temp_repo(monkeypatch, tmp_path)
    import app as app_module

    status = app_module._rag_index_status_from_build_plan(_make_rag_build_plan(repo_root, state=state))
    assert status.state == state
    assert message_fragment in status.message
    assert str(repo_root / ".rag" / "rag_index.sqlite3") in status.details
    assert "snapshot-123" in status.details



def test_rag_index_refresh_preview_and_build_require_confirmation_and_preserve_campaign_state(tmp_path, monkeypatch) -> None:
    build_calls: list[Path] = []

    def plan_provider(*, repo_root):
        return _make_rag_build_plan(repo_root)

    def build_provider(*, repo_root):
        build_calls.append(repo_root)
        return _make_rag_build_result(repo_root)

    at, repo_root, app_module = _make_rag_index_app_test(
        monkeypatch,
        tmp_path,
        plan_provider=plan_provider,
        build_provider=build_provider,
    )
    _patch_fake_generation(monkeypatch)
    _load_campaign(at)
    _run_generation(at)
    session_before = at.session_state[ui_state.PIPELINE_SESSION_KEY]

    assert any(metric.label == "RAG index" and metric.value == "Ready" for metric in at.metric)

    _on_page(at, "Index").button(key="rag_index_preview_button").click().run()
    assert build_calls == []
    assert at.session_state[app_module.RAG_INDEX_MANAGE_SOURCES_EXPANDED_KEY] is True
    assert any("Index update preview ready." in success.value for success in at.success)
    assert any("Corpus snapshot: snapshot-123" in caption.value for caption in at.caption)
    assert any("Chunk count: 6" in caption.value for caption in at.caption)
    assert any("Reusable embeddings: 4 | Missing embeddings: 2" in caption.value for caption in at.caption)
    assert any("Planned batches: 2" in caption.value for caption in at.caption)
    assert _on_page(at, "Index").button(key="rag_index_build_button").disabled is True

    _on_page(at, "Index").checkbox(key="rag_index_build_confirm").check().run()
    assert _on_page(at, "Index").button(key="rag_index_build_button").disabled is False
    _on_page(at, "Index").button(key="rag_index_build_button").click().run()

    assert any(status.state == "complete" and status.label == "Building RAG index completed." for status in at.status)
    session_after = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    summary = at.session_state[app_module.RAG_INDEX_BUILD_SUMMARY_KEY]
    assert session_after is session_before
    assert len(build_calls) == 1
    assert summary["outcome"] == "success"
    assert summary["corpus_snapshot_id"] == "snapshot-123"
    assert summary["embedded_chunk_count"] == 2
    assert summary["reused_embedding_count"] == 4
    assert summary["actual_api_batch_count"] == 1
    assert summary["resulting_index_status"] == "Ready"
    assert at.session_state[app_module.RAG_INDEX_MANAGE_SOURCES_EXPANDED_KEY] is True
    assert any("RAG index updated." in success.value for success in at.success)
    assert any("Outcome: success" in caption.value for caption in at.caption)
    assert any("Embedded chunks: 2 | Reused chunks: 4" in caption.value for caption in at.caption)
    assert any("Actual API batches: 1 | Elapsed: 1.234s" in caption.value for caption in at.caption)
    assert any("Usage: prompt_tokens=32 | total_tokens=48" in caption.value for caption in at.caption)

    at.run()
    assert len(build_calls) == 1
    assert at.session_state[app_module.RAG_INDEX_BUILD_SUMMARY_KEY]["outcome"] == "success"
    assert at.session_state[app_module.RAG_INDEX_MANAGE_SOURCES_EXPANDED_KEY] is True
    assert any("Outcome: success" in caption.value for caption in at.caption)
    assert any("Embedded chunks: 2 | Reused chunks: 4" in caption.value for caption in at.caption)
    assert any("Actual API batches: 1 | Elapsed: 1.234s" in caption.value for caption in at.caption)
    del at
    gc.collect()



def test_rag_index_refresh_preview_is_invalidated_when_sources_change(tmp_path, monkeypatch) -> None:
    plan_state = {"current": None}

    def plan_provider(*, repo_root):
        return plan_state["current"] or _make_rag_build_plan(repo_root)

    def build_provider(*, repo_root):
        raise AssertionError("build should not run for a stale preview")

    at, repo_root, app_module = _make_rag_index_app_test(
        monkeypatch,
        tmp_path,
        plan_provider=plan_provider,
        build_provider=build_provider,
    )
    plan_state["current"] = _make_rag_build_plan(repo_root)
    at.run()

    _on_page(at, "Index").button(key="rag_index_preview_button").click().run()
    assert any("Index update preview ready." in success.value for success in at.success)

    plan_state["current"] = _make_rag_build_plan(
        repo_root,
        state="stale",
        snapshot_id="snapshot-999",
        reusable_embedding_count=1,
        pending_embedding_count=5,
    )
    at.run()

    assert any("changed after the last preview" in warning.value for warning in at.warning)
    assert not any(button.key == "rag_index_build_button" for button in at.button)
    assert not any(checkbox.key == "rag_index_build_confirm" for checkbox in at.checkbox)
    del at
    gc.collect()



def test_rag_index_refresh_is_blocked_when_source_management_is_disabled(tmp_path, monkeypatch) -> None:
    def plan_provider(*, repo_root):
        return _make_rag_build_plan(repo_root)

    def build_provider(*, repo_root):
        raise AssertionError("build should not run when source management is disabled")

    at, repo_root, app_module = _make_rag_index_app_test(
        monkeypatch,
        tmp_path,
        plan_provider=plan_provider,
        build_provider=build_provider,
        enable_source_management=False,
    )

    _on_page(at, "Index").button(key="rag_index_preview_button").click().run()
    assert any("Index builds are disabled" in info.value for info in at.info)
    assert any(button.key == "rag_index_preview_button" for button in at.button)
    assert not any(button.key == "rag_index_build_button" for button in at.button)

    monkeypatch.setattr(app_module, "SOURCE_MANAGEMENT_ENABLED", False)
    with pytest.raises(rag_service.RagServiceError, match="Index building is unavailable"):
        app_module._run_rag_index_build(_make_rag_build_plan(repo_root))

    del at
    gc.collect()



def test_rag_index_build_failure_preserves_campaign_work_and_editor_buffers(tmp_path, monkeypatch) -> None:
    build_calls: list[Path] = []

    def plan_provider(*, repo_root):
        return _make_rag_build_plan(repo_root)

    def build_provider(*, repo_root):
        build_calls.append(repo_root)
        raise rag_service.RagServiceError("simulated build failure")

    at, repo_root, app_module = _make_rag_index_app_test(
        monkeypatch,
        tmp_path,
        plan_provider=plan_provider,
        build_provider=build_provider,
    )
    _patch_fake_generation(monkeypatch)

    def fake_export(session, **kwargs):
        temp_dir = Path(tempfile.gettempdir()) / "patagonia-content-studio-tests"
        temp_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = temp_dir / "rag-index-failure.md"
        json_path = temp_dir / "rag-index-failure.json"
        markdown_path.write_text(session.current_draft.channel_copy + "\n", encoding="utf-8")
        json_path.write_text('{"review": true}\n', encoding="utf-8")
        return SimpleNamespace(markdown_path=markdown_path, json_path=json_path)

    monkeypatch.setattr(pipeline, "export_approved_current_draft", fake_export)

    _load_campaign(at)
    _run_generation(at)
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Review").run()
    at.checkbox(key=_approval_confirm_key(revision=1)).check().run()
    at.button(key="approve_button").click().run()
    session_before = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    approval_before = session_before.approval
    assert len(at.download_button) == 2

    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Edit").run()
    _on_page(at, "Campaign").text_area(key=_editor_copy_key()).set_value("Edited copy").run()
    _on_page(at, "Campaign").text_area(key=_editor_notes_key()).set_value("Edited notes").run()
    editor_copy_before = _on_page(at, "Campaign").text_area(key=_editor_copy_key()).value
    editor_notes_before = _on_page(at, "Campaign").text_area(key=_editor_notes_key()).value

    _on_page(at, "Index").button(key="rag_index_preview_button").click().run()
    _on_page(at, "Index").checkbox(key="rag_index_build_confirm").check().run()
    _on_page(at, "Index").button(key="rag_index_build_button").click().run()

    session_after = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    summary = at.session_state[app_module.RAG_INDEX_BUILD_SUMMARY_KEY]
    assert session_after is session_before
    assert session_after.approval == approval_before
    assert session_after.current_draft is session_before.current_draft
    assert _on_page(at, "Campaign").text_area(key=_editor_copy_key()).value == editor_copy_before
    assert _on_page(at, "Campaign").text_area(key=_editor_notes_key()).value == editor_notes_before
    assert _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).value == "Edit"
    assert ui_state.get_export_record(at.session_state, session_after.channel) is not None
    assert len(build_calls) == 1
    assert summary["outcome"] == "failure"
    assert summary["corpus_snapshot_id"] == "snapshot-123"
    assert summary["planned_batch_count"] == 2
    assert summary["resulting_index_status"] == "Ready"
    assert summary["error_message"] == "simulated build failure"
    assert at.session_state[app_module.RAG_INDEX_MANAGE_SOURCES_EXPANDED_KEY] is True
    _on_page(at, "Index")
    assert any("Error: simulated build failure" in caption.value for caption in at.caption)
    assert any("Outcome: failure" in caption.value for caption in at.caption)

    at.run()
    assert len(build_calls) == 1
    assert at.session_state[app_module.RAG_INDEX_BUILD_SUMMARY_KEY]["outcome"] == "failure"
    assert at.session_state[app_module.RAG_INDEX_MANAGE_SOURCES_EXPANDED_KEY] is True
    assert any("Outcome: failure" in caption.value for caption in at.caption)
    del at
    gc.collect()


def _make_rag_prompt_context():
    return SimpleNamespace(
        primary_context="### Primary retrieved context\nThe internal chest pocket doubles as a stuffsack.\n",
        secondary_context="### Secondary retrieved context\nEditorial context from the companion source.\n",
        source_manifest=(
            SimpleNamespace(
                repository_relative_path="knowledge_base/primary/nano-puff-facts.md",
                knowledge_base="primary",
                document_title="Nano Puff facts",
                source_urls=(PRIMARY_URL,),
                source_url_text=PRIMARY_URL,
                publisher="Patagonia, US website",
                published_updated="2026-10-23",
                accessed="2026-10-23",
                evidence_type="official statement",
                chunk_ids=("primary-facts-1",),
                chunk_scores=(0.91,),
                chunk_kinds=("facts",),
            ),
            SimpleNamespace(
                repository_relative_path="knowledge_base/secondary/outdoor-context.md",
                knowledge_base="secondary",
                document_title="Outdoor context",
                source_urls=(SECONDARY_URL,),
                source_url_text=SECONDARY_URL,
                publisher="Example Publisher",
                published_updated="2026-10-23",
                accessed="2026-10-23",
                evidence_type="analysis",
                chunk_ids=("secondary-editorial-1",),
                chunk_scores=(0.63,),
                chunk_kinds=("editorial",),
            ),
        ),
    )



def _make_rag_retrieval_provenance():
    return {
        "saved_at_utc": "2026-10-23T10:49:24Z",
        "channel": DEFAULT_TEST_CHANNEL,
        "retrieval_status": "success",
        "query": {
            "text": "query text",
            "digest": "query-digest",
            "character_count": 42,
        },
        "corpus_snapshot_id": "snapshot-123",
        "retrieval_settings": {
            "index_path": str(REPO_ROOT / ".rag" / "rag_index.sqlite3"),
            "embedding_model_id": "text-embedding-3-small",
            "primary_top_k": 3,
            "secondary_top_k": 3,
            "primary_minimum_similarity": 0.18,
            "secondary_minimum_similarity": 0.12,
            "max_context_characters": 6000,
            "timeout_seconds": 30.0,
        },
        "manifest": {
            "corpus_snapshot_id": "snapshot-123",
            "embedding_model_id": "text-embedding-3-small",
            "requested_model_id": "text-embedding-3-small",
            "returned_model_id": "text-embedding-3-small",
            "query_digest": "query-digest",
            "query_character_count": 42,
            "query_usage": {"prompt_tokens": 11, "total_tokens": 11},
            "query_elapsed_seconds": 0.123,
            "omission_reasons": ["primary-editorial-1:budget_exceeded", "secondary-editorial-1:ranked_out"],
            "included_sources": [
                {
                    "repository_relative_path": "knowledge_base/primary/nano-puff-facts.md",
                    "knowledge_base": "primary",
                    "document_title": "Nano Puff facts",
                    "source_urls": [PRIMARY_URL],
                    "source_url_text": PRIMARY_URL,
                    "publisher": "Patagonia, US website",
                    "published_updated": "2026-10-23",
                    "accessed": "2026-10-23",
                    "evidence_type": "official statement",
                    "chunk_ids": ["primary-facts-1"],
                    "chunk_scores": [0.91],
                    "chunk_kinds": ["facts"],
                },
                {
                    "repository_relative_path": "knowledge_base/secondary/outdoor-context.md",
                    "knowledge_base": "secondary",
                    "document_title": "Outdoor context",
                    "source_urls": [SECONDARY_URL],
                    "source_url_text": SECONDARY_URL,
                    "publisher": "Example Publisher",
                    "published_updated": "2026-10-23",
                    "accessed": "2026-10-23",
                    "evidence_type": "analysis",
                    "chunk_ids": ["secondary-editorial-1"],
                    "chunk_scores": [0.63],
                    "chunk_kinds": ["editorial"],
                },
            ],
        },
        "blocked_reason": None,
        "query_usage": {"prompt_tokens": 11, "total_tokens": 11},
        "query_elapsed_seconds": 0.123,
        "source_manifest": [
            {
                "repository_relative_path": "knowledge_base/primary/nano-puff-facts.md",
                "knowledge_base": "primary",
                "document_title": "Nano Puff facts",
                "source_urls": [PRIMARY_URL],
                "source_url_text": PRIMARY_URL,
                "publisher": "Patagonia, US website",
                "published_updated": "2026-10-23",
                "accessed": "2026-10-23",
                "evidence_type": "official statement",
                "chunk_ids": ["primary-facts-1"],
                "chunk_scores": [0.91],
                "chunk_kinds": ["facts"],
            },
            {
                "repository_relative_path": "knowledge_base/secondary/outdoor-context.md",
                "knowledge_base": "secondary",
                "document_title": "Outdoor context",
                "source_urls": [SECONDARY_URL],
                "source_url_text": SECONDARY_URL,
                "publisher": "Example Publisher",
                "published_updated": "2026-10-23",
                "accessed": "2026-10-23",
                "evidence_type": "analysis",
                "chunk_ids": ["secondary-editorial-1"],
                "chunk_scores": [0.63],
                "chunk_kinds": ["editorial"],
            },
        ],
        "ranked_candidates": {
            "primary": [
                {
                    "rank": 1,
                    "pool": "primary",
                    "chunk_id": "primary-facts-1",
                    "source_path": "knowledge_base/primary/nano-puff-facts.md",
                    "knowledge_base": "primary",
                    "chunk_kind": "facts",
                    "similarity": 0.91,
                    "document_title": "Nano Puff facts",
                    "section_id": "facts",
                    "section_heading_path": ["Relevant facts"],
                    "section_line_range": [8, 12],
                    "chunk_line_range": [8, 12],
                },
                {
                    "rank": 2,
                    "pool": "primary",
                    "chunk_id": "primary-editorial-1",
                    "source_path": "knowledge_base/primary/nano-puff-facts.md",
                    "knowledge_base": "primary",
                    "chunk_kind": "editorial",
                    "similarity": 0.89,
                    "document_title": "Nano Puff facts",
                    "section_id": "editorial",
                    "section_heading_path": ["Content implications"],
                    "section_line_range": [14, 18],
                    "chunk_line_range": [14, 18],
                },
            ],
            "secondary": [
                {
                    "rank": 1,
                    "pool": "secondary",
                    "chunk_id": "secondary-editorial-1",
                    "source_path": "knowledge_base/secondary/outdoor-context.md",
                    "knowledge_base": "secondary",
                    "chunk_kind": "editorial",
                    "similarity": 0.63,
                    "document_title": "Outdoor context",
                    "section_id": "editorial",
                    "section_heading_path": ["Editorial context"],
                    "section_line_range": [6, 10],
                    "chunk_line_range": [6, 10],
                },
            ],
        },
        "included_chunks": [
            {
                "rank": 1,
                "pool": "primary",
                "chunk_id": "primary-facts-1",
                "source_path": "knowledge_base/primary/nano-puff-facts.md",
                "knowledge_base": "primary",
                "chunk_kind": "facts",
                "similarity": 0.91,
                "document_title": "Nano Puff facts",
                "section_id": "facts",
                "section_heading_path": ["Relevant facts"],
                "section_line_range": [8, 12],
                "chunk_line_range": [8, 12],
                "source_urls": [PRIMARY_URL],
                "source_url_text": PRIMARY_URL,
                "publisher": "Patagonia, US website",
                "published_updated": "2026-10-23",
                "accessed": "2026-10-23",
                "evidence_type": "official statement",
                "chunk_text": "The internal chest pocket doubles as a stuffsack.",
                "applicable_limitations": "Use only the verified packability fact.",
            },
            {
                "rank": 1,
                "pool": "secondary",
                "chunk_id": "secondary-editorial-1",
                "source_path": "knowledge_base/secondary/outdoor-context.md",
                "knowledge_base": "secondary",
                "chunk_kind": "editorial",
                "similarity": 0.63,
                "document_title": "Outdoor context",
                "section_id": "editorial",
                "section_heading_path": ["Editorial context"],
                "section_line_range": [6, 10],
                "chunk_line_range": [6, 10],
                "source_urls": [SECONDARY_URL],
                "source_url_text": SECONDARY_URL,
                "publisher": "Example Publisher",
                "published_updated": "2026-10-23",
                "accessed": "2026-10-23",
                "evidence_type": "analysis",
                "chunk_text": "Use a confident, outdoorsy tone without overstating performance.",
                "applicable_limitations": "Do not imply unsupported field-tested claims.",
            },
        ],
        "retrieved_context": {
            "primary": "### Primary retrieved context\nThe internal chest pocket doubles as a stuffsack.\n",
            "secondary": "### Secondary retrieved context\nEditorial context from the companion source.\n",
        },
        "measurements": {
            "primary_selected_count": 1,
            "primary_fact_count": 1,
            "secondary_selected_count": 1,
            "secondary_fact_count": 0,
            "included_source_count": 2,
            "serialized_context_characters": 128,
            "max_serialized_characters": 6000,
        },
    }



class _FakeRagContextProvider:
    def __init__(self, *, status_state: str = "ready") -> None:
        self.status_state = status_state
        self.describe_calls: list[dict[str, object]] = []
        self.resolve_calls: list[dict[str, object]] = []
        self.prompt_context = _make_rag_prompt_context()
        self.retrieval_provenance = _make_rag_retrieval_provenance()

    def describe_status(self, *, channel: str, campaign_brief: str, revision_feedback: str = ""):
        self.describe_calls.append(
            {
                "channel": channel,
                "campaign_brief": campaign_brief,
                "revision_feedback": revision_feedback,
            }
        )
        details = f"Index available for {channel}."
        if self.status_state == "ready":
            return rag_context_provider.RagIndexStatus(
                state="ready",
                message="RAG index ready.",
                details=details,
                index_path=REPO_ROOT / ".rag" / "rag_index.sqlite3",
                corpus_snapshot_id="snapshot-123",
                existing_index_matches=True,
                existing_index_reason="ready",
                embedding_model_id="text-embedding-3-small",
            )
        if self.status_state == "missing":
            return rag_context_provider.RagIndexStatus(
                state="missing",
                message="No local RAG index was found at the configured path.",
                details=details,
                index_path=REPO_ROOT / ".rag" / "rag_index.sqlite3",
                corpus_snapshot_id="snapshot-123",
                existing_index_matches=None,
                existing_index_reason="missing",
                embedding_model_id="text-embedding-3-small",
            )
        if self.status_state == "stale":
            return rag_context_provider.RagIndexStatus(
                state="stale",
                message="The local RAG index was built from an older source snapshot.",
                details=details,
                index_path=REPO_ROOT / ".rag" / "rag_index.sqlite3",
                corpus_snapshot_id="snapshot-123",
                existing_index_matches=False,
                existing_index_reason="snapshot_mismatch",
                embedding_model_id="text-embedding-3-small",
            )
        return rag_context_provider.RagIndexStatus(
            state="incompatible",
            message="The local RAG index does not match the configured embedding model or settings.",
            details=details,
            index_path=REPO_ROOT / ".rag" / "rag_index.sqlite3",
            corpus_snapshot_id="snapshot-123",
            existing_index_matches=False,
            existing_index_reason="model_mismatch",
            embedding_model_id="text-embedding-3-small",
        )

    def resolve(self, session, *, revision_feedback: str = "", current_draft=None):
        self.resolve_calls.append(
            {
                "channel": session.channel,
                "revision_feedback": revision_feedback,
                "current_draft": current_draft,
            }
        )
        if self.status_state != "ready":
            raise rag_context_provider.RagContextBlockedError(f"blocked:{self.status_state}")
        return pipeline.ResolvedGenerationContext(
            context_mode="rag",
            prompt_context=self.prompt_context,
            retrieval_provenance=self.retrieval_provenance,
        )



def _fake_generated_text(*, instructions: str, user_input: str, max_output_tokens: int, timeout_seconds: float):
    del instructions, max_output_tokens, timeout_seconds
    assert "### Context mode" in user_input
    assert "RAG primary evidence" in user_input
    return pipeline.GeneratedText(
        generated_text="### CHANNEL COPY\nGenerated RAG copy\n### REVIEWER NOTES\nGenerated RAG notes",
        response_id="response-rag",
        model="test-model",
        elapsed_seconds=0.5,
        usage=None,
    )



def test_rag_generation_and_revision_use_retrieval_context_and_feedback(monkeypatch) -> None:
    provider = _FakeRagContextProvider()
    real_generate_initial_draft = pipeline.generate_initial_draft
    real_revise_current_draft = pipeline.revise_current_draft
    prompt_texts: list[str] = []

    def fake_generation_function(*, instructions, user_input, max_output_tokens, timeout_seconds):
        del instructions, max_output_tokens, timeout_seconds
        prompt_texts.append(user_input)
        return pipeline.GeneratedText(
            generated_text="### CHANNEL COPY\nGenerated RAG copy\n### REVIEWER NOTES\nGenerated RAG notes",
            response_id="response-rag",
            model="test-model",
            elapsed_seconds=0.5,
            usage=None,
        )

    def wrapped_generation(session, **kwargs):
        return real_generate_initial_draft(session, generation_function=fake_generation_function, **kwargs)

    def wrapped_revision(session, feedback, **kwargs):
        return real_revise_current_draft(session, feedback, generation_function=fake_generation_function, **kwargs)

    def fake_build_provider():
        return provider


    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    _load_campaign(at)
    session = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    real_generate_initial_draft(session, context_provider=provider, generation_function=fake_generation_function)
    at.run()
    assert session.current_draft.context_mode == "rag"
    assert session.current_draft.retrieval_provenance == provider.retrieval_provenance
    assert provider.resolve_calls[0]["revision_feedback"] == ""
    assert prompt_texts
    assert "### Context mode\nrag" in prompt_texts[0]
    assert "### Primary retrieved context" in prompt_texts[0]
    assert "LEGACY FULL PRIMARY CONTEXT" not in prompt_texts[0]
    assert any("Context mode: rag" in caption.value for caption in at.caption)
    assert any("knowledge_base/primary/nano-puff-facts.md" in markdown.value for markdown in at.markdown)
    assert any("primary-facts-1" in markdown.value for markdown in at.markdown)
    assert any("budget_exceeded" in markdown.value for markdown in at.markdown)

    real_revise_current_draft(session, "Mention the stuffsack feature.", context_provider=provider, generation_function=fake_generation_function)
    at.run()
    assert session.current_draft is not None
    assert session.current_draft.revision_number == 2
    assert session.current_draft.context_mode == "rag"
    assert provider.resolve_calls[-1]["revision_feedback"].startswith("## Current channel copy")
    assert "Mention the stuffsack feature." in provider.resolve_calls[-1]["revision_feedback"]
    assert "### Secondary retrieved context" in prompt_texts[-1]
    del at
    gc.collect()



@pytest.mark.parametrize("status_state", ["missing", "stale", "incompatible"])
def test_rag_status_blocks_generation_before_paid_call_for_all_nonready_states(tmp_path, monkeypatch, status_state) -> None:
    _patch_fake_generation(monkeypatch)
    provider = _FakeRagContextProvider(status_state=status_state)
    warnings: list[str] = []
    generation_called = False

    def fake_warning(message, **kwargs):
        warnings.append(str(message))

    def fail_generation(*args, **kwargs):
        nonlocal generation_called
        generation_called = True
        raise AssertionError("generate_initial_draft should not run when RAG is unavailable")

    import app as app_module
    monkeypatch.setattr(app_module.st, "warning", fake_warning)
    monkeypatch.setattr(app_module, "_build_rag_context_provider", lambda: provider)
    monkeypatch.setattr(app_module, "generate_initial_draft", fail_generation)

    at, _ = _make_app_test(monkeypatch, tmp_path, enable_source_management=True)
    _load_campaign(at)
    session = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    app_module._run_generation(session)

    assert generation_called is False
    assert session.paid_attempts_used == 0
    assert warnings
    del at
    gc.collect()



def test_rag_revision_blocks_and_preserves_previous_work(tmp_path, monkeypatch) -> None:
    provider = _FakeRagContextProvider()
    real_generate_initial_draft = pipeline.generate_initial_draft

    def fake_generation_function(*, instructions, user_input, max_output_tokens, timeout_seconds):
        del instructions, max_output_tokens, timeout_seconds
        return pipeline.GeneratedText(
            generated_text="### CHANNEL COPY\nGenerated RAG copy\n### REVIEWER NOTES\nGenerated RAG notes",
            response_id="response-rag",
            model="test-model",
            elapsed_seconds=0.5,
            usage=None,
        )

    def wrapped_generation(session, **kwargs):
        return real_generate_initial_draft(session, generation_function=fake_generation_function, **kwargs)


    import app as app_module
    import app as app_module
    monkeypatch.setattr(app_module, "generate_initial_draft", wrapped_generation)
    monkeypatch.setattr(app_module, "_build_rag_context_provider", lambda: provider)
    at, _ = _make_app_test(monkeypatch, tmp_path, enable_source_management=True)
    _load_campaign(at)
    session = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    real_generate_initial_draft(session, context_provider=provider, generation_function=fake_generation_function)
    at.run()
    draft_before = session.current_draft

    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Review").run()
    at.checkbox(key=_approval_confirm_key(revision=1)).check().run()
    at.button(key="approve_button").click().run()
    approval_before = session.approval

    import app as app_module

    stale_provider = _FakeRagContextProvider(status_state="stale")
    warnings: list[str] = []

    def fake_warning(message, **kwargs):
        warnings.append(str(message))

    monkeypatch.setattr(app_module.st, "warning", fake_warning)
    monkeypatch.setattr(app_module, "_build_rag_context_provider", lambda: stale_provider)

    app_module._run_revision(session, "Make it more direct.")

    assert session.current_draft is draft_before
    assert session.approval is approval_before
    assert session.paid_attempts_used == 1
    assert warnings
    assert any("older source snapshot" in warning or "RAG" in warning for warning in warnings)
    del at
    gc.collect()



def test_legacy_draft_context_mode_defaults_to_full_corpus(monkeypatch) -> None:
    def fake_generate(session, **kwargs):
        draft = _fake_channel_draft(session.channel)
        session.current_draft = draft
        session.history = [draft]
        return draft

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    _load_campaign(at)
    _run_generation(at)

    assert any("Context mode: full_corpus" in caption.value for caption in at.caption)
    del at
    gc.collect()


def test_workspace_view_retains_selection_through_save_and_approval(monkeypatch) -> None:
    def fake_generate(session, **kwargs):
        draft = _fake_draft()
        session.current_draft = draft
        session.history = [draft]
        return draft

    def fake_export(session, **kwargs):
        temp_dir = Path(tempfile.gettempdir()) / "patagonia-content-studio-tests"
        temp_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = temp_dir / "workspace-view.md"
        json_path = temp_dir / "workspace-view.json"
        markdown_path.write_text(session.current_draft.channel_copy + "\n", encoding="utf-8")
        json_path.write_text("{\"review\": true}\n", encoding="utf-8")
        return SimpleNamespace(markdown_path=markdown_path, json_path=json_path)

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)
    monkeypatch.setattr(pipeline, "export_approved_current_draft", fake_export)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    _load_campaign(at)
    _run_generation(at)
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Edit").run()
    _on_page(at, "Campaign").text_area(key=_editor_copy_key()).set_value("Edited copy").run()
    at.button(key="save_edit_button").click().run()

    assert _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).value == "Edit"
    assert any("Saved revision: 2" in caption.value for caption in at.caption)
    assert any("Revision 2 | Not approved" in item.value for item in at.markdown)
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Review").run()
    assert at.checkbox(key=_approval_confirm_key(revision=2)).value is False

    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).set_value("Review").run()
    at.checkbox(key=_approval_confirm_key(revision=2)).check().run()
    at.button(key="approve_button").click().run()

    assert _on_page(at, "Campaign").radio(key=_workspace_view_widget_key()).value == "Review"
    assert len(at.download_button) == 2
    assert any("Revision 2 | Approved" in item.value for item in at.markdown)
    del at
    gc.collect()



def test_workspace_view_is_preserved_per_channel(monkeypatch) -> None:
    def fake_generate(session, **kwargs):
        draft = _fake_channel_draft(session.channel)
        session.current_draft = draft
        session.history = [draft]
        return draft

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    _load_campaign(at)
    _run_generation(at)
    _on_page(at, "Campaign").radio(key=_workspace_view_widget_key("instagram")).set_value("Review").run()

    _load_campaign(at, channel="linkedin", brief=BRIEF)
    assert _on_page(at, "Campaign").radio(key=_workspace_view_widget_key("linkedin")).value == "Draft"

    _load_campaign(at, channel="instagram", brief=BRIEF)
    assert _on_page(at, "Campaign").radio(key=_workspace_view_widget_key("instagram")).value == "Review"
    del at
    gc.collect()


def test_rag_index_bootstrap_helper_uses_configured_seed_path(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    calls: list[tuple[Path, str, object]] = []

    def fake_bootstrap(*, repo_root, seed_path, index_path=None):
        calls.append((repo_root, seed_path, index_path))
        return SimpleNamespace(restored=True)

    monkeypatch.setenv(app_module.RAG_INDEX_BOOTSTRAP_SEED_PATH_ENV, "deploy/rag_index_seed.sqlite3")
    monkeypatch.setattr(app_module.rag_service, "bootstrap_rag_index_from_seed", fake_bootstrap)

    app_module._bootstrap_rag_index_if_configured()

    assert calls == [(app_module.REPO_ROOT, "deploy/rag_index_seed.sqlite3", None)]


def test_seed_bootstrap_is_opt_in_and_failure_blocks_startup(monkeypatch):
    import app as app_module
    calls = []
    monkeypatch.delenv(app_module.RAG_INDEX_BOOTSTRAP_SEED_PATH_ENV, raising=False)
    monkeypatch.setattr(app_module.rag_service, "bootstrap_rag_index_from_seed", lambda **kwargs: calls.append(kwargs))
    app_module._bootstrap_rag_index_if_configured()
    assert calls == []
    monkeypatch.setenv(app_module.RAG_INDEX_BOOTSTRAP_SEED_PATH_ENV, "deploy/seed.sqlite3")
    def fail(**kwargs):
        raise app_module.rag_service.RagServiceError("Index does not match the current corpus snapshot.")
    monkeypatch.setattr(app_module.rag_service, "bootstrap_rag_index_from_seed", fail)
    messages = []
    monkeypatch.setattr(app_module.st, "error", messages.append)
    class Stopped(Exception):
        pass
    def stop():
        raise Stopped()
    monkeypatch.setattr(app_module.st, "stop", stop)
    with pytest.raises(Stopped):
        app_module._bootstrap_rag_index_if_configured()
    assert messages == ["RAG index bootstrap failed: Index does not match the current corpus snapshot."]


def test_studio_pages_keep_overview_and_show_only_relevant_controls(monkeypatch):
    monkeypatch.setattr(pipeline, "generate_initial_draft", lambda *a, **k: pytest.fail("Navigation must not generate"))
    monkeypatch.setattr(rag_service, "build_rag_index", lambda *a, **k: pytest.fail("Navigation must not build"))
    at = AppTest.from_file(REPO_ROOT / "app.py").run()
    assert not at.exception
    assert {metric.label: metric.value for metric in at.metric} == {
        "RAG index": "Ready", "Primary sources": "5", "Secondary sources": "2", "Product style": "84212", "Loaded campaign": "Not loaded",
    }
    assert not any(widget.key == "source_browser_selected" for widget in at.selectbox)
    assert not any(button.key == "rag_index_preview_button" for button in at.button)
    _on_page(at, "Sources")
    assert len(at.selectbox(key="source_browser_selected").options) == 7
    at.radio(key="source_browser_pool").set_value("Secondary").run()
    assert len(at.selectbox(key="source_browser_selected").options) == 2
    assert not any(widget.key == ui_state.CAMPAIGN_CHANNEL_INPUT_KEY for widget in at.selectbox)
    assert not any(button.key == "rag_index_preview_button" for button in at.button)
    assert any("read-only in this deployment" in info.value for info in at.info)
    assert not at.exception


def test_studio_navigation_preserves_campaign_editor_feedback_and_view(tmp_path, monkeypatch):
    at, _, _ = _make_rag_index_app_test(
        monkeypatch, tmp_path,
        plan_provider=lambda *, repo_root: _make_rag_build_plan(repo_root),
        build_provider=lambda **kwargs: pytest.fail("Preview must not build"),
    )
    _patch_fake_generation(monkeypatch)
    _load_campaign(at, channel="linkedin", brief="A custom campaign brief")
    _run_generation(at)
    session = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    at.radio(key=_workspace_view_widget_key("linkedin")).set_value("Edit").run()
    at.text_area(key=_editor_copy_key("linkedin")).set_value("Unsaved working copy").run()
    at.text_area(key=_editor_notes_key("linkedin")).set_value("Unsaved working notes").run()
    _on_page(at, "Sources")
    _on_page(at, "Index").button(key="rag_index_preview_button").click().run()
    _on_page(at, "Campaign")
    assert at.session_state[ui_state.PIPELINE_SESSION_KEY] is session
    assert at.selectbox(key=ui_state.CAMPAIGN_CHANNEL_INPUT_KEY).value == "linkedin"
    assert at.text_area(key=ui_state.CAMPAIGN_BRIEF_INPUT_KEY).value == "A custom campaign brief"
    assert at.radio(key=_workspace_view_widget_key("linkedin")).value == "Edit"
    assert at.text_area(key=_editor_copy_key("linkedin")).value == "Unsaved working copy"
    assert at.text_area(key=_editor_notes_key("linkedin")).value == "Unsaved working notes"
    at.radio(key=_workspace_view_widget_key("linkedin")).set_value("Review").run()
    at.text_area(key=_revision_feedback_key("linkedin")).set_value("Keep this feedback").run()
    _on_page(at, "Sources")
    _on_page(at, "Campaign")
    assert at.radio(key=_workspace_view_widget_key("linkedin")).value == "Review"
    assert at.text_area(key=_revision_feedback_key("linkedin")).value == "Keep this feedback"
    assert not at.exception


def test_product_switch_isolates_drafts_and_restores_unsaved_work(monkeypatch):
    _patch_fake_generation(monkeypatch)
    at = AppTest.from_file(REPO_ROOT / "app.py").run()
    _load_campaign(at)
    _run_generation(at)
    nano = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    at.radio(key=_workspace_view_widget_key()).set_value("Edit").run()
    at.text_area(key=_editor_copy_key()).set_value("Unsaved Nano Puff copy").run()
    at.selectbox(key="product_selector").set_value("torrentshell_85241").run()
    assert not at.exception
    assert at.session_state[ui_state.PIPELINE_SESSION_KEY] is None
    assert "85241" in at.text_area(key=ui_state.CAMPAIGN_BRIEF_INPUT_KEY).value
    assert all("chest pocket" not in item.value for item in at.markdown)
    _load_campaign(at)
    _run_generation(at)
    rain = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert rain is not nano
    assert rain.product_id == "torrentshell_85241"
    assert nano.product_id == "nano_puff_84212"
    _on_page(at, "Sources")
    _on_page(at, "Campaign")
    assert at.selectbox(key="product_selector").value == "torrentshell_85241"
    at.selectbox(key="product_selector").set_value("nano_puff_84212").run()
    assert not at.exception
    assert at.session_state[ui_state.PIPELINE_SESSION_KEY] is nano
    assert at.radio(key=_workspace_view_widget_key()).value == "Edit"
    assert at.text_area(key=_editor_copy_key()).value == "Unsaved Nano Puff copy"
    at.selectbox(key="product_selector").set_value("torrentshell_85241").run()
    assert at.session_state[ui_state.PIPELINE_SESSION_KEY] is rain


def test_second_product_prepared_brief_uses_only_its_own_focus(monkeypatch):
    at = AppTest.from_file(REPO_ROOT / "app.py").run()
    at.selectbox(key="product_selector").set_value("torrentshell_85241").run()
    at.text_input(key=ui_state.BRIEF_INSIGHT_AUDIENCE_KEY).set_value("US commuters")
    at.text_area(key=ui_state.BRIEF_INSIGHT_OBJECTIVE_KEY).set_value("Introduce rain protection")
    _prepare_brief(at)
    assert not at.exception
    brief = at.text_area(key=ui_state.BRIEF_INSIGHT_PROPOSAL_TEXT_KEY).value
    assert "85241" in brief
    assert "left-pocket" in brief
    assert "stuffsack" not in brief
    assert "windproof" not in brief
    assert at.session_state[ui_state.PIPELINE_SESSION_KEY] is None


def test_preexisting_ui_session_is_bound_to_its_product_before_revision(monkeypatch):
    _patch_fake_generation(monkeypatch)
    at = AppTest.from_file(REPO_ROOT / "app.py").run()
    _load_campaign(at)
    _run_generation(at)
    session = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    draft = session.current_draft
    session.product_id = None  # Pre-extension in-memory UI session.
    at.run()
    assert at.session_state[ui_state.PIPELINE_SESSION_KEY] is session
    assert session.product_id == "nano_puff_84212"
    assert session.current_draft is draft
    assert not at.exception


@pytest.mark.parametrize("mode,copy_text", [("rag", "word " * 70 + "#One #Two #Three"), ("rag", "Too short"), ("full_corpus", "Legacy copy")])
def test_current_result_summarizes_only_saved_evidence_and_advisory_format(monkeypatch, mode, copy_text):
    import app as studio
    monkeypatch.setattr(studio.ui_state, "editor_is_dirty", lambda *_: True)
    draft = SimpleNamespace(channel="instagram", revision_number=3, channel_copy=copy_text,
                            context_mode=mode, source_manifest=({"repository_relative_path": "knowledge_base/primary/product.md"},),
                            retrieval_provenance={"included_chunks": [{"chunk_kind": "facts"}, {"chunk_kind": "editorial"}],
                                "measurements": {"included_source_count": 1, "primary_selected_count": 2,
                                    "primary_fact_count": 1, "secondary_selected_count": 0, "secondary_fact_count": 0,
                                    "serialized_context_characters": 2858, "max_serialized_characters": 6000}})
    session = SimpleNamespace(channel="instagram", current_draft=draft, approval=None)
    at = AppTest.from_string("import streamlit as st; import app; app._render_current_result(st.session_state['test_session'])")
    at.session_state["test_session"] = session
    at.run()
    assert not at.exception
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Format (advisory)"] == ("Pass" if mode == "rag" and copy_text.startswith("word") else "Needs attention")
    if mode == "rag":
        assert metrics["RAG context (chars)"] == "2,858 / 6,000"
        assert any("2 chunks | 1 factual | 1 editorial" in m.value for m in at.markdown)
        assert any("knowledge_base/primary/product.md" in m.value for m in at.markdown)
    else:
        assert metrics["Retrieved evidence"] == "Not recorded"
        assert not any("2 chunks" in m.value for m in at.markdown)
    assert any("saved revision 3" in w.value for w in at.warning)


def test_recorded_index_build_is_historical_and_flags_another_snapshot(monkeypatch, tmp_path):
    import app as studio
    import json
    evidence = tmp_path / "docs/evidence/rag/two-product-index-build.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text(json.dumps({"chunk_count": 23, "reused_embedding_count": 20,
        "embedded_chunk_count": 3, "corpus_snapshot_id": "older-snapshot"}), encoding="utf-8")
    monkeypatch.setattr(studio, "REPO_ROOT", tmp_path)
    plan = SimpleNamespace(corpus_snapshot=SimpleNamespace(snapshot_id="current-snapshot"))
    at = AppTest.from_string("import streamlit as st; import app; app._render_recorded_index_build(st.session_state['test_plan'])")
    at.session_state["test_plan"] = plan
    at.run()
    assert not at.exception
    assert {m.label: m.value for m in at.metric} == {"Total chunks": "23", "Reused embeddings": "20", "New embeddings": "3"}
    assert any("not a new build on Render" in i.value for i in at.info)
    assert any("different corpus snapshot" in w.value for w in at.warning)


def test_read_only_demo_can_confirm_reuse_only_rebuild_without_source_mutations(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_INDEX_BUILD_ENABLED", "true")
    calls = []
    def plan_provider(*, repo_root):
        return _make_rag_build_plan(repo_root, reusable_embedding_count=6, pending_embedding_count=0, planned_batches=())
    def build_provider(*, repo_root, allow_new_embeddings):
        calls.append(allow_new_embeddings)
        result = _make_rag_build_result(repo_root)
        result.embedded_chunk_count = 0
        result.reused_embedding_count = 6
        result.completed_batches = ()
        return result
    at, root, module = _make_rag_index_app_test(monkeypatch, tmp_path, plan_provider=plan_provider,
        build_provider=build_provider, enable_source_management=False)
    _on_page(at, "Index").button(key="rag_index_preview_button").click().run()
    assert at.button(key="rag_index_build_button").disabled
    assert calls == []
    at.checkbox(key=module.RAG_INDEX_BUILD_CONFIRM_KEY).check().run()
    at.button(key="rag_index_build_button").click().run()
    assert not at.exception
    assert calls == [False]
    assert at.session_state[module.RAG_INDEX_BUILD_CONFIRM_KEY] is False
    _on_page(at, "Sources")
    assert any("Source management is read-only" in i.value for i in at.info)
    assert not any(b.key == "source_create_apply_button" for b in at.button)


def test_read_only_rebuild_blocks_missing_vectors_in_ui_and_handler(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_INDEX_BUILD_ENABLED", "true")
    def plan_provider(*, repo_root):
        return _make_rag_build_plan(repo_root)
    def never_build(**kwargs):
        pytest.fail("Missing vectors must not reach builder")
    at, root, module = _make_rag_index_app_test(monkeypatch, tmp_path, plan_provider=plan_provider,
        build_provider=never_build, enable_source_management=False)
    _on_page(at, "Index").button(key="rag_index_preview_button").click().run()
    assert any("New embedding requests are blocked" in w.value for w in at.warning)
    assert not any(b.key == "rag_index_build_button" for b in at.button)
    with pytest.raises(rag_service.RagServiceError, match="only reuse existing embeddings"):
        module._run_rag_index_build(plan_provider(repo_root=root))
