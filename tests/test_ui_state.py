from pathlib import Path
from types import SimpleNamespace
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import src.ui_state as ui_state


def _fake_session(*, revision_number: int = 1, approved: bool = False, paid_attempts_used: int = 0):
    draft = SimpleNamespace(revision_number=revision_number)
    approval = SimpleNamespace(approved_revision=revision_number) if approved else None
    return SimpleNamespace(current_draft=draft, approval=approval, history=[draft], paid_attempts_used=paid_attempts_used)


def test_initialize_state_sets_defaults_and_supported_channels() -> None:
    state: dict[str, object] = {}

    ui_state.initialize_state(state)

    assert state[ui_state.CAMPAIGN_CHANNEL_KEY] is None
    assert state[ui_state.CAMPAIGN_BRIEF_KEY] is None
    assert state[ui_state.CAMPAIGN_CHANNEL_INPUT_KEY] == ui_state.DEFAULT_CHANNEL
    assert state[ui_state.CAMPAIGN_BRIEF_INPUT_KEY] == ui_state.DEFAULT_BRIEF
    assert state[ui_state.BRIEF_INSIGHT_ANGLE_KEY] == "packability"
    assert state[ui_state.BRIEF_INSIGHT_AUDIENCE_KEY] == ""
    assert state[ui_state.BRIEF_INSIGHT_OBJECTIVE_KEY] == ""
    assert state[ui_state.BRIEF_INSIGHT_PROPOSAL_KEY] is None
    assert state[ui_state.PIPELINE_SESSION_KEY] is None
    assert state[ui_state.PENDING_CAMPAIGN_REPLACEMENT_KEY] is None
    assert set(ui_state.CHANNEL_LABELS) == {"instagram", "linkedin", "email"}
    assert ui_state.DEFAULT_BRIEF.startswith("Introduce Patagonia's Men's Nano Puff Jacket")


def test_store_channel_session_keeps_other_channel_work() -> None:
    state: dict[str, object] = {}
    ui_state.initialize_state(state)
    instagram_session = _fake_session()
    linkedin_session = _fake_session(revision_number=2, approved=True)

    ui_state.store_channel_session(state, channel="instagram", session=instagram_session)
    ui_state.store_channel_session(state, channel="linkedin", session=linkedin_session)

    assert state[ui_state.channel_session_key("instagram")] is instagram_session
    assert state[ui_state.channel_session_key("linkedin")] is linkedin_session
    assert state[ui_state.PIPELINE_SESSION_KEY] is linkedin_session
    assert state[ui_state.CAMPAIGN_CHANNEL_KEY] == "linkedin"


def test_editor_buffers_are_channel_scoped() -> None:
    state: dict[str, object] = {}
    ui_state.initialize_state(state)

    ui_state.sync_editor_buffers(state, channel="instagram", channel_copy="Copy A", reviewer_notes="Notes A")
    ui_state.queue_editor_sync(state, channel="linkedin", channel_copy="Copy B", reviewer_notes="Notes B")

    assert ui_state.editor_is_dirty(state, "instagram") is False
    assert ui_state.editor_is_dirty(state, "linkedin") is False

    state[ui_state.editor_working_copy_key("instagram")] = "Edited A"
    assert ui_state.editor_is_dirty(state, "instagram") is True
    assert ui_state.editor_is_dirty(state, "linkedin") is False

    assert ui_state.apply_pending_editor_sync(state, "linkedin") is True
    assert state[ui_state.editor_working_copy_key("linkedin")] == "Copy B"
    assert state[ui_state.editor_working_notes_key("linkedin")] == "Notes B"
    ui_state.hydrate_editor_buffers(state, "linkedin")
    assert state[ui_state.editor_copy_key("linkedin")] == "Copy B"
    assert state[ui_state.editor_notes_key("linkedin")] == "Notes B"
    assert state[ui_state.editor_saved_copy_key("linkedin")] == "Copy B"
    assert state[ui_state.editor_saved_notes_key("linkedin")] == "Notes B"
    assert ui_state.apply_pending_editor_sync(state, "linkedin") is False


def test_install_session_sets_loaded_campaign_without_clearing_other_work() -> None:
    state: dict[str, object] = {}
    ui_state.initialize_state(state)
    other_session = _fake_session()
    ui_state.store_channel_session(state, channel="instagram", session=other_session)
    session = _fake_session(revision_number=2)
    source_signature = (("knowledge_base/primary/brand_voice.md", "hash-a"),)

    ui_state.install_campaign_session(
        state, channel="linkedin", brief="Brief", session=session, source_signature=source_signature
    )

    assert state[ui_state.PIPELINE_SESSION_KEY] is session
    assert state[ui_state.CAMPAIGN_CHANNEL_KEY] == "linkedin"
    assert state[ui_state.CAMPAIGN_BRIEF_KEY] == "Brief"
    assert state[ui_state.CAMPAIGN_SIGNATURE_KEY] == ("linkedin", "Brief")
    assert state[ui_state.channel_session_key("instagram")] is other_session
    assert state[ui_state.channel_session_key("linkedin")] is session
    assert ui_state.get_channel_source_signature(state, "linkedin") == source_signature


def test_campaign_change_depends_on_shared_brief_only() -> None:
    state: dict[str, object] = {}
    ui_state.initialize_state(state)

    assert ui_state.current_campaign_changed(state, "instagram", "Brief") is True
    ui_state.set_loaded_campaign(state, channel="instagram", brief="Brief")
    assert ui_state.current_campaign_changed(state, "instagram", "Brief") is False
    assert ui_state.current_campaign_changed(state, "linkedin", "Brief") is False
    assert ui_state.current_campaign_changed(state, "linkedin", "Another brief") is True


def test_source_inventory_signature_helpers_track_current_snapshot() -> None:
    state: dict[str, object] = {}
    ui_state.initialize_state(state)
    source_records = (
        SimpleNamespace(repository_relative_path="knowledge_base/primary/brand_voice.md", source_hash="hash-a"),
        SimpleNamespace(repository_relative_path="knowledge_base/secondary/market_trends.md", source_hash="hash-b"),
    )
    signature = ui_state.source_inventory_signature(source_records)

    ui_state.set_source_inventory(state, source_records=source_records, source_signature=signature, current=True, error="")
    ui_state.set_channel_source_signature(state, "instagram", signature)

    assert ui_state.get_source_inventory(state) == source_records
    assert ui_state.get_source_inventory_signature(state) == signature
    assert ui_state.source_inventory_is_current(state) is True
    assert ui_state.get_source_inventory_error(state) == ""
    assert ui_state.campaign_sources_are_stale(state, "instagram", signature) is False

    refreshed_signature = signature + (("knowledge_base/primary/product_facts.md", "hash-c"),)
    assert ui_state.campaign_sources_are_stale(state, "instagram", refreshed_signature) is True

    ui_state.set_source_inventory(state, source_records=source_records, source_signature=signature, current=False, error="boom")
    assert ui_state.source_inventory_is_current(state) is False
    assert ui_state.get_source_inventory_error(state) == "boom"
    assert ui_state.campaign_sources_are_stale(state, "instagram", signature) is True


def test_campaign_work_and_status_helpers_are_channel_specific() -> None:
    state: dict[str, object] = {}
    ui_state.initialize_state(state)
    ui_state.store_channel_session(state, channel="instagram", session=_fake_session())
    ui_state.store_channel_session(state, channel="linkedin", session=_fake_session(approved=True))

    assert ui_state.campaign_has_work(state) is True
    assert ui_state.channel_status_label(state, "instagram") == "Draft"
    assert ui_state.channel_status_label(state, "linkedin") == "Approved"
    assert "Instagram: Draft" in ui_state.campaign_status_summary(state)
    assert "LinkedIn: Approved" in ui_state.campaign_status_summary(state)
    assert ui_state.channel_status_label(state, "email") == "Not generated"


def test_loaded_campaign_summary_is_human_readable() -> None:
    assert ui_state.loaded_campaign_summary("email", " Newsletter brief ") == "Email newsletter - Newsletter brief"


def test_loaded_campaign_preview_truncates_whitespace_and_length() -> None:
    preview = ui_state.loaded_campaign_preview(
        "instagram",
        "  This   brief has   extra whitespace and should be shortened for the workspace preview.  ",
        max_length=60,
    )

    assert preview.startswith("Instagram - This brief has extra whitespace")
    assert "  " not in preview
    assert len(preview) <= len("Instagram - ") + 60


def test_source_staleness_survives_reruns_and_channel_switches() -> None:
    state: dict[str, object] = {}
    ui_state.initialize_state(state)
    source_records = (
        SimpleNamespace(repository_relative_path="knowledge_base/primary/brand_voice.md", source_hash="hash-a"),
        SimpleNamespace(repository_relative_path="knowledge_base/secondary/market_trends.md", source_hash="hash-b"),
    )
    current_signature = ui_state.source_inventory_signature(source_records)
    refreshed_signature = current_signature + (("knowledge_base/primary/product_facts.md", "hash-c"),)

    ui_state.set_source_inventory(state, source_records=source_records, source_signature=current_signature, current=True, error="")
    ui_state.store_channel_session(state, channel="instagram", session=_fake_session())
    ui_state.set_channel_source_signature(state, "instagram", current_signature)

    assert ui_state.campaign_sources_are_stale(state, "instagram", current_signature) is False

    ui_state.set_source_inventory(state, source_records=source_records, source_signature=refreshed_signature, current=True, error="")
    assert ui_state.campaign_sources_are_stale(state, "instagram", refreshed_signature) is True

    ui_state.set_loaded_campaign(state, channel="linkedin", brief="Brief")
    ui_state.activate_channel_session(state, "linkedin")

    assert ui_state.campaign_sources_are_stale(state, "instagram", refreshed_signature) is True



def test_action_in_progress_helpers_toggle_and_reset() -> None:
    state: dict[str, object] = {}
    ui_state.initialize_state(state)

    assert ui_state.action_in_progress(state, "generation") is False
    assert ui_state.action_in_progress(state, "revision") is False

    ui_state.set_action_in_progress(state, "generation", True)
    ui_state.set_action_in_progress(state, "revision", True)

    assert ui_state.action_in_progress(state, "generation") is True
    assert ui_state.action_in_progress(state, "revision") is True

    ui_state.clear_runtime_state(state)

    assert ui_state.action_in_progress(state, "generation") is False
    assert ui_state.action_in_progress(state, "revision") is False


def test_workspace_view_state_is_channel_scoped_and_resets_with_runtime_state() -> None:
    state: dict[str, object] = {}
    ui_state.initialize_state(state)
    state[ui_state.workspace_view_key("instagram")] = "Edit"
    state[ui_state.workspace_view_key("linkedin")] = "Review"

    assert state[ui_state.workspace_view_key("instagram")] == "Edit"
    assert state[ui_state.workspace_view_key("linkedin")] == "Review"

    ui_state.clear_channel_state(state, "instagram")
    assert ui_state.workspace_view_key("instagram") not in state
    assert state[ui_state.workspace_view_key("linkedin")] == "Review"

    ui_state.clear_runtime_state(state)
    assert ui_state.workspace_view_key("linkedin") not in state
