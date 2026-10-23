from __future__ import annotations

from typing import Any, MutableMapping

DEFAULT_CHANNEL = "instagram"
DEFAULT_BRIEF = (
    "Introduce Patagonia's Men's Nano Puff Jacket, style 84212, to an English-speaking US audience planning everyday "
    "outings and outdoor trips. Highlight verified packability and practical features. Use a direct, useful tone and "
    "one invitation to explore the product details. Avoid prices, discounts, urgency and unsupported environmental "
    "claims."
)

CAMPAIGN_CHANNEL_KEY = "campaign_channel"
CAMPAIGN_CHANNEL_INPUT_KEY = "campaign_channel_input"
CAMPAIGN_BRIEF_KEY = "campaign_brief"
CAMPAIGN_BRIEF_INPUT_KEY = "campaign_brief_input"
BRIEF_INSIGHT_ANGLE_KEY = "brief_insight_angle"
BRIEF_INSIGHT_AUDIENCE_KEY = "brief_insight_audience"
BRIEF_INSIGHT_OBJECTIVE_KEY = "brief_insight_objective"
BRIEF_INSIGHT_PROPOSAL_KEY = "brief_insight_proposal"
BRIEF_INSIGHT_PROPOSAL_TEXT_KEY = "brief_insight_proposal_text"
CAMPAIGN_SIGNATURE_KEY = "campaign_signature"
CONTEXT_BUNDLE_KEY = "context_bundle"
BRIEF_SNAPSHOT_KEY = "brief_snapshot"
SOURCE_INVENTORY_KEY = "source_inventory"
SOURCE_INVENTORY_SIGNATURE_KEY = "source_inventory_signature"
SOURCE_INVENTORY_CURRENT_KEY = "source_inventory_current"
SOURCE_INVENTORY_ERROR_KEY = "source_inventory_error"
PIPELINE_SESSION_KEY = "pipeline_session"
STATUS_MESSAGE_KEY = "status_message"
ERROR_MESSAGE_KEY = "error_message"
EDITOR_COPY_KEY = "editor_copy_buffer"
EDITOR_NOTES_KEY = "editor_notes_buffer"
EDITOR_SAVED_COPY_KEY = "editor_saved_copy"
EDITOR_SAVED_NOTES_KEY = "editor_saved_notes"
EDITOR_PENDING_COPY_KEY = "editor_pending_copy"
EDITOR_PENDING_NOTES_KEY = "editor_pending_notes"
EDITOR_WORKING_COPY_KEY = "editor_working_copy"
EDITOR_WORKING_NOTES_KEY = "editor_working_notes"
REVISION_FEEDBACK_KEY = "revision_feedback"
REVISION_FEEDBACK_WORKING_KEY = "revision_feedback_working"
EXPORT_RECORD_KEY = "export_record"
PENDING_CAMPAIGN_REPLACEMENT_KEY = "pending_campaign_replacement"
APPROVAL_CONFIRM_PREFIX = "approval_confirm_"
CHANNEL_SESSION_PREFIX = "channel_session_"
CHANNEL_EXPORT_PREFIX = "channel_export_"
CHANNEL_EDITOR_PREFIX = "channel_editor_"
CHANNEL_EDITOR_SAVED_PREFIX = "channel_editor_saved_"
CHANNEL_EDITOR_PENDING_PREFIX = "channel_editor_pending_"
CHANNEL_EDITOR_WORKING_PREFIX = "channel_editor_working_"
CHANNEL_REVISION_FEEDBACK_WORKING_PREFIX = "channel_revision_feedback_working_"
CHANNEL_FEEDBACK_PREFIX = "channel_revision_feedback_"
CHANNEL_SOURCE_SIGNATURE_PREFIX = "channel_source_signature_"
CHANNEL_WORKSPACE_VIEW_PREFIX = "workspace_view_"
CHANNEL_WORKSPACE_VIEW_WIDGET_PREFIX = "workspace_view_widget_"
ACTION_IN_PROGRESS_PREFIX = "action_in_progress_"

WORKSPACE_VIEWS = ("Draft", "Edit", "Review")
DEFAULT_WORKSPACE_VIEW = WORKSPACE_VIEWS[0]

CHANNEL_LABELS = {
    "instagram": "Instagram",
    "linkedin": "LinkedIn",
    "email": "Email newsletter",
}

SUPPORTED_CHANNELS = tuple(CHANNEL_LABELS.keys())


def campaign_signature(channel: str, brief: str) -> tuple[str, str]:
    return channel, brief.strip()


def scoped_key(prefix: str, channel: str) -> str:
    return f"{prefix}{channel}"


def channel_session_key(channel: str) -> str:
    return scoped_key(CHANNEL_SESSION_PREFIX, channel)


def export_record_key(channel: str) -> str:
    return scoped_key(CHANNEL_EXPORT_PREFIX, channel)


def editor_copy_key(channel: str) -> str:
    return scoped_key(CHANNEL_EDITOR_PREFIX, channel)


def editor_notes_key(channel: str) -> str:
    return f"{CHANNEL_EDITOR_PREFIX}{channel}_notes"


def editor_saved_copy_key(channel: str) -> str:
    return scoped_key(CHANNEL_EDITOR_SAVED_PREFIX, channel)


def editor_saved_notes_key(channel: str) -> str:
    return f"{CHANNEL_EDITOR_SAVED_PREFIX}{channel}_notes"


def editor_pending_copy_key(channel: str) -> str:
    return scoped_key(CHANNEL_EDITOR_PENDING_PREFIX, channel)


def editor_pending_notes_key(channel: str) -> str:
    return f"{CHANNEL_EDITOR_PENDING_PREFIX}{channel}_notes"


def editor_working_copy_key(channel: str) -> str:
    return scoped_key(CHANNEL_EDITOR_WORKING_PREFIX, channel)


def editor_working_notes_key(channel: str) -> str:
    return f"{CHANNEL_EDITOR_WORKING_PREFIX}{channel}_notes"


def revision_feedback_key(channel: str) -> str:
    return scoped_key(CHANNEL_FEEDBACK_PREFIX, channel)


def revision_feedback_working_key(channel: str) -> str:
    return scoped_key(CHANNEL_REVISION_FEEDBACK_WORKING_PREFIX, channel)


def channel_source_signature_key(channel: str) -> str:
    return scoped_key(CHANNEL_SOURCE_SIGNATURE_PREFIX, channel)


def action_in_progress_key(action: str) -> str:
    return scoped_key(ACTION_IN_PROGRESS_PREFIX, action)


def approval_confirm_key(channel: str, revision: int) -> str:
    return f"{APPROVAL_CONFIRM_PREFIX}{channel}_{revision}"


def workspace_view_key(channel: str) -> str:
    return scoped_key(CHANNEL_WORKSPACE_VIEW_PREFIX, channel)


def workspace_view_widget_key(channel: str) -> str:
    return scoped_key(CHANNEL_WORKSPACE_VIEW_WIDGET_PREFIX, channel)


def get_workspace_view(state: MutableMapping[str, Any], channel: str) -> str:
    value = state.get(workspace_view_key(channel))
    return value if isinstance(value, str) and value in WORKSPACE_VIEWS else DEFAULT_WORKSPACE_VIEW


def set_workspace_view(state: MutableMapping[str, Any], channel: str, workspace_view: str) -> None:
    if workspace_view not in WORKSPACE_VIEWS:
        workspace_view = DEFAULT_WORKSPACE_VIEW
    state[workspace_view_key(channel)] = workspace_view


def initialize_state(state: MutableMapping[str, Any]) -> None:
    state.setdefault(CAMPAIGN_CHANNEL_KEY, None)
    state.setdefault(CAMPAIGN_BRIEF_KEY, None)
    state.setdefault(CAMPAIGN_SIGNATURE_KEY, None)
    state.setdefault(CONTEXT_BUNDLE_KEY, None)
    state.setdefault(BRIEF_SNAPSHOT_KEY, None)
    state.setdefault(SOURCE_INVENTORY_KEY, None)
    state.setdefault(SOURCE_INVENTORY_SIGNATURE_KEY, None)
    state.setdefault(SOURCE_INVENTORY_CURRENT_KEY, None)
    state.setdefault(SOURCE_INVENTORY_ERROR_KEY, "")
    state.setdefault(PIPELINE_SESSION_KEY, None)
    state.setdefault(action_in_progress_key("generation"), False)
    state.setdefault(action_in_progress_key("revision"), False)
    state.setdefault(STATUS_MESSAGE_KEY, "")
    state.setdefault(ERROR_MESSAGE_KEY, "")
    state.setdefault(PENDING_CAMPAIGN_REPLACEMENT_KEY, None)
    state.setdefault(CAMPAIGN_CHANNEL_INPUT_KEY, DEFAULT_CHANNEL)
    state.setdefault(CAMPAIGN_BRIEF_INPUT_KEY, DEFAULT_BRIEF)
    state.setdefault(BRIEF_INSIGHT_ANGLE_KEY, "packability")
    state.setdefault(BRIEF_INSIGHT_AUDIENCE_KEY, "")
    state.setdefault(BRIEF_INSIGHT_OBJECTIVE_KEY, "")
    state.setdefault(BRIEF_INSIGHT_PROPOSAL_KEY, None)
    state.setdefault(BRIEF_INSIGHT_PROPOSAL_TEXT_KEY, "")


def set_loaded_campaign(state: MutableMapping[str, Any], *, channel: str, brief: str) -> None:
    state[CAMPAIGN_CHANNEL_KEY] = channel
    state[CAMPAIGN_BRIEF_KEY] = brief
    state[CAMPAIGN_SIGNATURE_KEY] = campaign_signature(channel, brief)


def get_loaded_campaign_brief(state: MutableMapping[str, Any]) -> str | None:
    value = state.get(CAMPAIGN_BRIEF_KEY)
    return value if isinstance(value, str) else None


def clear_runtime_state(state: MutableMapping[str, Any]) -> None:
    for channel in SUPPORTED_CHANNELS:
        state.pop(channel_session_key(channel), None)
        state.pop(channel_source_signature_key(channel), None)
        state.pop(export_record_key(channel), None)
        state.pop(editor_copy_key(channel), None)
        state.pop(editor_notes_key(channel), None)
        state.pop(editor_saved_copy_key(channel), None)
        state.pop(editor_saved_notes_key(channel), None)
        state.pop(editor_pending_copy_key(channel), None)
        state.pop(editor_working_copy_key(channel), None)
        state.pop(editor_working_notes_key(channel), None)
        state.pop(revision_feedback_key(channel), None)
        state.pop(revision_feedback_working_key(channel), None)
        state.pop(workspace_view_key(channel), None)
        state.pop(workspace_view_widget_key(channel), None)
        for key in list(state.keys()):
            if isinstance(key, str) and key.startswith(APPROVAL_CONFIRM_PREFIX) and key.startswith(f"{APPROVAL_CONFIRM_PREFIX}{channel}_"):
                del state[key]
    state[PIPELINE_SESSION_KEY] = None
    state[CAMPAIGN_CHANNEL_KEY] = None
    state[CAMPAIGN_BRIEF_KEY] = None
    state[CAMPAIGN_SIGNATURE_KEY] = None
    state[PENDING_CAMPAIGN_REPLACEMENT_KEY] = None
    state.pop(action_in_progress_key("generation"), None)
    state.pop(action_in_progress_key("revision"), None)
    state[STATUS_MESSAGE_KEY] = ""
    state[ERROR_MESSAGE_KEY] = ""


def clear_channel_state(state: MutableMapping[str, Any], channel: str) -> None:
    state.pop(channel_session_key(channel), None)
    state.pop(channel_source_signature_key(channel), None)
    state.pop(export_record_key(channel), None)
    state.pop(editor_copy_key(channel), None)
    state.pop(editor_notes_key(channel), None)
    state.pop(editor_saved_copy_key(channel), None)
    state.pop(editor_saved_notes_key(channel), None)
    state.pop(editor_pending_copy_key(channel), None)
    state.pop(editor_working_copy_key(channel), None)
    state.pop(editor_working_notes_key(channel), None)
    state.pop(revision_feedback_key(channel), None)
    state.pop(revision_feedback_working_key(channel), None)
    state.pop(workspace_view_key(channel), None)
    state.pop(workspace_view_widget_key(channel), None)
    for key in list(state.keys()):
        if isinstance(key, str) and key.startswith(f"{APPROVAL_CONFIRM_PREFIX}{channel}_"):
            del state[key]


def store_channel_session(
    state: MutableMapping[str, Any],
    *,
    channel: str,
    session: Any,
    source_signature: Any | None = None,
) -> None:
    state[channel_session_key(channel)] = session
    state[PIPELINE_SESSION_KEY] = session
    state[CAMPAIGN_CHANNEL_KEY] = channel
    if source_signature is not None:
        state[channel_source_signature_key(channel)] = source_signature


def get_channel_session(state: MutableMapping[str, Any], channel: str) -> Any:
    return state.get(channel_session_key(channel))


def activate_channel_session(state: MutableMapping[str, Any], channel: str) -> Any:
    session = get_channel_session(state, channel)
    state[PIPELINE_SESSION_KEY] = session
    state[CAMPAIGN_CHANNEL_KEY] = channel
    return session


def install_campaign_session(
    state: MutableMapping[str, Any],
    *,
    channel: str,
    brief: str,
    session: Any,
    source_signature: Any | None = None,
) -> None:
    set_loaded_campaign(state, channel=channel, brief=brief)
    store_channel_session(state, channel=channel, session=session, source_signature=source_signature)


def queue_editor_sync(state: MutableMapping[str, Any], *, channel: str | None = None, channel_copy: str, reviewer_notes: str) -> None:
    resolved_channel = _resolve_channel(state, channel)
    state[editor_pending_copy_key(resolved_channel)] = channel_copy
    state[editor_pending_notes_key(resolved_channel)] = reviewer_notes


def apply_pending_editor_sync(state: MutableMapping[str, Any], channel: str | None = None) -> bool:
    resolved_channel = _resolve_channel(state, channel)
    pending_copy = state.get(editor_pending_copy_key(resolved_channel))
    pending_notes = state.get(editor_pending_notes_key(resolved_channel))
    if pending_copy is None and pending_notes is None:
        return False

    state[editor_working_copy_key(resolved_channel)] = "" if pending_copy is None else pending_copy
    state[editor_working_notes_key(resolved_channel)] = "" if pending_notes is None else pending_notes
    state[editor_saved_copy_key(resolved_channel)] = state[editor_working_copy_key(resolved_channel)]
    state[editor_saved_notes_key(resolved_channel)] = state[editor_working_notes_key(resolved_channel)]
    state[editor_pending_copy_key(resolved_channel)] = None
    state[editor_pending_notes_key(resolved_channel)] = None
    return True


def hydrate_editor_buffers(state: MutableMapping[str, Any], channel: str | None = None) -> None:
    resolved_channel = _resolve_channel(state, channel)
    state[editor_copy_key(resolved_channel)] = state.get(
        editor_working_copy_key(resolved_channel),
        state.get(editor_saved_copy_key(resolved_channel), ""),
    )
    state[editor_notes_key(resolved_channel)] = state.get(
        editor_working_notes_key(resolved_channel),
        state.get(editor_saved_notes_key(resolved_channel), ""),
    )


def record_editor_working_values(state: MutableMapping[str, Any], channel: str | None = None) -> None:
    resolved_channel = _resolve_channel(state, channel)
    state[editor_working_copy_key(resolved_channel)] = state.get(editor_copy_key(resolved_channel), "")
    state[editor_working_notes_key(resolved_channel)] = state.get(editor_notes_key(resolved_channel), "")


def hydrate_revision_feedback(state: MutableMapping[str, Any], channel: str | None = None) -> None:
    resolved_channel = _resolve_channel(state, channel)
    state[revision_feedback_key(resolved_channel)] = state.get(revision_feedback_working_key(resolved_channel), "")


def record_revision_feedback(state: MutableMapping[str, Any], channel: str | None = None) -> None:
    resolved_channel = _resolve_channel(state, channel)
    state[revision_feedback_working_key(resolved_channel)] = state.get(revision_feedback_key(resolved_channel), "")


def sync_editor_buffers(
    state: MutableMapping[str, Any],
    *,
    channel: str | None = None,
    channel_copy: str,
    reviewer_notes: str,
) -> None:
    resolved_channel = _resolve_channel(state, channel)
    state[editor_copy_key(resolved_channel)] = channel_copy
    state[editor_notes_key(resolved_channel)] = reviewer_notes
    state[editor_working_copy_key(resolved_channel)] = channel_copy
    state[editor_working_notes_key(resolved_channel)] = reviewer_notes
    state[editor_saved_copy_key(resolved_channel)] = channel_copy
    state[editor_saved_notes_key(resolved_channel)] = reviewer_notes
    state[editor_pending_copy_key(resolved_channel)] = None
    state[editor_pending_notes_key(resolved_channel)] = None


def clear_review_state(state: MutableMapping[str, Any], channel: str | None = None) -> None:
    resolved_channel = _resolve_channel(state, channel)
    state.pop(export_record_key(resolved_channel), None)
    state[STATUS_MESSAGE_KEY] = ""
    state[ERROR_MESSAGE_KEY] = ""
    for key in list(state.keys()):
        if isinstance(key, str) and key.startswith(f"{APPROVAL_CONFIRM_PREFIX}{resolved_channel}_"):
            del state[key]


def mark_export_ready(state: MutableMapping[str, Any], export_record: Any, channel: str | None = None) -> None:
    resolved_channel = _resolve_channel(state, channel)
    state[export_record_key(resolved_channel)] = export_record


def get_export_record(state: MutableMapping[str, Any], channel: str | None = None) -> Any:
    resolved_channel = _resolve_channel(state, channel)
    return state.get(export_record_key(resolved_channel))


def editor_is_dirty(state: MutableMapping[str, Any], channel: str | None = None) -> bool:
    resolved_channel = _resolve_channel(state, channel)
    return state.get(editor_working_copy_key(resolved_channel), "") != state.get(editor_saved_copy_key(resolved_channel), "") or state.get(
        editor_working_notes_key(resolved_channel), ""
    ) != state.get(editor_saved_notes_key(resolved_channel), "")


def current_campaign_changed(state: MutableMapping[str, Any], channel: str, brief: str) -> bool:
    del channel
    current_brief = get_loaded_campaign_brief(state)
    return current_brief != brief.strip()


def source_inventory_signature(source_records: Any) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (
                getattr(record, "repository_relative_path"),
                getattr(record, "source_hash"),
            )
            for record in source_records
        )
    )


def set_brief_snapshot(state: MutableMapping[str, Any], snapshot: Any) -> None:
    state[BRIEF_SNAPSHOT_KEY] = snapshot


def get_brief_snapshot(state: MutableMapping[str, Any]) -> Any:
    return state.get(BRIEF_SNAPSHOT_KEY)


def set_source_inventory(
    state: MutableMapping[str, Any],
    *,
    source_records: Any,
    source_signature: Any | None = None,
    current: bool | None = None,
    error: str = "",
) -> None:
    state[SOURCE_INVENTORY_KEY] = tuple(source_records)
    state[SOURCE_INVENTORY_SIGNATURE_KEY] = (
        source_signature if source_signature is not None else source_inventory_signature(source_records)
    )
    state[SOURCE_INVENTORY_CURRENT_KEY] = current
    state[SOURCE_INVENTORY_ERROR_KEY] = error


def get_source_inventory(state: MutableMapping[str, Any]) -> tuple[Any, ...] | None:
    value = state.get(SOURCE_INVENTORY_KEY)
    return tuple(value) if isinstance(value, tuple) else None


def get_source_inventory_signature(state: MutableMapping[str, Any]) -> Any:
    return state.get(SOURCE_INVENTORY_SIGNATURE_KEY)


def source_inventory_is_current(state: MutableMapping[str, Any]) -> bool:
    return bool(state.get(SOURCE_INVENTORY_CURRENT_KEY))


def get_source_inventory_error(state: MutableMapping[str, Any]) -> str:
    error = state.get(SOURCE_INVENTORY_ERROR_KEY)
    return error if isinstance(error, str) else ""


def set_action_in_progress(state: MutableMapping[str, Any], action: str, in_progress: bool) -> None:
    state[action_in_progress_key(action)] = in_progress


def action_in_progress(state: MutableMapping[str, Any], action: str) -> bool:
    return bool(state.get(action_in_progress_key(action)))


def set_channel_source_signature(state: MutableMapping[str, Any], channel: str, source_signature: Any) -> None:
    state[channel_source_signature_key(channel)] = source_signature


def get_channel_source_signature(state: MutableMapping[str, Any], channel: str) -> Any:
    return state.get(channel_source_signature_key(channel))


def campaign_sources_are_stale(state: MutableMapping[str, Any], channel: str, current_source_signature: Any) -> bool:
    if not source_inventory_is_current(state):
        return True

    stored_signature = get_channel_source_signature(state, channel)
    if stored_signature is None:
        return False
    return stored_signature != current_source_signature


def set_pending_campaign_replacement(state: MutableMapping[str, Any], *, channel: str, brief: str) -> None:
    state[PENDING_CAMPAIGN_REPLACEMENT_KEY] = {"channel": channel, "brief": brief}


def get_pending_campaign_replacement(state: MutableMapping[str, Any]) -> dict[str, str] | None:
    pending = state.get(PENDING_CAMPAIGN_REPLACEMENT_KEY)
    return pending if isinstance(pending, dict) else None


def clear_pending_campaign_replacement(state: MutableMapping[str, Any]) -> None:
    state[PENDING_CAMPAIGN_REPLACEMENT_KEY] = None


def campaign_has_work(state: MutableMapping[str, Any]) -> bool:
    for channel in SUPPORTED_CHANNELS:
        session = get_channel_session(state, channel)
        if session is None:
            continue
        if getattr(session, "current_draft", None) is not None:
            return True
        if getattr(session, "approval", None) is not None:
            return True
        if getattr(session, "history", None):
            return True
        if getattr(session, "paid_attempts_used", 0):
            return True
    return False


def channel_status_label(state: MutableMapping[str, Any], channel: str) -> str:
    session = get_channel_session(state, channel)
    if session is None or getattr(session, "current_draft", None) is None:
        return "Not generated"
    approval = getattr(session, "approval", None)
    current_draft = session.current_draft
    status = "Approved" if approval is not None and approval.approved_revision == current_draft.revision_number else "Draft"
    if editor_is_dirty(state, channel):
        status = f"{status} - unsaved edits"
    return status


def campaign_status_summary(state: MutableMapping[str, Any]) -> str:
    return " | ".join(f"{channel_display_name(channel)}: {channel_status_label(state, channel)}" for channel in SUPPORTED_CHANNELS)


def loaded_campaign_summary(channel: str, brief: str) -> str:
    return f"{channel_display_name(channel)} - {brief.strip()}"


def loaded_campaign_preview(channel: str, brief: str, *, max_length: int = 120) -> str:
    normalized_brief = " ".join(brief.strip().split())
    if len(normalized_brief) > max_length:
        normalized_brief = normalized_brief[: max_length - 3].rstrip() + "..."
    return f"{channel_display_name(channel)} - {normalized_brief}"


def channel_display_name(channel: str) -> str:
    return CHANNEL_LABELS[channel]


def channel_from_display_name(display_name: str) -> str:
    for channel, label in CHANNEL_LABELS.items():
        if label == display_name:
            return channel
    raise KeyError(display_name)


def _resolve_channel(state: MutableMapping[str, Any], channel: str | None) -> str:
    if channel is not None:
        return channel
    active_channel = state.get(CAMPAIGN_CHANNEL_KEY)
    if isinstance(active_channel, str):
        return active_channel
    return DEFAULT_CHANNEL
