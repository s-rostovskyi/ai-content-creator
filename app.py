from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.content_pipeline import (
    ApprovalError,
    ContentPipelineError,
    ExportError,
    PipelineSession,
    approve_current_draft,
    create_pipeline_session,
    edit_current_draft,
    export_approved_current_draft,
    generate_initial_draft,
    revise_current_draft,
)
from src.knowledge_base import MarkdownCorpusError, assemble_context_bundle
from src.llm_integration import OpenAIIntegrationError
from src.prompt_templates import PromptTemplateError
from src import ui_state

REPO_ROOT = Path(__file__).resolve().parent
APP_TITLE = "Patagonia Content Studio"
APP_SUBTITLE = "Unofficial educational prototype"
APP_PRODUCT_LINE = "Men's Nano Puff Jacket - Style 84212 - US"


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    ui_state.initialize_state(st.session_state)
    context_bundle = _ensure_context_bundle()

    st.title(APP_TITLE)
    st.caption(APP_SUBTITLE)
    st.write(APP_PRODUCT_LINE)

    left_column, right_column = st.columns([1, 2], gap="large")
    with left_column:
        _render_campaign_controls(context_bundle)
        _render_action_controls()

    with right_column:
        _render_workspace()


def _ensure_context_bundle():
    context_bundle = st.session_state.get(ui_state.CONTEXT_BUNDLE_KEY)
    if context_bundle is not None:
        return context_bundle

    try:
        context_bundle = assemble_context_bundle(REPO_ROOT)
    except MarkdownCorpusError:
        st.error("Could not load the knowledge base corpus.")
        st.stop()
    st.session_state[ui_state.CONTEXT_BUNDLE_KEY] = context_bundle
    return context_bundle


def _render_workspace() -> None:
    st.subheader("Draft workspace")
    session = st.session_state.get(ui_state.PIPELINE_SESSION_KEY)
    if session is None:
        st.info("No campaign session is loaded yet.")
        return

    st.caption(f"Loaded campaign: {ui_state.loaded_campaign_preview(session.channel, session.campaign_brief)}")

    with st.expander("Campaign details", expanded=False):
        st.write(f"Channel: {ui_state.channel_display_name(session.channel)}")
        st.write("Brief:")
        st.write(session.campaign_brief)

    draft = session.current_draft
    if draft is None:
        st.info("No draft yet. Generate a draft from the controls on the left.")
        return

    st.markdown("### Publishable copy")
    st.markdown(draft.channel_copy)

    with st.expander("Reviewer notes", expanded=False):
        st.markdown(draft.reviewer_notes or "_No reviewer notes supplied._")

    with st.expander("Sources", expanded=False):
        if not draft.source_manifest:
            st.write("No source manifest is available for this draft.")
        else:
            for entry in draft.source_manifest:
                st.markdown(f"- `{entry.repository_relative_path}` ? {entry.document_title}")
                st.caption(
                    f"{entry.knowledge_base} ? {entry.publisher} ? {entry.published_updated} ? {entry.accessed} ? {entry.evidence_type}"
                )
                if entry.source_urls:
                    for url in entry.source_urls:
                        st.write(url)

    if draft.response_metadata is not None:
        with st.expander("Response metadata", expanded=False):
            st.write(f"Response ID: {draft.response_metadata.response_id}")
            st.write(f"Model: {draft.response_metadata.model}")
            st.write(f"Elapsed seconds: {draft.response_metadata.elapsed_seconds:.3f}")
            if draft.response_metadata.usage is not None:
                st.json(draft.response_metadata.usage.__dict__)



def _render_campaign_controls(context_bundle) -> None:
    st.subheader("Campaign")
    with st.form("campaign-form", clear_on_submit=False):
        st.selectbox(
            "Channel",
            options=list(ui_state.CHANNEL_LABELS.keys()),
            format_func=ui_state.channel_display_name,
            key=ui_state.CAMPAIGN_CHANNEL_INPUT_KEY,
        )
        st.text_area(
            "Campaign brief",
            height=220,
            key=ui_state.CAMPAIGN_BRIEF_INPUT_KEY,
            help="Enter a short campaign brief before generating a draft.",
        )
        submitted = st.form_submit_button("Load campaign", key="load_campaign_button")

    if not submitted:
        return

    channel = st.session_state[ui_state.CAMPAIGN_CHANNEL_INPUT_KEY]
    brief = st.session_state[ui_state.CAMPAIGN_BRIEF_INPUT_KEY]
    session = st.session_state.get(ui_state.PIPELINE_SESSION_KEY)
    if session is not None and not ui_state.current_campaign_changed(st.session_state, channel, brief):
        st.success("This campaign is already loaded.")
        return

    try:
        session = _create_or_replace_session(channel, brief, context_bundle)
    except ContentPipelineError as exc:
        _show_error(exc)
        return

    ui_state.install_campaign_session(st.session_state, channel=channel, brief=brief, session=session)
    st.success(f"{ui_state.channel_display_name(channel)} campaign loaded.")


def _create_or_replace_session(channel: str, brief: str, context_bundle) -> PipelineSession:
    if ui_state.current_campaign_changed(st.session_state, channel, brief) or st.session_state.get(
        ui_state.PIPELINE_SESSION_KEY
    ) is None:
        ui_state.clear_runtime_state(st.session_state)
        return create_pipeline_session(channel, brief, context_bundle)
    session = st.session_state[ui_state.PIPELINE_SESSION_KEY]
    assert isinstance(session, PipelineSession)
    return session


def _render_action_controls() -> None:
    st.subheader("Actions")
    session = st.session_state.get(ui_state.PIPELINE_SESSION_KEY)
    if session is None:
        st.info("Load a campaign brief to enable generation, revision, approval and export.")
        return

    attempts_placeholder = st.empty()
    _render_remaining_attempts(attempts_placeholder, session)

    if st.button("Generate draft", key="generate_button", use_container_width=True, disabled=session.current_draft is not None):
        _run_generation(session)
        _render_remaining_attempts(attempts_placeholder, session)

    if session.current_draft is None:
        _render_remaining_attempts(attempts_placeholder, session)
        st.info("No draft yet. Use Generate draft to begin.")
        return

    st.divider()
    _render_revision_form(session, attempts_placeholder)
    _render_manual_editor(session)
    _render_approval_and_downloads(session)
    _render_remaining_attempts(attempts_placeholder, session)


def _render_remaining_attempts(placeholder, session: PipelineSession) -> None:
    placeholder.caption(f"Remaining generation attempts: {session.remaining_paid_attempts} of {session.max_paid_attempts}")


def _run_generation(session: PipelineSession) -> None:
    try:
        with st.spinner("Generating draft..."):
            draft = generate_initial_draft(session)
    except (ContentPipelineError, OpenAIIntegrationError, PromptTemplateError) as exc:
        _show_error(exc)
        return

    session.approval = None
    ui_state.sync_editor_buffers(
        st.session_state,
        channel_copy=draft.channel_copy,
        reviewer_notes=draft.reviewer_notes,
    )
    ui_state.clear_review_state(st.session_state)
    st.success("Draft generated.")


def _render_revision_form(session: PipelineSession, attempts_placeholder) -> None:
    st.subheader("Revision")
    with st.form("revision-form", clear_on_submit=False):
        st.text_area(
            "Feedback for the next revision",
            height=140,
            key=ui_state.REVISION_FEEDBACK_KEY,
            help="Describe the requested changes in plain language.",
        )
        submitted = st.form_submit_button("Revise draft", key="revise_button")

    if not submitted:
        return

    feedback = st.session_state[ui_state.REVISION_FEEDBACK_KEY]
    if not feedback.strip():
        st.warning("Enter feedback before requesting a revision.")
        return

    try:
        with st.spinner("Revising draft..."):
            draft = revise_current_draft(session, feedback)
    except (ContentPipelineError, OpenAIIntegrationError, PromptTemplateError) as exc:
        _show_error(exc)
        _render_remaining_attempts(attempts_placeholder, session)
        return

    session.approval = None
    ui_state.sync_editor_buffers(
        st.session_state,
        channel_copy=draft.channel_copy,
        reviewer_notes=draft.reviewer_notes,
    )
    ui_state.clear_review_state(st.session_state)
    st.success("Draft revised.")
    _render_remaining_attempts(attempts_placeholder, session)


def _render_manual_editor(session: PipelineSession) -> None:
    ui_state.apply_pending_editor_sync(st.session_state)

    st.subheader("Manual edit")
    st.text_area(
        "Channel copy",
        height=260,
        key=ui_state.EDITOR_COPY_KEY,
        help="Edit the exact publishable copy before saving.",
    )
    st.text_area(
        "Reviewer notes",
        height=120,
        key=ui_state.EDITOR_NOTES_KEY,
        help="Optional notes that travel with the current draft.",
    )

    dirty = ui_state.editor_is_dirty(st.session_state)
    if dirty:
        st.warning("Unsaved edits are pending. Save them before approving or downloading.")

    st.button(
        "Save edit",
        key="save_edit_button",
        use_container_width=True,
        disabled=not dirty,
        on_click=_save_manual_edit,
        args=(session,),
    )


def _save_manual_edit(session: PipelineSession) -> None:
    revised_copy = st.session_state[ui_state.EDITOR_COPY_KEY]
    revised_notes = st.session_state[ui_state.EDITOR_NOTES_KEY]
    try:
        with st.spinner("Saving edit..."):
            draft = edit_current_draft(
                session,
                revised_copy,
                revised_reviewer_notes=revised_notes,
            )
    except ContentPipelineError as exc:
        _show_error(exc)
        return

    session.approval = None
    ui_state.queue_editor_sync(
        st.session_state,
        channel_copy=draft.channel_copy,
        reviewer_notes=draft.reviewer_notes,
    )
    ui_state.clear_review_state(st.session_state)
    st.success("Manual edit saved.")


def _render_approval_and_downloads(session: PipelineSession) -> None:
    st.subheader("Approval and export")
    st.caption(f"Active campaign: {ui_state.channel_display_name(session.channel)}")

    draft = session.current_draft
    if draft is None:
        return

    dirty = ui_state.editor_is_dirty(st.session_state)
    approval = session.approval
    already_approved = approval is not None and approval.approved_revision == draft.revision_number

    if already_approved:
        st.success(f"Approved revision {draft.revision_number} by {approval.approved_by}.")
    else:
        approved = st.checkbox(
            f"I confirm revision {draft.revision_number} is the exact copy to approve.",
            key=f"approval_confirm_{draft.revision_number}",
            disabled=dirty,
        )
        if st.button("Approve draft", key="approve_button", use_container_width=True, disabled=dirty or not approved):
            _approve_and_export(session)
            approval = session.approval
            already_approved = approval is not None and approval.approved_revision == draft.revision_number

    export_record = st.session_state.get(ui_state.EXPORT_RECORD_KEY)
    if dirty:
        st.caption("Downloads appear after the current draft is approved and saved.")
        return
    if export_record is None:
        if session.approval is not None and already_approved:
            st.caption("The approved draft is ready to export.")
            if st.button("Retry export", key="retry_export_button", use_container_width=True):
                _retry_export(session)
                export_record = st.session_state.get(ui_state.EXPORT_RECORD_KEY)
                if export_record is None:
                    return
            else:
                return
        else:
            st.caption("Downloads appear after the current draft is approved and saved.")
            return

    try:
        markdown_data = export_record.markdown_path.read_text(encoding="utf-8")
        json_data = export_record.json_path.read_text(encoding="utf-8")
    except OSError:
        st.error("The exported files could not be read. You can retry the export.")
        if st.button("Retry export", key="retry_export_button", use_container_width=True):
            _retry_export(session)
            export_record = st.session_state.get(ui_state.EXPORT_RECORD_KEY)
            if export_record is None:
                return
            markdown_data = export_record.markdown_path.read_text(encoding="utf-8")
            json_data = export_record.json_path.read_text(encoding="utf-8")
        else:
            return

    st.download_button(
        "Download Markdown copy",
        key="download_markdown_button",
        data=markdown_data,
        file_name=export_record.markdown_path.name,
        mime="text/markdown",
        use_container_width=True,
    )
    st.download_button(
        "Download JSON metadata",
        key="download_json_button",
        data=json_data,
        file_name=export_record.json_path.name,
        mime="application/json",
        use_container_width=True,
    )


def _approve_and_export(session: PipelineSession) -> None:
    draft = session.current_draft
    if draft is None:
        _show_error(ContentPipelineError("No draft is available for approval."))
        return

    try:
        with st.spinner("Approving and exporting draft..."):
            approve_current_draft(
                session,
                approved_copy=draft.channel_copy,
                approved_revision=draft.revision_number,
            )
            _export_current_draft(session)
    except (ApprovalError, ExportError, ContentPipelineError) as exc:
        _show_error(exc)
        return


def _retry_export(session: PipelineSession) -> None:
    try:
        with st.spinner("Retrying export..."):
            _export_current_draft(session, success_message="Export refreshed.")
    except ExportError as exc:
        _show_error(exc)


def _export_current_draft(session: PipelineSession, *, success_message: str = "Draft approved and exported.") -> None:
    export_record = export_approved_current_draft(session)
    ui_state.mark_export_ready(st.session_state, export_record)
    st.success(success_message)


def _show_error(exc: Exception) -> None:
    st.error(f"Error: {exc}")


if __name__ == "__main__":
    main()
