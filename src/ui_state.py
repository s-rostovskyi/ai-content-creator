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
CAMPAIGN_SIGNATURE_KEY = "campaign_signature"
CONTEXT_BUNDLE_KEY = "context_bundle"
PIPELINE_SESSION_KEY = "pipeline_session"
EXPORT_RECORD_KEY = "export_record"
STATUS_MESSAGE_KEY = "status_message"
ERROR_MESSAGE_KEY = "error_message"
EDITOR_COPY_KEY = "editor_copy_buffer"
EDITOR_NOTES_KEY = "editor_notes_buffer"
EDITOR_SAVED_COPY_KEY = "editor_saved_copy"
EDITOR_SAVED_NOTES_KEY = "editor_saved_notes"
EDITOR_PENDING_COPY_KEY = "editor_pending_copy"
EDITOR_PENDING_NOTES_KEY = "editor_pending_notes"
REVISION_FEEDBACK_KEY = "revision_feedback"
APPROVAL_CONFIRM_PREFIX = "approval_confirm_"

CHANNEL_LABELS = {
    "instagram": "Instagram",
    "linkedin": "LinkedIn",
    "email": "Email newsletter",
}


def campaign_signature(channel: str, brief: str) -> tuple[str, str]:
    return channel, brief.strip()


def initialize_state(state: MutableMapping[str, Any]) -> None:
    state.setdefault(CAMPAIGN_CHANNEL_KEY, None)
    state.setdefault(CAMPAIGN_BRIEF_KEY, None)
    state.setdefault(CAMPAIGN_SIGNATURE_KEY, None)
    state.setdefault(CONTEXT_BUNDLE_KEY, None)
    state.setdefault(PIPELINE_SESSION_KEY, None)
    state.setdefault(EXPORT_RECORD_KEY, None)
    state.setdefault(STATUS_MESSAGE_KEY, "")
    state.setdefault(ERROR_MESSAGE_KEY, "")
    state.setdefault(EDITOR_COPY_KEY, "")
    state.setdefault(EDITOR_NOTES_KEY, "")
    state.setdefault(EDITOR_SAVED_COPY_KEY, "")
    state.setdefault(EDITOR_SAVED_NOTES_KEY, "")
    state.setdefault(EDITOR_PENDING_COPY_KEY, None)
    state.setdefault(EDITOR_PENDING_NOTES_KEY, None)
    state.setdefault(REVISION_FEEDBACK_KEY, "")
    state.setdefault(CAMPAIGN_CHANNEL_INPUT_KEY, DEFAULT_CHANNEL)
    state.setdefault(CAMPAIGN_BRIEF_INPUT_KEY, DEFAULT_BRIEF)


def clear_runtime_state(state: MutableMapping[str, Any]) -> None:
    state[PIPELINE_SESSION_KEY] = None
    state[CAMPAIGN_SIGNATURE_KEY] = None
    clear_review_state(state)
    state[EDITOR_COPY_KEY] = ""
    state[EDITOR_NOTES_KEY] = ""
    state[EDITOR_SAVED_COPY_KEY] = ""
    state[EDITOR_SAVED_NOTES_KEY] = ""
    state[EDITOR_PENDING_COPY_KEY] = None
    state[EDITOR_PENDING_NOTES_KEY] = None
    state[REVISION_FEEDBACK_KEY] = ""


def install_campaign_session(state: MutableMapping[str, Any], *, channel: str, brief: str, session: Any) -> None:
    state[CAMPAIGN_CHANNEL_KEY] = channel
    state[CAMPAIGN_BRIEF_KEY] = brief
    state[CAMPAIGN_SIGNATURE_KEY] = campaign_signature(channel, brief)
    state[PIPELINE_SESSION_KEY] = session
    clear_review_state(state)
    state[EDITOR_COPY_KEY] = ""
    state[EDITOR_NOTES_KEY] = ""
    state[EDITOR_SAVED_COPY_KEY] = ""
    state[EDITOR_SAVED_NOTES_KEY] = ""
    state[EDITOR_PENDING_COPY_KEY] = None
    state[EDITOR_PENDING_NOTES_KEY] = None
    state[REVISION_FEEDBACK_KEY] = ""


def sync_editor_buffers(state: MutableMapping[str, Any], *, channel_copy: str, reviewer_notes: str) -> None:
    state[EDITOR_COPY_KEY] = channel_copy
    state[EDITOR_NOTES_KEY] = reviewer_notes
    state[EDITOR_SAVED_COPY_KEY] = channel_copy
    state[EDITOR_SAVED_NOTES_KEY] = reviewer_notes


def queue_editor_sync(state: MutableMapping[str, Any], *, channel_copy: str, reviewer_notes: str) -> None:
    state[EDITOR_PENDING_COPY_KEY] = channel_copy
    state[EDITOR_PENDING_NOTES_KEY] = reviewer_notes


def apply_pending_editor_sync(state: MutableMapping[str, Any]) -> bool:
    pending_copy = state.get(EDITOR_PENDING_COPY_KEY)
    pending_notes = state.get(EDITOR_PENDING_NOTES_KEY)
    if pending_copy is None and pending_notes is None:
        return False

    state[EDITOR_COPY_KEY] = "" if pending_copy is None else pending_copy
    state[EDITOR_NOTES_KEY] = "" if pending_notes is None else pending_notes
    state[EDITOR_SAVED_COPY_KEY] = state[EDITOR_COPY_KEY]
    state[EDITOR_SAVED_NOTES_KEY] = state[EDITOR_NOTES_KEY]
    state[EDITOR_PENDING_COPY_KEY] = None
    state[EDITOR_PENDING_NOTES_KEY] = None
    return True


def mark_export_ready(state: MutableMapping[str, Any], export_record: Any) -> None:
    state[EXPORT_RECORD_KEY] = export_record


def clear_review_state(state: MutableMapping[str, Any]) -> None:
    state[EXPORT_RECORD_KEY] = None
    state[STATUS_MESSAGE_KEY] = ""
    state[ERROR_MESSAGE_KEY] = ""
    for key in list(state.keys()):
        if isinstance(key, str) and key.startswith(APPROVAL_CONFIRM_PREFIX):
            del state[key]


def editor_is_dirty(state: MutableMapping[str, Any]) -> bool:
    return state.get(EDITOR_COPY_KEY, "") != state.get(EDITOR_SAVED_COPY_KEY, "") or state.get(
        EDITOR_NOTES_KEY, ""
    ) != state.get(EDITOR_SAVED_NOTES_KEY, "")


def current_campaign_changed(state: MutableMapping[str, Any], channel: str, brief: str) -> bool:
    return state.get(CAMPAIGN_SIGNATURE_KEY) != campaign_signature(channel, brief)


def loaded_campaign_summary(channel: str, brief: str) -> str:
    return f"{channel_display_name(channel)} - {brief.strip()}"


def loaded_campaign_preview(channel: str, brief: str, *, max_length: int = 120) -> str:
    normalized_brief = " ".join(brief.strip().split())
    if len(normalized_brief) > max_length:
        normalized_brief = normalized_brief[: max_length - 1].rstrip() + "?"
    return f"{channel_display_name(channel)} ? {normalized_brief}"


def channel_display_name(channel: str) -> str:
    return CHANNEL_LABELS[channel]


def channel_from_display_name(display_name: str) -> str:
    for channel, label in CHANNEL_LABELS.items():
        if label == display_name:
            return channel
    raise KeyError(display_name)
