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

BRIEF = ui_state.DEFAULT_BRIEF
DEFAULT_TEST_CHANNEL = "instagram"


@pytest.fixture(autouse=True)
def _default_source_management_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_MANAGEMENT_ENABLED", "false")


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
    at.button(key="generate_button").click().run()


def _prepare_brief(at: AppTest) -> None:
    at.button(key="prepare_brief_button").click().run()


def _use_prepared_brief(at: AppTest) -> None:
    at.button(key="use_prepared_brief_button").click().run()


def _load_campaign(at: AppTest, *, channel: str | None = None, brief: str | None = None) -> None:
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

    assert len(at.selectbox) == 2
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

    assert calls["generate"] == 1
    assert at.text_area(key=_editor_copy_key()).value == "Generated copy v1"
    assert at.text_area(key=_editor_notes_key()).value == "Generated notes v1"
    assert any("Remaining generation attempts: 2 of 3" in caption.value for caption in at.caption)
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
    _run_loaded_campaign(at)
    _run_generation(at)
    at.text_area(key=_revision_feedback_key()).set_value("Please tighten the opening.")
    at.button(key="revise_button").click().run()

    assert calls == {"generate": 1, "revise": 1}
    session = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert session.current_draft.revision_number == 1
    assert session.approval is None
    assert any("Remaining generation attempts: 1 of 3" in caption.value for caption in at.caption)
    assert any("Error: Could not revise draft." in error.value for error in at.error)
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
            channel_copy="Initial copy",
            reviewer_notes="Initial notes",
            source_manifest=(),
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
            channel_copy="Revised copy",
            reviewer_notes="Revised notes",
            source_manifest=(),
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
    _run_loaded_campaign(at)
    _run_generation(at)
    at.text_area(key=_revision_feedback_key()).set_value("Please revise the opening and keep the verified product details.")
    at.button(key="revise_button").click().run()

    assert calls == {"generate": 1, "revise": 1}
    session = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert session.current_draft.revision_number == 2
    assert session.current_draft.channel_copy == "Revised copy"
    assert session.current_draft.reviewer_notes == "Revised notes"
    assert session.current_draft.response_metadata.response_id == "resp_revised"
    assert any("Instagram caption: 2 words; 0 hashtags." in caption.value for caption in at.caption)
    assert at.text_area(key=_editor_copy_key()).value == "Revised copy"
    assert at.text_area(key=_editor_notes_key()).value == "Revised notes"
    assert any("Revised copy" in element.value for element in at.markdown)
    assert any("Revised notes" in element.value for element in at.markdown)
    assert any("Response ID: resp_revised" in element.value for element in at.markdown)

    at.checkbox(key=_approval_confirm_key(revision=2)).check().run()
    at.button(key="approve_button").click().run()
    assert session.approval is not None
    assert session.approval.approved_revision == 2

    at.run()
    assert calls["revise"] == 1
    assert at.text_area(key=_editor_copy_key()).value == "Revised copy"
    assert at.text_area(key=_editor_notes_key()).value == "Revised notes"
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
        markdown_path = temp_dir / "manual-save.md"
        json_path = temp_dir / "manual-save.json"
        markdown_path.write_text(session.current_draft.channel_copy + "\n", encoding="utf-8")
        json_path.write_text("{\"review\": true}\n", encoding="utf-8")
        return SimpleNamespace(markdown_path=markdown_path, json_path=json_path)

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)
    monkeypatch.setattr(pipeline, "export_approved_current_draft", fake_export)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    _run_loaded_campaign(at)
    _run_generation(at)
    at.checkbox(key=_approval_confirm_key()).check().run()
    at.button(key="approve_button").click().run()

    at.text_area(key=_editor_copy_key()).set_value("Edited copy").run()
    at.button(key="save_edit_button").click().run()

    assert len(at.exception) == 0
    session = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert session.current_draft.revision_number == 2
    assert session.current_draft.channel_copy == "Edited copy"
    assert session.approval is None
    assert at.session_state.get(_export_record_key()) is None
    assert len(at.download_button) == 0
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

    at.text_area(key=_editor_notes_key()).set_value("Updated reviewer notes.").run()
    at.button(key="save_edit_button").click().run()

    session = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert calls == {"generate": 1, "revise": 0}
    assert session.current_draft.revision_number == 2
    assert session.current_draft.reviewer_notes == "Updated reviewer notes."
    assert at.text_area(key=_editor_notes_key()).value == "Updated reviewer notes."
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
    assert at.text_area(key=_editor_copy_key("instagram")).value == "Instagram copy v1"
    assert at.text_area(key=_editor_notes_key("instagram")).value == "Instagram notes v1"
    assert len(at.download_button) == 2
    assert any("Instagram: Approved" in caption.value for caption in at.caption)
    assert any("LinkedIn: Draft" in caption.value for caption in at.caption)
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
    at.text_area(key=_editor_copy_key("instagram")).set_value("Unsaved Instagram copy").run()
    at.text_area(key=_editor_notes_key("instagram")).set_value("Unsaved Instagram notes").run()
    at.text_area(key=_revision_feedback_key("instagram")).set_value("Tighten the opening.").run()
    assert ui_state.editor_is_dirty(at.session_state, "instagram") is True

    _load_campaign(at, channel="linkedin", brief=BRIEF)
    _run_generation(at)
    _load_campaign(at, channel="instagram", brief=BRIEF)

    assert calls["generate"] == 2
    assert at.text_area(key=_editor_copy_key("instagram")).value == "Unsaved Instagram copy"
    assert at.text_area(key=_editor_notes_key("instagram")).value == "Unsaved Instagram notes"
    assert at.text_area(key=_revision_feedback_key("instagram")).value == "Tighten the opening."
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
    assert sum(1 for caption in at.caption if "Instagram caption: 60 words; 0 hashtags." in caption.value) >= 2
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
    assert initial_caption_count >= 2

    at.text_area(key=_editor_copy_key()).set_value(_instagram_copy(121)).run()
    assert any("Instagram caption: 60 words; 0 hashtags." in caption.value for caption in at.caption)
    assert ui_state.editor_is_dirty(at.session_state, "instagram") is True

    at.button(key="save_edit_button").click().run()

    session = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert calls == {"generate": 1}
    assert session.current_draft.revision_number == 2
    assert any("Instagram caption: 121 words; 0 hashtags." in caption.value for caption in at.caption)
    assert any("Instagram captions must be 60-120 words; current draft is 121." in warning.value for warning in at.warning)
    assert ui_state.editor_is_dirty(at.session_state, "instagram") is False
    del at
    gc.collect()



def test_manage_sources_are_read_only_when_disabled(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_MANAGEMENT_ENABLED", "false")
    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()

    assert any("Source management is read-only in this deployment." in info.value for info in at.info)
    assert not any(button.label == "Preview create" for button in at.button)
    assert not any(button.label == "Preview edit" for button in at.button)
    assert not any(button.label == "Preview delete" for button in at.button)
    del at
    gc.collect()


def test_source_create_uploader_uses_backend_limit_and_rejects_oversized_uploads(tmp_path, monkeypatch) -> None:
    at, _repo_root = _make_app_test(monkeypatch, tmp_path, enable_source_management=True)

    uploader = at.file_uploader(key="source_create_upload")
    assert uploader.proto.max_upload_size_mb == 1

    oversized_bytes = b"\xff" * (source_registry.MAX_SOURCE_UPLOAD_BYTES + 1)
    at.file_uploader(key="source_create_upload").set_value(("generated-source.md", oversized_bytes, "text/markdown"))
    at.selectbox(key="source_create_knowledge_base").set_value("secondary")
    at.text_input(key="source_create_filename").set_value("generated-source")
    at.button(key="source_create_preview_button").click().run()

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

    at.file_uploader(key="source_create_upload").set_value(("generated-source.md", uploaded_source.read_bytes(), "text/markdown"))
    at.selectbox(key="source_create_knowledge_base").set_value("secondary")
    at.text_input(key="source_create_filename").set_value("generated-source")
    at.button(key="source_create_preview_button").click().run()

    assert any(
        "Create preview ready for knowledge_base/secondary/generated-source.md." in success.value for success in at.success
    )

    at.button(key="source_create_apply_button").click().run()

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

    at.selectbox(key="source_edit_source").set_value(source_id).run()
    at.text_area(key="source_edit_markdown").set_value(first_edit).run()
    at.button(key="source_edit_preview_button").click().run()
    assert any("Edit preview ready for knowledge_base/secondary/competitor_context.md." in success.value for success in at.success)

    at.text_area(key="source_edit_markdown").set_value(second_edit).run()
    assert any("changed after the last preview" in warning.value for warning in at.warning)
    assert not any(button.key == "source_edit_apply_button" for button in at.button)

    at.text_area(key="source_edit_markdown").set_value(first_edit).run()
    at.button(key="source_edit_preview_button").click().run()
    at.button(key="source_edit_apply_button").click().run()

    session_after = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert session_after is session_before
    assert any("Saved knowledge_base/secondary/competitor_context.md." in success.value for success in at.success)
    inventory_after = ui_state.get_source_inventory(at.session_state)
    assert inventory_after is not None
    assert sum(1 for record in inventory_after if record.knowledge_base == "secondary") == 2
    assert at.button(key="generate_button").disabled is True
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

    at.file_uploader(key="source_create_upload").set_value(("generated-source.md", uploaded_source.read_bytes(), "text/markdown"))
    at.selectbox(key="source_create_knowledge_base").set_value("secondary")
    at.text_input(key="source_create_filename").set_value("generated-source")
    at.button(key="source_create_preview_button").click().run()
    at.button(key="source_create_apply_button").click().run()
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
    assert at.button(key="generate_button").disabled is True

    at.selectbox(key="source_edit_source").set_value(generated_source_id).run()
    edited_markdown = (repo_root / generated_source_id).read_text(encoding="utf-8") + "\n\nTemporary edit note."
    at.text_area(key="source_edit_markdown").set_value(edited_markdown).run()
    at.button(key="source_edit_preview_button").click().run()
    at.button(key="source_edit_apply_button").click().run()
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
    assert at.button(key="revise_button").disabled is True

    at.selectbox(key="source_delete_source").set_value(generated_source_id).run()
    at.button(key="source_delete_preview_button").click().run()
    at.checkbox(key="source_delete_confirm").check().run()
    at.button(key="source_delete_apply_button").click().run()
    at.session_state["source_delete_confirm"] = False

    assert at.session_state[ui_state.PIPELINE_SESSION_KEY] is session_before
    assert at.session_state[ui_state.CONTEXT_BUNDLE_KEY] is not context_after_edit
    inventory_after_delete = ui_state.get_source_inventory(at.session_state) or ()
    context_after_delete = at.session_state[ui_state.CONTEXT_BUNDLE_KEY]
    assert context_after_delete.corpus_measurements.total_document_count == initial_total_documents
    assert ui_state.get_source_inventory_signature(at.session_state) == source_signature_before
    assert sum(1 for record in inventory_after_delete if record.knowledge_base == "secondary") == initial_secondary_count
    assert not (repo_root / generated_source_id).exists()
    assert at.button(key="generate_button").disabled is True
    del at
    gc.collect()


def test_source_delete_preview_and_confirmation_refreshes_inventory_and_preserves_campaign_state(tmp_path, monkeypatch) -> None:
    _patch_fake_generation(monkeypatch)
    at, repo_root = _make_app_test(monkeypatch, tmp_path, enable_source_management=True)
    _load_campaign(at)
    _run_generation(at)
    session_before = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    source_id = "knowledge_base/secondary/market_trends.md"

    at.selectbox(key="source_delete_source").set_value(source_id).run()
    at.button(key="source_delete_preview_button").click().run()
    assert any("Delete preview ready for knowledge_base/secondary/market_trends.md." in success.value for success in at.success)

    at.checkbox(key="source_delete_confirm").check().run()
    at.button(key="source_delete_apply_button").click().run()

    session_after = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert session_after is session_before
    assert any("Deleted knowledge_base/secondary/market_trends.md." in success.value for success in at.success)
    inventory_after = ui_state.get_source_inventory(at.session_state)
    assert inventory_after is not None
    assert sum(1 for record in inventory_after if record.knowledge_base == "secondary") == 1
    assert at.button(key="generate_button").disabled is True
    del at
    gc.collect()


def test_source_create_preview_is_invalidated_by_uploaded_content_change(tmp_path, monkeypatch) -> None:
    at, repo_root = _make_app_test(monkeypatch, tmp_path, enable_source_management=True)
    uploaded_source = repo_root / "knowledge_base" / "secondary" / "competitor_context.md"
    original_bytes = uploaded_source.read_bytes()
    alternate_bytes = (repo_root / "knowledge_base" / "primary" / "brand_voice.md").read_bytes()

    at.file_uploader(key="source_create_upload").set_value(("generated-source.md", original_bytes, "text/markdown"))
    at.selectbox(key="source_create_knowledge_base").set_value("secondary")
    at.text_input(key="source_create_filename").set_value("generated-source")
    at.button(key="source_create_preview_button").click().run()

    assert any(
        "Create preview ready for knowledge_base/secondary/generated-source.md." in success.value for success in at.success
    )

    at.file_uploader(key="source_create_upload").set_value(("generated-source.md", alternate_bytes, "text/markdown")).run()
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

    at.file_uploader(key="source_create_upload").set_value(("generated-source.md", uploaded_bytes, "text/markdown"))
    at.selectbox(key="source_create_knowledge_base").set_value("secondary")
    at.text_input(key="source_create_filename").set_value("generated-source")
    at.button(key="source_create_preview_button").click().run()

    at.selectbox(key="source_create_knowledge_base").set_value("primary").run()
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

    at.selectbox(key="source_delete_source").set_value(source_id).run()
    at.button(key="source_delete_preview_button").click().run()
    assert any("Delete preview ready for knowledge_base/secondary/market_trends.md." in success.value for success in at.success)

    at.selectbox(key="source_delete_source").set_value(alternate_source_id).run()
    assert any("changed after the last preview" in warning.value for warning in at.warning)
    assert not any(button.key == "source_delete_apply_button" for button in at.button)

    at.selectbox(key="source_delete_source").set_value(source_id).run()
    assert not any(button.key == "source_delete_apply_button" for button in at.button)

    at.button(key="source_delete_preview_button").click().run()
    at.checkbox(key="source_delete_confirm").check().run()
    at.button(key="source_delete_apply_button").click().run()

    assert not (repo_root / source_id).exists()
    del at
    gc.collect()


def test_stale_campaign_blocks_generation_and_revision_handlers(tmp_path, monkeypatch) -> None:
    _patch_fake_generation(monkeypatch)
    at, repo_root = _make_app_test(monkeypatch, tmp_path, enable_source_management=True)
    _load_campaign(at)
    _run_generation(at)

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
