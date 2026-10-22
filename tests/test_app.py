from pathlib import Path
from types import SimpleNamespace
import gc
import sys
import tempfile

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

streamlit = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

import src.content_pipeline as pipeline
import src.ui_state as ui_state

BRIEF = ui_state.DEFAULT_BRIEF


def _fake_draft(revision_number: int = 1):
    return SimpleNamespace(
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


def test_initial_state_does_not_generate_and_keeps_default_channel(monkeypatch) -> None:
    def fail_generation(*args, **kwargs):
        raise AssertionError("generation should not run on initial load")

    monkeypatch.setattr(pipeline, "generate_initial_draft", fail_generation)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()

    assert len(at.selectbox) == 1
    assert at.selectbox[0].value == "instagram"
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
    assert at.text_area(key=ui_state.EDITOR_COPY_KEY).value == "Generated copy v1"
    assert at.text_area(key=ui_state.EDITOR_NOTES_KEY).value == "Generated notes v1"
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
    at.text_area(key=ui_state.REVISION_FEEDBACK_KEY).set_value("Please tighten the opening.")
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
    at.text_area(key=ui_state.REVISION_FEEDBACK_KEY).set_value("Please tighten the opening.")
    at.button(key="revise_button").click().run()

    assert calls == {"generate": 1, "revise": 1}
    session = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert session.current_draft.revision_number == 1
    assert session.approval is None
    assert any("Remaining generation attempts: 1 of 3" in caption.value for caption in at.caption)
    assert any("Error: Could not revise draft." in error.value for error in at.error)
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
    at.checkbox(key="approval_confirm_1").check().run()
    at.button(key="approve_button").click().run()

    at.text_area(key=ui_state.EDITOR_COPY_KEY).set_value("Edited copy").run()
    at.button(key="save_edit_button").click().run()

    assert len(at.exception) == 0
    session = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert session.current_draft.revision_number == 2
    assert session.current_draft.channel_copy == "Edited copy"
    assert session.approval is None
    assert at.session_state[ui_state.EXPORT_RECORD_KEY] is None
    assert len(at.download_button) == 0
    assert at.checkbox(key="approval_confirm_2").value is False
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
    _run_loaded_campaign(at)

    assert any(success.value == "Instagram campaign loaded." for success in at.success)
    assert any(
        caption.value == f"Loaded campaign: {ui_state.loaded_campaign_preview('instagram', BRIEF)}"
        for caption in at.caption
    )
    del at
    gc.collect()


def test_campaign_reload_preserves_unchanged_session_and_clears_changed_state(monkeypatch) -> None:
    def fake_generate(session, **kwargs):
        draft = _fake_draft()
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
    _run_loaded_campaign(at)
    _run_generation(at)
    at.checkbox(key="approval_confirm_1").check().run()
    at.button(key="approve_button").click().run()

    session_before = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    draft_before = session_before.current_draft
    approval_before = session_before.approval
    export_before = at.session_state[ui_state.EXPORT_RECORD_KEY]

    _run_loaded_campaign(at)

    session_after = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert session_after is session_before
    assert session_after.current_draft is draft_before
    assert session_after.approval is approval_before
    assert at.session_state[ui_state.EXPORT_RECORD_KEY] is export_before
    assert len(at.download_button) == 2
    assert any("Loaded campaign:" in caption.value and "Instagram" in caption.value for caption in at.caption)
    del at
    gc.collect()


def test_campaign_reload_with_changed_inputs_replaces_session_and_clears_stale_state(monkeypatch) -> None:
    def fake_generate(session, **kwargs):
        draft = _fake_draft()
        session.current_draft = draft
        session.history = [draft]
        return draft

    def fake_export(session, **kwargs):
        temp_dir = Path(tempfile.gettempdir()) / "patagonia-content-studio-tests"
        temp_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = temp_dir / f"changed-{session.current_draft.revision_number}.md"
        json_path = temp_dir / f"changed-{session.current_draft.revision_number}.json"
        markdown_path.write_text(session.current_draft.channel_copy + "\n", encoding="utf-8")
        json_path.write_text("{\"review\": true}\n", encoding="utf-8")
        return SimpleNamespace(markdown_path=markdown_path, json_path=json_path)

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)
    monkeypatch.setattr(pipeline, "export_approved_current_draft", fake_export)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    _run_loaded_campaign(at)
    _run_generation(at)
    at.checkbox(key="approval_confirm_1").check().run()
    at.button(key="approve_button").click().run()

    old_session = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    at.selectbox(key=ui_state.CAMPAIGN_CHANNEL_INPUT_KEY).set_value("linkedin")
    at.text_area(key=ui_state.CAMPAIGN_BRIEF_INPUT_KEY).set_value("New campaign brief")
    _run_loaded_campaign(at)

    new_session = at.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert new_session is not old_session
    assert new_session.current_draft is None
    assert new_session.approval is None
    assert at.session_state[ui_state.EXPORT_RECORD_KEY] is None
    assert at.session_state[ui_state.EDITOR_COPY_KEY] == ""
    assert at.session_state[ui_state.EDITOR_NOTES_KEY] == ""
    assert not any(key.startswith(ui_state.APPROVAL_CONFIRM_PREFIX) for key in at.session_state.keys())
    assert any("Loaded campaign:" in caption.value and "LinkedIn" in caption.value for caption in at.caption)
    del at
    gc.collect()


def test_export_retry_preserves_approval_and_handles_missing_files(monkeypatch) -> None:
    calls = {"generate": 0, "export": 0}
    temp_dir = Path(tempfile.gettempdir()) / "patagonia-content-studio-tests"
    temp_dir.mkdir(parents=True, exist_ok=True)
    exported_paths: dict[str, Path] = {}

    def fake_generate(session, **kwargs):
        calls["generate"] += 1
        session.paid_attempts_used += 1
        draft = _fake_draft()
        session.current_draft = draft
        session.history = [draft]
        return draft

    def fake_export(session, **kwargs):
        calls["export"] += 1
        if calls["export"] == 1:
            raise pipeline.ExportError("Could not export approved draft.")
        markdown_path = temp_dir / f"retry-{calls['export']}.md"
        json_path = temp_dir / f"retry-{calls['export']}.json"
        markdown_path.write_text(session.current_draft.channel_copy + "\n", encoding="utf-8")
        json_path.write_text("{\"review\": true}\n", encoding="utf-8")
        exported_paths["markdown"] = markdown_path
        exported_paths["json"] = json_path
        return SimpleNamespace(markdown_path=markdown_path, json_path=json_path)

    monkeypatch.setattr(pipeline, "generate_initial_draft", fake_generate)
    monkeypatch.setattr(pipeline, "export_approved_current_draft", fake_export)

    at = AppTest.from_file(REPO_ROOT / "app.py")
    at.run()
    _run_loaded_campaign(at)
    _run_generation(at)
    at.checkbox(key="approval_confirm_1").check().run()
    at.button(key="approve_button").click().run()

    assert calls["generate"] == 1
    assert calls["export"] == 1
    assert at.session_state[ui_state.PIPELINE_SESSION_KEY].approval is not None
    assert len(at.download_button) == 0
    retry_button = at.button(key="retry_export_button")
    retry_button.click().run()

    assert calls["generate"] == 1
    assert calls["export"] == 2
    assert len(at.download_button) == 2
    assert len(at.checkbox) == 0

    exported_paths["markdown"].unlink()
    exported_paths["json"].unlink()
    at.run()

    assert len(at.error) >= 1
    assert any("could not be read" in error.value.lower() for error in at.error)
    retry_button = at.button(key="retry_export_button")
    retry_button.click().run()
    assert calls["generate"] == 1
    assert calls["export"] == 3
    assert len(at.download_button) == 2
    del at
    gc.collect()
