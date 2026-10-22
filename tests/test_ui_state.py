from types import SimpleNamespace

import src.ui_state as ui_state


def test_initialize_state_sets_defaults_and_supported_channels() -> None:
    state: dict[str, object] = {}

    ui_state.initialize_state(state)

    assert state[ui_state.CAMPAIGN_CHANNEL_KEY] is None
    assert state[ui_state.CAMPAIGN_BRIEF_KEY] is None
    assert state[ui_state.CAMPAIGN_CHANNEL_INPUT_KEY] == ui_state.DEFAULT_CHANNEL
    assert state[ui_state.CAMPAIGN_BRIEF_INPUT_KEY] == ui_state.DEFAULT_BRIEF
    assert state[ui_state.PIPELINE_SESSION_KEY] is None
    assert set(ui_state.CHANNEL_LABELS) == {"instagram", "linkedin", "email"}
    assert ui_state.DEFAULT_BRIEF.startswith("Introduce Patagonia's Men's Nano Puff Jacket")


def test_initialize_state_keeps_existing_brief_input() -> None:
    state: dict[str, object] = {ui_state.CAMPAIGN_BRIEF_INPUT_KEY: "Existing brief"}

    ui_state.initialize_state(state)

    assert state[ui_state.CAMPAIGN_BRIEF_INPUT_KEY] == "Existing brief"


def test_install_session_syncs_editor_buffers_and_clears_review_state() -> None:
    state: dict[str, object] = {}
    ui_state.initialize_state(state)
    session = SimpleNamespace()
    state["approval_confirm_1"] = True
    state[ui_state.EXPORT_RECORD_KEY] = object()

    ui_state.install_campaign_session(state, channel="linkedin", brief="Brief", session=session)
    assert state[ui_state.PIPELINE_SESSION_KEY] is session
    assert state[ui_state.CAMPAIGN_SIGNATURE_KEY] == ("linkedin", "Brief")
    assert state[ui_state.EXPORT_RECORD_KEY] is None
    assert "approval_confirm_1" not in state

    ui_state.sync_editor_buffers(state, channel_copy="Copy", reviewer_notes="Notes")
    assert ui_state.editor_is_dirty(state) is False

    state[ui_state.EDITOR_COPY_KEY] = "Edited copy"
    assert ui_state.editor_is_dirty(state) is True

    ui_state.clear_runtime_state(state)
    assert state[ui_state.PIPELINE_SESSION_KEY] is None
    assert state[ui_state.CAMPAIGN_SIGNATURE_KEY] is None
    assert state[ui_state.EXPORT_RECORD_KEY] is None
    assert state[ui_state.EDITOR_COPY_KEY] == ""
    assert state[ui_state.EDITOR_NOTES_KEY] == ""


def test_pending_editor_sync_applies_before_widget_render() -> None:
    state: dict[str, object] = {}
    ui_state.initialize_state(state)

    ui_state.queue_editor_sync(state, channel_copy="Queued copy", reviewer_notes="Queued notes")
    assert ui_state.apply_pending_editor_sync(state) is True
    assert state[ui_state.EDITOR_COPY_KEY] == "Queued copy"
    assert state[ui_state.EDITOR_NOTES_KEY] == "Queued notes"
    assert state[ui_state.EDITOR_SAVED_COPY_KEY] == "Queued copy"
    assert state[ui_state.EDITOR_SAVED_NOTES_KEY] == "Queued notes"
    assert ui_state.apply_pending_editor_sync(state) is False


def test_current_campaign_changed_detects_new_inputs() -> None:
    state: dict[str, object] = {}
    ui_state.initialize_state(state)
    assert ui_state.current_campaign_changed(state, "instagram", "Brief") is True
    ui_state.install_campaign_session(state, channel="instagram", brief="Brief", session=SimpleNamespace())
    assert ui_state.current_campaign_changed(state, "instagram", "Brief") is False
    assert ui_state.current_campaign_changed(state, "linkedin", "Brief") is True


def test_loaded_campaign_summary_is_human_readable() -> None:
    assert ui_state.loaded_campaign_summary("email", " Newsletter brief ") == "Email newsletter - Newsletter brief"


def test_loaded_campaign_preview_truncates_whitespace_and_length() -> None:
    preview = ui_state.loaded_campaign_preview(
        "instagram",
        "  This   brief has   extra whitespace and should be shortened for the workspace preview.  ",
        max_length=60,
    )

    assert preview.startswith("Instagram ? This brief has extra whitespace")
    assert "  " not in preview
    assert len(preview) <= len("Instagram ? ") + 60
