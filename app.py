from __future__ import annotations

from pathlib import Path
import base64
import os
import re

from dotenv import load_dotenv
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
from src.campaign_brief import (
    PRIMARY_LABEL,
    SECONDARY_LABEL,
    get_campaign_angle_options,
    load_campaign_brief_snapshot,
    prepare_campaign_brief,
)
from src.knowledge_base import MarkdownCorpusError, assemble_context_bundle
from src.llm_integration import OpenAIIntegrationError
from src.prompt_templates import PromptTemplateError
from src.content_validation import format_validation_summary, validate_channel_format
from src import source_registry
from src import ui_state
from src import rag_context_provider
from src import rag_service

REPO_ROOT = Path(__file__).resolve().parent
load_dotenv(REPO_ROOT / ".env", override=False)
APP_TITLE = "Patagonia Content Studio"
APP_SUBTITLE = "Unofficial educational prototype"
APP_PRODUCT_LINE = "Men's Nano Puff Jacket \u00b7 Style 84212 \u00b7 US"
SOURCE_MANAGEMENT_ENABLED = os.getenv("SOURCE_MANAGEMENT_ENABLED", "").strip().lower() == "true"
SOURCE_UPLOAD_MAX_BYTES = source_registry.MAX_SOURCE_UPLOAD_BYTES
SOURCE_UPLOAD_MAX_MB = 1
SOURCE_CREATE_PREVIEW_KEY = "source_create_preview"
SOURCE_EDIT_PREVIEW_KEY = "source_edit_preview"
SOURCE_DELETE_PREVIEW_KEY = "source_delete_preview"
SOURCE_EDIT_LOADED_SOURCE_KEY = "source_edit_loaded_source"
SOURCE_CREATE_FILENAME_KEY = "source_create_filename"
SOURCE_CREATE_KB_KEY = "source_create_knowledge_base"
SOURCE_CREATE_UPLOAD_KEY = "source_create_upload"
SOURCE_EDIT_SOURCE_KEY = "source_edit_source"
SOURCE_EDIT_MARKDOWN_KEY = "source_edit_markdown"
SOURCE_DELETE_SOURCE_KEY = "source_delete_source"
SOURCE_DELETE_CONFIRM_KEY = "source_delete_confirm"
RAG_INDEX_PREVIEW_STATE_KEY = "rag_index_preview_state"
RAG_INDEX_BUILD_CONFIRM_KEY = "rag_index_build_confirm"
RAG_INDEX_BUILD_ACTION_KEY = "rag_index_build"
RAG_INDEX_MANAGE_SOURCES_EXPANDED_KEY = "rag_index_manage_sources_expanded"
RAG_INDEX_BUILD_SUMMARY_KEY = "rag_index_build_summary"



def _render_header() -> None:
    st.markdown(f"## {APP_TITLE}")
    st.caption(APP_SUBTITLE)
    st.markdown(f"**{APP_PRODUCT_LINE}**")


def _render_responsive_layout_styles() -> None:
    st.markdown(
        """<style>
@media (max-width: 800px) {
  section[data-testid="stMain"] div[data-testid="stHorizontalBlock"] {
    flex-direction: column;
  }

  section[data-testid="stMain"] div[data-testid="stHorizontalBlock"] > div {
    width: 100% !important;
    min-width: 0 !important;
  }
}
</style>""",
        unsafe_allow_html=True,
    )


HEADER_IMAGE_PATH = REPO_ROOT / "assets" / "outdoor-header-v1.png"
HEADER_IMAGE_HEIGHT = 160


def _render_header_image() -> None:
    if not HEADER_IMAGE_PATH.is_file():
        return

    try:
        image_bytes = HEADER_IMAGE_PATH.read_bytes()
    except OSError:
        return

    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    st.markdown(
        f"""<img
    src="data:image/png;base64,{encoded_image}"
    alt="AI-generated mountain landscape used as a decorative header image."
    style="display:block;width:100%;height:{HEADER_IMAGE_HEIGHT}px;object-fit:cover;object-position:center center;border-radius:0.5rem;border:1px solid rgba(0,0,0,0.12);"
  />""",
        unsafe_allow_html=True,
    )
    st.caption("AI-generated landscape")



def _build_rag_context_provider() -> rag_context_provider.LiveRagContextProvider:
    return rag_context_provider.LiveRagContextProvider(repo_root=REPO_ROOT)



def _get_rag_index_status(session: PipelineSession, *, revision_feedback: str = "") -> rag_context_provider.RagIndexStatus:
    provider = _build_rag_context_provider()
    return provider.describe_status(
        channel=session.channel,
        campaign_brief=session.campaign_brief,
        revision_feedback=revision_feedback,
    )



def _rag_status_action_hint(status: rag_context_provider.RagIndexStatus) -> str:
    if status.state == "missing":
        return "Build the local index with `python scripts/build_rag_index.py --live`."
    if status.state == "stale":
        return "Rebuild the local index with `python scripts/build_rag_index.py --live` after refreshing the corpus."
    if status.state == "incompatible":
        return "Set `OPENAI_EMBEDDING_MODEL` to match the local index or rebuild the index."
    return ""



def _rag_status_label(status: rag_context_provider.RagIndexStatus) -> str:
    labels = {
        "ready": "Ready",
        "missing": "Missing",
        "stale": "Stale",
        "incompatible": "Incompatible model/configuration",
    }
    return labels.get(status.state, status.state)



def _rag_status_is_ready(status: rag_context_provider.RagIndexStatus) -> bool:
    return status.state == "ready"



def _render_rag_index_status(status: rag_context_provider.RagIndexStatus) -> None:
    st.caption(f"RAG index status: {_rag_status_label(status)}")
    if status.state == "ready":
        return
    st.warning(status.message)
    action_hint = _rag_status_action_hint(status)
    if action_hint:
        st.caption(action_hint)
    if status.details:
        st.caption(status.details)



def _draft_context_mode(draft) -> str:
    context_mode = getattr(draft, "context_mode", "full_corpus")
    return context_mode if isinstance(context_mode, str) and context_mode else "full_corpus"



def _draft_retrieval_provenance(draft):
    provenance = getattr(draft, "retrieval_provenance", None)
    return provenance if isinstance(provenance, dict) else None



def _mapping_value(source, key: str, default=None):
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)



def _short_text_excerpt(text: str, *, limit: int = 180) -> str:
    compact = " ".join(str(text).split())
    if len(compact) <= limit:
        return compact
    return compact[: max(limit - 3, 1)].rstrip() + "..."



def _format_query_usage(usage) -> str:
    if not isinstance(usage, dict):
        return "none"
    return f"prompt_tokens={usage.get('prompt_tokens')}, total_tokens={usage.get('total_tokens')}"



def _render_rag_retrieval_details(draft) -> None:
    provenance = _draft_retrieval_provenance(draft)
    if not provenance:
        st.caption("No retrieval provenance is attached to this draft.")
        return

    manifest = provenance.get("manifest", {})
    measurements = provenance.get("measurements", {})
    retrieval_settings = provenance.get("retrieval_settings", {})
    included_chunks = tuple(provenance.get("included_chunks", ()))
    ranked_candidates = provenance.get("ranked_candidates", {})
    included_chunk_ids = {
        str(_mapping_value(chunk, "chunk_id", ""))
        for chunk in included_chunks
        if _mapping_value(chunk, "chunk_id", "")
    }
    omission_reason_map: dict[str, str] = {}
    for reason in manifest.get("omission_reasons", []):
        if isinstance(reason, str) and ":" in reason:
            chunk_id, omission_reason = reason.split(":", 1)
            omission_reason_map[chunk_id] = omission_reason

    st.caption(f"Corpus snapshot: {_mapping_value(provenance, 'corpus_snapshot_id', _mapping_value(manifest, 'corpus_snapshot_id', 'n/a'))}")
    st.caption(
        f"Requested embedding model: {_mapping_value(manifest, 'requested_model_id', 'n/a')} · "
        f"Returned embedding model: {_mapping_value(manifest, 'returned_model_id', 'n/a')}"
    )
    st.caption(f"Query usage: {_format_query_usage(manifest.get('query_usage'))}")
    query_latency = manifest.get("query_elapsed_seconds")
    if isinstance(query_latency, (int, float)):
        st.caption(f"Query latency: {query_latency:.3f} seconds")
    st.caption(
        "Context size: "
        f"{measurements.get('serialized_context_characters', 0)} / {measurements.get('max_serialized_characters', 0)} characters"
    )
    st.caption(
        "Selection counts: "
        f"primary={measurements.get('primary_selected_count', 0)} "
        f"(facts={measurements.get('primary_fact_count', 0)}), "
        f"secondary={measurements.get('secondary_selected_count', 0)} "
        f"(facts={measurements.get('secondary_fact_count', 0)}), "
        f"distinct sources={measurements.get('included_source_count', 0)}"
    )
    if retrieval_settings:
        st.caption(
            "Retrieval settings: "
            f"primary top-k {retrieval_settings.get('primary_top_k')} · "
            f"secondary top-k {retrieval_settings.get('secondary_top_k')} · "
            f"thresholds {retrieval_settings.get('primary_minimum_similarity')} / {retrieval_settings.get('secondary_minimum_similarity')}"
        )

    st.markdown("**Included chunks**")
    if not included_chunks:
        st.write("No chunks were included.")
    for chunk in included_chunks:
        source_path = str(_mapping_value(chunk, "source_path", _mapping_value(chunk, "repository_relative_path", "")))
        chunk_id = str(_mapping_value(chunk, "chunk_id", ""))
        knowledge_base = str(_mapping_value(chunk, "knowledge_base", ""))
        chunk_kind = str(_mapping_value(chunk, "chunk_kind", ""))
        similarity = _mapping_value(chunk, "similarity", 0.0)
        try:
            similarity_text = f"{float(similarity):.6f}"
        except (TypeError, ValueError):
            similarity_text = str(similarity)
        st.markdown(f"- `{source_path}` · `{chunk_id}` · {knowledge_base} · {chunk_kind} · score {similarity_text}")
        heading_path = _mapping_value(chunk, "section_heading_path", ())
        if heading_path:
            if isinstance(heading_path, (list, tuple)):
                heading_text = " / ".join(str(part) for part in heading_path)
            else:
                heading_text = str(heading_path)
            st.caption(f"Heading path: {heading_text}")
        line_range = _mapping_value(chunk, "chunk_line_range", ())
        if isinstance(line_range, (list, tuple)) and len(line_range) == 2:
            st.caption(f"Chunk lines: {line_range[0]}-{line_range[1]}")
        limitations = str(_mapping_value(chunk, "applicable_limitations", "")).strip()
        if limitations:
            st.caption(f"Limitations: {limitations}")
        excerpt = _short_text_excerpt(_mapping_value(chunk, "chunk_text", ""))
        if excerpt:
            st.write(excerpt)

    omitted_candidates: list[str] = []
    for pool_name, candidates in ranked_candidates.items():
        if not isinstance(candidates, (list, tuple)):
            continue
        for candidate in candidates:
            chunk_id = str(_mapping_value(candidate, "chunk_id", ""))
            if not chunk_id or chunk_id in included_chunk_ids:
                continue
            source_path = str(_mapping_value(candidate, "source_path", _mapping_value(candidate, "repository_relative_path", "")))
            chunk_kind = str(_mapping_value(candidate, "chunk_kind", ""))
            similarity = _mapping_value(candidate, "similarity", 0.0)
            try:
                similarity_text = f"{float(similarity):.6f}"
            except (TypeError, ValueError):
                similarity_text = str(similarity)
            reason = omission_reason_map.get(chunk_id, "ranked_out")
            omitted_candidates.append(
                f"- `{source_path}` · `{chunk_id}` · {pool_name} · {chunk_kind} · score {similarity_text} · {reason}"
            )
    if omitted_candidates:
        st.markdown("**Ranked but omitted**")
        for line in omitted_candidates:
            st.markdown(line)

    omission_reasons = tuple(manifest.get("omission_reasons", ()))
    if omission_reasons:
        st.caption("Omission reasons: " + ", ".join(str(reason) for reason in omission_reasons))


def _refresh_source_state() -> bool:
    cached_inventory = ui_state.get_source_inventory(st.session_state)
    cached_snapshot = ui_state.get_brief_snapshot(st.session_state)
    cached_bundle = st.session_state.get(ui_state.CONTEXT_BUNDLE_KEY)
    try:
        source_inventory = source_registry.list_sources(REPO_ROOT)
        brief_snapshot = load_campaign_brief_snapshot(REPO_ROOT)
        context_bundle = assemble_context_bundle(REPO_ROOT)
    except (MarkdownCorpusError, source_registry.SourceRegistryError) as exc:
        if cached_inventory is None or cached_snapshot is None or cached_bundle is None:
            st.error("Could not load the current source inventory.")
            st.stop()
        ui_state.set_source_inventory(
            st.session_state,
            source_records=cached_inventory,
            source_signature=ui_state.get_source_inventory_signature(st.session_state),
            current=False,
            error=str(exc),
        )
        ui_state.set_brief_snapshot(st.session_state, cached_snapshot)
        return False

    source_signature = ui_state.source_inventory_signature(source_inventory)
    ui_state.set_source_inventory(
        st.session_state,
        source_records=source_inventory,
        source_signature=source_signature,
        current=True,
        error="",
    )
    ui_state.set_brief_snapshot(st.session_state, brief_snapshot)
    st.session_state[ui_state.CONTEXT_BUNDLE_KEY] = context_bundle
    return True


def _source_records_by_knowledge_base(source_records):
    primary_records = tuple(record for record in source_records if record.knowledge_base == "primary")
    secondary_records = tuple(record for record in source_records if record.knowledge_base == "secondary")
    return primary_records, secondary_records


def _render_source_inventory_group(source_records) -> None:
    if not source_records:
        st.caption("No sources in this group.")
        return

    for record in source_records:
        with st.expander(f"{record.document_title} · {record.repository_relative_path}", expanded=False):
            st.caption(
                f"{record.knowledge_base} · {record.publisher} · {record.published_updated} · {record.accessed} · {record.evidence_type}"
            )
            st.caption(f"Sections: {record.section_count} · Source hash: {record.source_hash}")
            if record.source_urls:
                st.markdown("**Source URLs**")
                for url in record.source_urls:
                    st.write(url)


def _normalize_source_filename(raw_filename: str) -> str:
    filename = re.sub(r"[^A-Za-z0-9._-]+", "-", raw_filename.strip())
    filename = filename.strip("._-")
    if not filename:
        raise ValueError("Source filename must contain letters, numbers, dots, dashes, or underscores.")
    if not filename.lower().endswith(".md"):
        filename = f"{filename}.md"
    return filename


def _build_managed_source_id(knowledge_base: str, raw_filename: str) -> str:
    filename = _normalize_source_filename(raw_filename)
    return f"knowledge_base/{knowledge_base}/{filename}"


def _show_source_registry_error(exc: Exception, *, action: str) -> None:
    if isinstance(exc, source_registry.SourceConflictError):
        st.error(f"Conflict while {action}: {exc}")
    elif isinstance(exc, source_registry.SourceValidationError):
        st.error(f"Validation failed while {action}: {exc}")
    elif isinstance(exc, source_registry.SourcePathError):
        st.error(f"Invalid source path while {action}: {exc}")
    elif isinstance(exc, source_registry.SourceWriteError):
        st.error(f"Write failed while {action}: {exc}")
    elif isinstance(exc, source_registry.SourceNotFoundError):
        st.error(f"Source not found while {action}: {exc}")
    else:
        st.error(f"Source management failed while {action}: {exc}")


def _apply_prepared_source_operation(prepared_operation, *, action: str):
    if not SOURCE_MANAGEMENT_ENABLED:
        raise source_registry.SourceRegistryError(
            f"Source management is disabled in this deployment. {action} is unavailable."
        )
    return source_registry.apply_prepared_source_operation(prepared_operation, REPO_ROOT)


def _rag_index_preview_signature(plan) -> tuple[str, str, str, int, int]:
    return (
        str(plan.index_path),
        plan.corpus_snapshot.snapshot_id,
        plan.embedding_model_id or "unresolved",
        plan.chunking_policy.max_chunk_characters,
        plan.chunking_policy.overlap_characters,
    )



def _rag_index_status_from_build_plan(plan) -> rag_context_provider.RagIndexStatus:
    if plan.existing_index_matches is True:
        state = "ready"
        message = "RAG index ready."
    elif plan.existing_index_reason == "missing":
        state = "missing"
        message = f"No local RAG index was found at {plan.index_path}."
    elif plan.existing_index_reason == "snapshot_mismatch":
        state = "stale"
        message = "The local RAG index was built from an older source snapshot."
    else:
        state = "incompatible"
        message = "The local RAG index does not match the configured embedding model or settings."

    model_text = plan.embedding_model_id or "unresolved"
    details = (
        f"Index: {plan.index_path} | Corpus snapshot: {plan.corpus_snapshot.snapshot_id} | "
        f"Model: {model_text} | Existing index: {plan.existing_index_reason}"
    )
    return rag_context_provider.RagIndexStatus(
        state=state,
        message=message,
        details=details,
        index_path=plan.index_path,
        corpus_snapshot_id=plan.corpus_snapshot.snapshot_id,
        existing_index_matches=plan.existing_index_matches,
        existing_index_reason=plan.existing_index_reason,
        embedding_model_id=plan.embedding_model_id,
    )



def _render_rag_index_preview_details(plan) -> None:
    st.caption(f"Corpus snapshot: {plan.corpus_snapshot.snapshot_id}")
    st.caption(f"Chunk count: {plan.chunk_count}")
    st.caption(
        f"Reusable embeddings: {plan.reusable_embedding_count} | Missing embeddings: {plan.pending_embedding_count}"
    )
    if plan.planned_batches:
        st.caption(f"Planned batches: {len(plan.planned_batches)}")
        for index, batch in enumerate(plan.planned_batches, start=1):
            st.caption(
                f"Batch {index}: {len(batch.chunk_ids)} chunks | {batch.total_input_characters} characters"
            )
    else:
        st.caption("Planned batches: 0")



def _rag_index_usage_summary(result) -> dict[str, int] | None:
    usage_batches = [batch for batch in result.completed_batches if getattr(batch, "usage", None) is not None]
    if not usage_batches:
        return None
    return {
        "prompt_tokens": sum(batch.usage.prompt_tokens for batch in usage_batches),
        "total_tokens": sum(batch.usage.total_tokens for batch in usage_batches),
    }



def _rag_index_build_summary(*, status: rag_context_provider.RagIndexStatus, result=None, plan=None, error_message: str | None = None) -> dict[str, object]:
    summary: dict[str, object] = {
        "resulting_index_state": status.state,
        "resulting_index_status": _rag_status_label(status),
        "resulting_index_message": status.message,
        "index_path": str(status.index_path),
        "corpus_snapshot_id": status.corpus_snapshot_id,
    }
    if result is not None:
        summary.update(
            {
                "outcome": "success",
                "embedded_chunk_count": result.embedded_chunk_count,
                "reused_embedding_count": result.reused_embedding_count,
                "actual_api_batch_count": len(result.completed_batches),
                "elapsed_seconds": result.build_elapsed_seconds,
                "usage": _rag_index_usage_summary(result),
            }
        )
    elif plan is not None:
        summary.update(
            {
                "outcome": "failure",
                "embedded_chunk_count": None,
                "reused_embedding_count": None,
                "actual_api_batch_count": None,
                "elapsed_seconds": None,
                "usage": None,
                "planned_batch_count": len(plan.planned_batches),
            }
        )
    if error_message:
        summary["error_message"] = error_message
    return summary



def _render_rag_index_build_summary(summary: dict[str, object]) -> None:
    outcome = str(summary.get("outcome", "unknown"))
    st.markdown("##### Last build result")
    st.caption(f"Outcome: {outcome}")
    st.caption(f"Corpus snapshot: {summary.get('corpus_snapshot_id', 'unknown')}")
    embedded_chunk_count = summary.get("embedded_chunk_count")
    reused_embedding_count = summary.get("reused_embedding_count")
    actual_api_batch_count = summary.get("actual_api_batch_count")
    elapsed_seconds = summary.get("elapsed_seconds")
    usage = summary.get("usage")
    if embedded_chunk_count is None or reused_embedding_count is None or actual_api_batch_count is None or elapsed_seconds is None:
        st.caption("Embedded chunks: unavailable | Reused chunks: unavailable")
        st.caption("Actual API batches: unavailable | Elapsed: unavailable")
    else:
        st.caption(f"Embedded chunks: {embedded_chunk_count} | Reused chunks: {reused_embedding_count}")
        st.caption(f"Actual API batches: {actual_api_batch_count} | Elapsed: {elapsed_seconds:.3f}s")
    if isinstance(usage, dict):
        st.caption(f"Usage: prompt_tokens={usage['prompt_tokens']} | total_tokens={usage['total_tokens']}")
    elif outcome == "success":
        st.caption("Usage: none")
    st.caption(f"Resulting index status: {summary.get('resulting_index_status', 'unknown')}")
    if summary.get("error_message"):
        st.caption(f"Error: {summary['error_message']}")



def _store_rag_index_build_summary(*, status: rag_context_provider.RagIndexStatus, result=None, plan=None, error_message: str | None = None) -> None:
    st.session_state[RAG_INDEX_BUILD_SUMMARY_KEY] = _rag_index_build_summary(
        status=status,
        result=result,
        plan=plan,
        error_message=error_message,
    )



def _keep_manage_sources_expanded() -> None:
    st.session_state[RAG_INDEX_MANAGE_SOURCES_EXPANDED_KEY] = True



def _render_rag_index_build_result(result) -> None:
    st.caption(f"Embedded chunks: {result.embedded_chunk_count} | Reused chunks: {result.reused_embedding_count}")
    st.caption(f"Batches: {len(result.completed_batches)} | Elapsed: {result.build_elapsed_seconds:.3f}s")
    usage_batches = [batch for batch in result.completed_batches if getattr(batch, "usage", None) is not None]
    if not usage_batches:
        st.caption("Usage: none")
        return
    prompt_tokens = sum(batch.usage.prompt_tokens for batch in usage_batches)
    total_tokens = sum(batch.usage.total_tokens for batch in usage_batches)
    st.caption(f"Usage: prompt_tokens={prompt_tokens} | total_tokens={total_tokens}")



def _show_rag_index_error(exc: Exception, *, action: str) -> None:
    message = str(exc).strip() or exc.__class__.__name__
    st.error(f"RAG index {action} failed: {message}")
    st.caption("Existing index and campaign work were preserved.")



def _run_rag_index_build(plan) -> None:
    _keep_manage_sources_expanded()
    if not SOURCE_MANAGEMENT_ENABLED:
        raise rag_service.RagServiceError("Source management is disabled in this deployment. Index building is unavailable.")

    preview_state = st.session_state.get(RAG_INDEX_PREVIEW_STATE_KEY)
    signature = _rag_index_preview_signature(plan)
    if not isinstance(preview_state, dict) or preview_state.get("signature") != signature:
        st.warning("The index update preview is stale. Preview again before building the index.")
        st.session_state[RAG_INDEX_BUILD_CONFIRM_KEY] = False
        return

    if not st.session_state.get(RAG_INDEX_BUILD_CONFIRM_KEY, False):
        st.warning("Confirm the charge notice before building the index.")
        return

    ui_state.set_action_in_progress(st.session_state, RAG_INDEX_BUILD_ACTION_KEY, True)
    preview_plan = preview_state["plan"]
    try:
        with st.spinner("Building RAG index..."):
            result = rag_service.build_rag_index(repo_root=REPO_ROOT)
    except Exception as exc:  # noqa: BLE001
        _store_rag_index_build_summary(
            status=_rag_index_status_from_build_plan(plan),
            plan=preview_plan,
            error_message=str(exc).strip() or exc.__class__.__name__,
        )
        _show_rag_index_error(exc, action="building the RAG index")
        return
    finally:
        ui_state.set_action_in_progress(st.session_state, RAG_INDEX_BUILD_ACTION_KEY, False)
        st.session_state[RAG_INDEX_BUILD_CONFIRM_KEY] = False

    post_build_status = _rag_index_status_from_build_plan(rag_service.plan_rag_index_build(repo_root=REPO_ROOT))
    _store_rag_index_build_summary(status=post_build_status, result=result)
    st.success("RAG index updated.")
    _render_rag_index_build_summary(st.session_state[RAG_INDEX_BUILD_SUMMARY_KEY])



def _render_rag_index_refresh_panel(plan) -> None:
    st.markdown("##### RAG index refresh")
    st.caption(
        "Preview the current corpus snapshot offline before building the index. Previewing does not create an API client."
    )
    if st.button("Preview index update", key="rag_index_preview_button", use_container_width=True):
        _keep_manage_sources_expanded()
        st.session_state[RAG_INDEX_PREVIEW_STATE_KEY] = {
            "signature": _rag_index_preview_signature(plan),
            "plan": plan,
        }
        st.session_state[RAG_INDEX_BUILD_CONFIRM_KEY] = False
        st.success("Index update preview ready.")

    summary_state = st.session_state.get(RAG_INDEX_BUILD_SUMMARY_KEY)
    if isinstance(summary_state, dict):
        _render_rag_index_build_summary(summary_state)

    preview_state = st.session_state.get(RAG_INDEX_PREVIEW_STATE_KEY)
    if preview_state is None:
        st.caption("Preview the snapshot to review reusable embeddings, missing embeddings, and planned batches.")
        return

    current_signature = _rag_index_preview_signature(plan)
    if preview_state.get("signature") != current_signature:
        st.warning(
            "The sources or embedding configuration changed after the last preview. Preview again before building the index."
        )
        st.session_state[RAG_INDEX_BUILD_CONFIRM_KEY] = False
        _keep_manage_sources_expanded()
        return

    preview_plan = preview_state["plan"]
    _render_rag_index_preview_details(preview_plan)
    st.caption("Building may incur embedding API charges.")
    confirmed = st.checkbox(
        "I understand this build may incur embedding API charges.",
        key=RAG_INDEX_BUILD_CONFIRM_KEY,
    )
    build_disabled = ui_state.action_in_progress(st.session_state, RAG_INDEX_BUILD_ACTION_KEY) or not confirmed
    st.button(
        "Build/update index",
        key="rag_index_build_button",
        use_container_width=True,
        disabled=build_disabled,
        on_click=_run_rag_index_build,
        args=(preview_plan,),
    )


def _render_manage_sources_area(source_records) -> None:
    source_records = tuple(source_records or ())
    primary_records, secondary_records = _source_records_by_knowledge_base(source_records)
    plan = rag_service.plan_rag_index_build(repo_root=REPO_ROOT)
    status = _rag_index_status_from_build_plan(plan)

    with st.expander("Manage sources", expanded=st.session_state.get(RAG_INDEX_MANAGE_SOURCES_EXPANDED_KEY, False)):
        st.caption("Source management is a deployment safeguard, not user authentication.")
        if not ui_state.source_inventory_is_current(st.session_state):
            error_message = ui_state.get_source_inventory_error(st.session_state)
            st.warning(
                "The source inventory could not be refreshed. Existing campaign work is retained, but generation and revision are blocked until the sources are refreshed."
            )
            if error_message:
                st.caption(error_message)

        st.markdown(f"**Primary sources ({len(primary_records)})**")
        _render_source_inventory_group(primary_records)
        st.markdown(f"**Secondary sources ({len(secondary_records)})**")
        _render_source_inventory_group(secondary_records)
        _render_rag_index_status(status)

        if not SOURCE_MANAGEMENT_ENABLED:
            st.info("Source management is read-only in this deployment. Set SOURCE_MANAGEMENT_ENABLED=true to allow validated mutations.")
            return

        st.divider()
        _render_rag_index_refresh_panel(plan)
        st.divider()
        create_tab, edit_tab, delete_tab = st.tabs(["Create", "Edit", "Delete"])
        with create_tab:
            _render_source_create_panel()
        with edit_tab:
            _render_source_edit_panel(source_records)
        with delete_tab:
            _render_source_delete_panel(source_records)


def _render_source_create_panel() -> None:
    st.markdown("##### Create a source")
    st.caption("Upload UTF-8 Markdown, choose the knowledge base, then preview validation before creating the file.")
    uploaded_file = st.file_uploader(
        "Markdown source file",
        key=SOURCE_CREATE_UPLOAD_KEY,
        type=["md"],
        max_upload_size=SOURCE_UPLOAD_MAX_MB,
        help=f"Upload a UTF-8 Markdown source up to {SOURCE_UPLOAD_MAX_BYTES:,} bytes.",
    )
    knowledge_base = st.selectbox(
        "Knowledge base",
        options=["primary", "secondary"],
        key=SOURCE_CREATE_KB_KEY,
        help="Choose the corpus that should contain the uploaded source.",
    )
    filename = st.text_input(
        "Source filename",
        key=SOURCE_CREATE_FILENAME_KEY,
        help="Application-controlled filename only. Do not enter folders or an absolute path.",
    )
    preview_requested = st.button("Preview create", key="source_create_preview_button", use_container_width=True)

    preview_state = st.session_state.get(SOURCE_CREATE_PREVIEW_KEY)
    uploaded_bytes = uploaded_file.getvalue() if uploaded_file is not None else None
    if uploaded_bytes is not None and len(uploaded_bytes) > SOURCE_UPLOAD_MAX_BYTES:
        st.error(f"Markdown source files must be at most {SOURCE_UPLOAD_MAX_BYTES:,} bytes.")
        return

    source_id = None
    markdown_text = None
    if uploaded_file is not None and filename.strip():
        try:
            source_id = _build_managed_source_id(knowledge_base, filename)
            if uploaded_bytes is None:
                return
            markdown_text = uploaded_bytes.decode("utf-8")
        except UnicodeDecodeError:
            st.error("Uploaded files must be UTF-8 Markdown.")
            return
        except ValueError as exc:
            st.warning(str(exc))
            return

    if preview_requested:
        if uploaded_file is None:
            st.warning("Upload a Markdown file before previewing the create operation.")
        elif not filename.strip():
            st.warning("Enter a source filename before previewing the create operation.")
        elif markdown_text is None or source_id is None:
            return
        else:
            try:
                prepared_operation = source_registry.prepare_create_source(source_id, markdown_text, REPO_ROOT)
            except Exception as exc:  # noqa: BLE001
                _show_source_registry_error(exc, action="previewing the new source")
            else:
                st.session_state[SOURCE_CREATE_PREVIEW_KEY] = {
                    "source_id": source_id,
                    "markdown": markdown_text,
                    "prepared_operation": prepared_operation,
                }
                st.success(f"Create preview ready for {source_id}.")
                st.caption(f"Validated title: {prepared_operation.snapshot.document_title}")
                preview_state = st.session_state[SOURCE_CREATE_PREVIEW_KEY]

    if preview_state is None:
        return
    if source_id is None or markdown_text is None:
        st.session_state.pop(SOURCE_CREATE_PREVIEW_KEY, None)
        st.warning("The uploaded Markdown or filename is missing. Preview again before creating the source.")
        return
    if preview_state["source_id"] != source_id or preview_state["markdown"] != markdown_text:
        st.session_state.pop(SOURCE_CREATE_PREVIEW_KEY, None)
        st.warning("The filename or Markdown changed after the last preview. Preview again before creating the source.")
        return

    st.caption(f"Preview target: {preview_state['source_id']}")
    if st.button("Create source", key="source_create_apply_button", use_container_width=True):
        try:
            result = _apply_prepared_source_operation(preview_state["prepared_operation"], action="creating the source")
        except Exception as exc:  # noqa: BLE001
            _show_source_registry_error(exc, action="creating the source")
            return
        st.session_state.pop(SOURCE_CREATE_PREVIEW_KEY, None)
        st.success(f"Created {result.source_id}.")
        if not _refresh_source_state():
            st.warning(
                "The source inventory could not be refreshed after creating the source. Existing campaign work is retained, but generation and revision are blocked until the sources are refreshed."
            )


def _render_source_edit_panel(source_records) -> None:
    st.markdown("##### Edit a source")
    source_records = tuple(source_records or ())
    if not source_records:
        st.info("No sources are available to edit.")
        return

    source_ids = [record.repository_relative_path for record in source_records]
    if st.session_state.get(SOURCE_EDIT_SOURCE_KEY) not in source_ids:
        st.session_state[SOURCE_EDIT_SOURCE_KEY] = source_ids[0]
    selected_source_id = st.selectbox(
        "Source to edit",
        options=source_ids,
        key=SOURCE_EDIT_SOURCE_KEY,
    )
    if st.session_state.get(SOURCE_EDIT_LOADED_SOURCE_KEY) != selected_source_id:
        try:
            snapshot = source_registry.read_source(selected_source_id, REPO_ROOT)
        except Exception as exc:  # noqa: BLE001
            _show_source_registry_error(exc, action="loading the source for editing")
            return
        st.session_state[SOURCE_EDIT_LOADED_SOURCE_KEY] = selected_source_id
        st.session_state[SOURCE_EDIT_MARKDOWN_KEY] = snapshot.document.markdown
        st.session_state.pop(SOURCE_EDIT_PREVIEW_KEY, None)

    markdown_text = st.text_area(
        "Markdown",
        key=SOURCE_EDIT_MARKDOWN_KEY,
        height=320,
        help="Edit the source Markdown, then preview the change before saving.",
    )
    preview_requested = st.button("Preview edit", key="source_edit_preview_button", use_container_width=True)
    selected_record = next(record for record in source_records if record.repository_relative_path == selected_source_id)

    if preview_requested:
        try:
            prepared_operation = source_registry.prepare_edit_source(
                selected_source_id,
                markdown_text,
                selected_record.source_hash,
                REPO_ROOT,
            )
        except Exception as exc:  # noqa: BLE001
            _show_source_registry_error(exc, action="previewing the source edit")
        else:
            st.session_state[SOURCE_EDIT_PREVIEW_KEY] = {
                "source_id": selected_source_id,
                "markdown": markdown_text,
                "expected_hash": selected_record.source_hash,
                "prepared_operation": prepared_operation,
            }
            st.success(f"Edit preview ready for {selected_source_id}.")
            st.caption(f"Expected source hash: {selected_record.source_hash}")

    preview_state = st.session_state.get(SOURCE_EDIT_PREVIEW_KEY)
    if preview_state is None:
        return
    if preview_state["source_id"] != selected_source_id or preview_state["markdown"] != markdown_text:
        st.session_state.pop(SOURCE_EDIT_PREVIEW_KEY, None)
        st.warning("The selected source or Markdown changed after the last preview. Preview again before saving.")
        return

    st.caption(f"Preview target: {preview_state['source_id']}")
    if st.button("Save edited source", key="source_edit_apply_button", use_container_width=True):
        try:
            result = _apply_prepared_source_operation(preview_state["prepared_operation"], action="saving the source edit")
        except Exception as exc:  # noqa: BLE001
            _show_source_registry_error(exc, action="saving the source edit")
            return
        st.session_state.pop(SOURCE_EDIT_PREVIEW_KEY, None)
        st.success(f"Saved {result.source_id}.")
        if not _refresh_source_state():
            st.warning(
                "The source inventory could not be refreshed after saving the source. Existing campaign work is retained, but generation and revision are blocked until the sources are refreshed."
            )


def _render_source_delete_panel(source_records) -> None:
    st.markdown("##### Delete a source")
    source_records = tuple(source_records or ())
    if not source_records:
        st.info("No sources are available to delete.")
        return

    source_ids = [record.repository_relative_path for record in source_records]
    if st.session_state.get(SOURCE_DELETE_SOURCE_KEY) not in source_ids:
        st.session_state[SOURCE_DELETE_SOURCE_KEY] = source_ids[0]
    selected_source_id = st.selectbox(
        "Source to delete",
        options=source_ids,
        key=SOURCE_DELETE_SOURCE_KEY,
    )
    selected_record = next(record for record in source_records if record.repository_relative_path == selected_source_id)
    preview_requested = st.button("Preview delete", key="source_delete_preview_button", use_container_width=True)

    if preview_requested:
        try:
            prepared_operation = source_registry.prepare_delete_source(
                selected_source_id,
                selected_record.source_hash,
                REPO_ROOT,
            )
        except Exception as exc:  # noqa: BLE001
            _show_source_registry_error(exc, action="previewing the source deletion")
        else:
            st.session_state[SOURCE_DELETE_PREVIEW_KEY] = {
                "source_id": selected_source_id,
                "expected_hash": selected_record.source_hash,
                "prepared_operation": prepared_operation,
            }
            st.success(f"Delete preview ready for {selected_source_id}.")
            st.caption(f"Expected source hash: {selected_record.source_hash}")

    preview_state = st.session_state.get(SOURCE_DELETE_PREVIEW_KEY)
    if preview_state is None:
        return
    if preview_state["source_id"] != selected_source_id:
        st.session_state.pop(SOURCE_DELETE_PREVIEW_KEY, None)
        st.session_state.pop(SOURCE_DELETE_CONFIRM_KEY, None)
        st.warning("The selected source changed after the last preview. Preview again before deleting the source.")
        return

    st.caption(f"Preview target: {preview_state['source_id']}")
    confirm = st.checkbox(
        "I understand this deletes the selected source.",
        key=SOURCE_DELETE_CONFIRM_KEY,
    )
    if st.button("Delete source", key="source_delete_apply_button", use_container_width=True, disabled=not confirm):
        try:
            result = _apply_prepared_source_operation(preview_state["prepared_operation"], action="deleting the source")
        except Exception as exc:  # noqa: BLE001
            _show_source_registry_error(exc, action="deleting the source")
            return
        st.session_state.pop(SOURCE_DELETE_PREVIEW_KEY, None)
        st.session_state.pop(SOURCE_DELETE_CONFIRM_KEY, None)
        st.success(f"Deleted {result.source_id}.")
        if not _refresh_source_state():
            st.warning(
                "The source inventory could not be refreshed after deleting the source. Existing campaign work is retained, but generation and revision are blocked until the sources are refreshed."
            )



def _render_campaign_insights_and_brief() -> None:
    snapshot = ui_state.get_brief_snapshot(st.session_state)
    if snapshot is None:
        st.error("Could not load the knowledge base corpus for brief preparation.")
        st.stop()

    angle_options = get_campaign_angle_options()
    angle_labels = {option.key: option.label for option in angle_options}

    with st.expander("Insights & brief", expanded=False):
        st.caption(
            "Review the curated source snapshot, then prepare one editable brief for all three channels. "
            "Historical industry evidence is background only, not live monitoring or channel-performance data."
        )
        st.markdown(f"**{PRIMARY_LABEL}**")
        _render_brief_source_group(snapshot.primary_sources)
        st.markdown(f"**{SECONDARY_LABEL}**")
        _render_brief_source_group(snapshot.secondary_sources)
        st.divider()
        with st.form("brief_insights_form", clear_on_submit=False):
            st.selectbox(
                "Campaign angle",
                options=[option.key for option in angle_options],
                format_func=lambda key: angle_labels[key],
                key=ui_state.BRIEF_INSIGHT_ANGLE_KEY,
                help="Choose the editorial angle for the proposed brief.",
            )
            st.text_input(
                "Audience",
                key=ui_state.BRIEF_INSIGHT_AUDIENCE_KEY,
                help="Describe the audience in a sentence.",
            )
            st.text_area(
                "Campaign objective",
                height=96,
                key=ui_state.BRIEF_INSIGHT_OBJECTIVE_KEY,
                help="State the campaign objective in a sentence or two.",
            )
            prepared = st.form_submit_button("Prepare brief", key="prepare_brief_button", use_container_width=True)

        if prepared:
            try:
                proposal = prepare_campaign_brief(
                    snapshot,
                    st.session_state[ui_state.BRIEF_INSIGHT_ANGLE_KEY],
                    st.session_state[ui_state.BRIEF_INSIGHT_AUDIENCE_KEY],
                    st.session_state[ui_state.BRIEF_INSIGHT_OBJECTIVE_KEY],
                )
            except ValueError as exc:
                _show_error(exc)
            else:
                st.session_state[ui_state.BRIEF_INSIGHT_PROPOSAL_KEY] = proposal
                st.session_state[ui_state.BRIEF_INSIGHT_PROPOSAL_TEXT_KEY] = proposal.proposed_brief

        proposal = st.session_state.get(ui_state.BRIEF_INSIGHT_PROPOSAL_KEY)
        if proposal is None:
            return

        st.markdown("##### Prepared brief")
        st.caption(f"Angle: {proposal.angle_label} · Audience: {proposal.audience} · Objective: {proposal.objective}")
        st.markdown("**Source-supported focus**")
        for item in proposal.source_supported_focus:
            st.markdown(f"- {item}")
        st.markdown("**Editorial guidance**")
        for item in proposal.editorial_guidance:
            st.markdown(f"- {item}")
        st.text_area(
            "Prepared brief",
            key=ui_state.BRIEF_INSIGHT_PROPOSAL_TEXT_KEY,
            height=320,
            help="Edit the proposed shared brief before copying it into the campaign brief input.",
        )
        if st.button("Use this brief", key="use_prepared_brief_button", use_container_width=True):
            st.session_state[ui_state.CAMPAIGN_BRIEF_INPUT_KEY] = st.session_state[ui_state.BRIEF_INSIGHT_PROPOSAL_TEXT_KEY]
            st.success("Brief copied into the campaign brief input.")


def _render_brief_source_group(source_cards) -> None:
    for card in source_cards:
        _render_brief_source_card(card)



def _render_brief_source_card(card) -> None:
    with st.expander(f"{card.document_title} \u00b7 {card.repository_relative_path}", expanded=False):
        st.caption(
            f"{card.knowledge_base} \u00b7 {card.publisher} \u00b7 {card.published_updated} \u00b7 {card.accessed} \u00b7 {card.evidence_type}"
        )
        if card.source_urls:
            st.markdown("**Source URLs**")
            for url in card.source_urls:
                st.write(url)
        for preview in card.section_previews:
            st.markdown(f"**{preview.heading}**")
            st.markdown(preview.excerpt)
            with st.expander("Technical details", expanded=False):
                st.caption(
                    f"Source lines: {preview.line_range[0]}\u2013{preview.line_range[1]} (zero-based, end-exclusive)"
                )



def _render_format_feedback(draft, *, location: str) -> None:
    validation = validate_channel_format(draft.channel, draft.channel_copy)
    st.markdown("##### Format check")
    if location == "approval":
        st.caption(
            f"Validates the saved revision {draft.revision_number}. Save edits first to validate or approve the current working copy."
        )
    else:
        st.caption(
            f"Validates the saved revision {draft.revision_number}. Save edits first to validate or approve the current working copy."
        )
    st.caption(format_validation_summary(validation))
    if validation.warnings:
        st.warning(" ".join(validation.warnings))
    st.caption("Advisory only: passing format checks does not verify factual accuracy.")



def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="collapsed")
    ui_state.initialize_state(st.session_state)
    _refresh_source_state()
    context_bundle = _ensure_context_bundle()
    source_records = ui_state.get_source_inventory(st.session_state) or ()
    current_source_signature = ui_state.get_source_inventory_signature(st.session_state)

    _render_header()
    _render_header_image()
    _render_responsive_layout_styles()

    left_column, right_column = st.columns([0.9, 1.35], gap="large")
    with left_column:
        _render_campaign_insights_and_brief()
        _render_manage_sources_area(source_records)
        _render_campaign_controls(context_bundle, current_source_signature)

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
    session = st.session_state.get(ui_state.PIPELINE_SESSION_KEY)
    if session is None:
        st.markdown("#### Workspace")
        st.info("No campaign session is loaded yet.")
        return

    ui_state.apply_pending_editor_sync(st.session_state, session.channel)
    ui_state.hydrate_editor_buffers(st.session_state, session.channel)

    st.markdown("#### Workspace")
    st.caption(f"Loaded campaign: {ui_state.loaded_campaign_preview(session.channel, session.campaign_brief)}")
    st.caption(f"Channel status: {ui_state.channel_status_label(st.session_state, session.channel)}")
    with st.expander("Campaign details", expanded=False):
        st.write(f"Channel: {ui_state.channel_display_name(session.channel)}")
        st.write("Brief:")
        st.write(session.campaign_brief)

    workspace_view_key = ui_state.workspace_view_key(session.channel)
    workspace_view_widget_key = ui_state.workspace_view_widget_key(session.channel)
    if st.session_state.get(workspace_view_key) not in ui_state.WORKSPACE_VIEWS:
        st.session_state[workspace_view_key] = ui_state.DEFAULT_WORKSPACE_VIEW
    if st.session_state.get(workspace_view_widget_key) not in ui_state.WORKSPACE_VIEWS:
        st.session_state[workspace_view_widget_key] = st.session_state[workspace_view_key]
    workspace_view = st.radio(
        "Workspace view",
        options=ui_state.WORKSPACE_VIEWS,
        horizontal=True,
        key=workspace_view_widget_key,
    )
    ui_state.set_workspace_view(st.session_state, session.channel, workspace_view)
    if workspace_view == "Review":
        _render_review_panel(session)
    elif workspace_view == "Edit":
        _render_manual_editor(session)
    else:
        _render_draft_panel(session)


def _render_draft_panel(session: PipelineSession) -> None:
    draft = session.current_draft
    if draft is None:
        st.info("No draft yet. Generate a draft from the controls on the left.")
        return

    st.markdown("##### Publishable copy")
    st.markdown(draft.channel_copy)
    st.caption(f"Context mode: {_draft_context_mode(draft)}")
    if _draft_context_mode(draft) == "rag":
        with st.expander("Retrieval details", expanded=False):
            _render_rag_retrieval_details(draft)

    with st.expander("Reviewer notes", expanded=False):
        st.markdown(draft.reviewer_notes or "_No reviewer notes supplied._")

    if draft.response_metadata is not None:
        with st.expander("Response metadata", expanded=False):
            st.write(f"Response ID: {draft.response_metadata.response_id}")
            st.write(f"Model: {draft.response_metadata.model}")
            st.write(f"Elapsed seconds: {draft.response_metadata.elapsed_seconds:.3f}")
            if draft.response_metadata.usage is not None:
                st.json(draft.response_metadata.usage.__dict__)

    _render_format_feedback(draft, location="draft")
def _render_review_panel(session: PipelineSession) -> None:
    draft = session.current_draft
    if draft is None:
        st.info("Generate a draft to review sources, revision feedback and approvals.")
        return

    _render_revision_form(session)
    st.caption(f"Remaining generation attempts: {session.remaining_paid_attempts} of {session.max_paid_attempts}")
    st.caption(f"Context mode: {_draft_context_mode(draft)}")
    _render_format_feedback(draft, location="approval")

    with st.expander("Sources", expanded=False):
        if not draft.source_manifest:
            st.write("No source manifest is available for this draft.")
        else:
            for entry in draft.source_manifest:
                st.markdown(f"- `{entry.repository_relative_path}` - {entry.document_title}")
                st.caption(
                    f"{entry.knowledge_base} - {entry.publisher} - {entry.published_updated} - {entry.accessed} - {entry.evidence_type}"
                )
                if entry.source_urls:
                    for url in entry.source_urls:
                        st.write(url)

    if _draft_context_mode(draft) == "rag":
        with st.expander("Retrieval details", expanded=False):
            _render_rag_retrieval_details(draft)

    _render_approval_and_downloads(session)
def _render_campaign_controls(context_bundle, current_source_signature) -> None:
    st.markdown("#### Campaign")
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
        submitted = st.form_submit_button(
            "Load campaign",
            key="load_campaign_button",
            disabled=not ui_state.source_inventory_is_current(st.session_state),
        )

    if submitted:
        channel = st.session_state[ui_state.CAMPAIGN_CHANNEL_INPUT_KEY]
        brief = st.session_state[ui_state.CAMPAIGN_BRIEF_INPUT_KEY]
        try:
            load_message = _load_or_activate_campaign(channel, brief, context_bundle, current_source_signature)
        except ContentPipelineError as exc:
            _show_error(exc)
        else:
            if load_message is not None:
                st.success(load_message)

    session = st.session_state.get(ui_state.PIPELINE_SESSION_KEY)
    if session is not None:
        _render_generation_controls(session)

    if not ui_state.source_inventory_is_current(st.session_state):
        st.warning(
            "The source inventory could not be refreshed. Existing campaign work is retained, but generation and revision are blocked until the sources are refreshed."
        )
    elif session is not None and ui_state.campaign_sources_are_stale(st.session_state, session.channel, current_source_signature):
        st.warning(
            "This campaign was prepared from an older source snapshot. Refresh the campaign from current sources before generating or revising."
        )

    pending_replacement = ui_state.get_pending_campaign_replacement(st.session_state)
    if pending_replacement is not None:
        st.warning("Replacing the shared brief will reset all channel work.")
        st.caption(
            f"Replacement target: {ui_state.channel_display_name(pending_replacement['channel'])} · {pending_replacement['brief']}"
        )
        confirm_key = "replace_campaign_confirm"
        st.checkbox(
            "I understand this will reset all channel work.",
            key=confirm_key,
        )
        confirm_disabled = not st.session_state.get(confirm_key, False)
        confirm_column, cancel_column = st.columns(2)
        with confirm_column:
            if st.button("Replace campaign", key="replace_campaign_button", use_container_width=True, disabled=confirm_disabled):
                _confirm_campaign_replacement(context_bundle, current_source_signature)
        with cancel_column:
            if st.button("Cancel replacement", key="cancel_campaign_replace_button", use_container_width=True):
                ui_state.clear_pending_campaign_replacement(st.session_state)
                st.session_state.pop(confirm_key, None)

    st.caption(f"Channel statuses: {ui_state.campaign_status_summary(st.session_state)}")


def _load_or_activate_campaign(channel: str, brief: str, context_bundle, current_source_signature) -> str | None:
    if not ui_state.source_inventory_is_current(st.session_state):
        raise ContentPipelineError(
            "The current source inventory is unavailable. Refresh the sources before loading or replacing the campaign."
        )

    loaded_brief = ui_state.get_loaded_campaign_brief(st.session_state)
    normalized_brief = brief.strip()
    existing_session = ui_state.get_channel_session(st.session_state, channel)
    loaded_channel = st.session_state.get(ui_state.CAMPAIGN_CHANNEL_KEY)
    campaign_is_stale = ui_state.campaign_sources_are_stale(st.session_state, channel, current_source_signature)

    if loaded_brief is None:
        session = existing_session or create_pipeline_session(channel, normalized_brief, context_bundle)
        if existing_session is None:
            ui_state.install_campaign_session(
                st.session_state,
                channel=channel,
                brief=normalized_brief,
                session=session,
                source_signature=current_source_signature,
            )
        else:
            ui_state.activate_channel_session(st.session_state, channel)
            ui_state.set_channel_source_signature(st.session_state, channel, current_source_signature)
        ui_state.set_loaded_campaign(st.session_state, channel=channel, brief=normalized_brief)
        return f"{ui_state.channel_display_name(channel)} campaign loaded."

    if normalized_brief == loaded_brief:
        if campaign_is_stale:
            ui_state.set_pending_campaign_replacement(st.session_state, channel=channel, brief=normalized_brief)
            return None
        if existing_session is None:
            session = create_pipeline_session(channel, normalized_brief, context_bundle)
            ui_state.install_campaign_session(
                st.session_state,
                channel=channel,
                brief=normalized_brief,
                session=session,
                source_signature=current_source_signature,
            )
        else:
            ui_state.activate_channel_session(st.session_state, channel)
            ui_state.set_channel_source_signature(st.session_state, channel, current_source_signature)
        if loaded_channel == channel:
            return "This campaign is already loaded."
        return f"{ui_state.channel_display_name(channel)} campaign loaded."

    if ui_state.campaign_has_work(st.session_state):
        ui_state.set_pending_campaign_replacement(st.session_state, channel=channel, brief=normalized_brief)
        return None

    ui_state.clear_runtime_state(st.session_state)
    session = create_pipeline_session(channel, normalized_brief, context_bundle)
    ui_state.install_campaign_session(
        st.session_state,
        channel=channel,
        brief=normalized_brief,
        session=session,
        source_signature=current_source_signature,
    )
    return f"{ui_state.channel_display_name(channel)} campaign loaded."


def _confirm_campaign_replacement(context_bundle, current_source_signature) -> None:
    pending_replacement = ui_state.get_pending_campaign_replacement(st.session_state)
    if pending_replacement is None:
        return

    channel = pending_replacement["channel"]
    brief = pending_replacement["brief"]
    try:
        candidate_session = create_pipeline_session(channel, brief, context_bundle)
    except ContentPipelineError as exc:
        _show_error(exc)
        return

    ui_state.clear_runtime_state(st.session_state)
    ui_state.install_campaign_session(
        st.session_state,
        channel=channel,
        brief=brief,
        session=candidate_session,
        source_signature=current_source_signature,
    )
    ui_state.clear_pending_campaign_replacement(st.session_state)
    st.session_state.pop("replace_campaign_confirm", None)
    st.success(f"{ui_state.channel_display_name(channel)} campaign loaded.")


def _render_generation_controls(session: PipelineSession) -> None:
    source_signature = ui_state.get_source_inventory_signature(st.session_state)
    source_stale = ui_state.campaign_sources_are_stale(st.session_state, session.channel, source_signature)
    rag_status = _get_rag_index_status(session)
    _render_rag_index_status(rag_status)
    if source_stale:
        st.warning("This campaign was prepared from an older source snapshot. Refresh the campaign from current sources before generating or revising.")
    generate_disabled = (
        session.current_draft is not None
        or source_stale
        or not _rag_status_is_ready(rag_status)
        or ui_state.action_in_progress(st.session_state, "generation")
        or ui_state.action_in_progress(st.session_state, "revision")
    )
    if st.button(
        "Generate draft",
        key="generate_button",
        type="primary",
        use_container_width=True,
        disabled=generate_disabled,
    ):
        _run_generation(session)
def _run_generation(session: PipelineSession) -> None:
    source_signature = ui_state.get_source_inventory_signature(st.session_state)
    if ui_state.campaign_sources_are_stale(st.session_state, session.channel, source_signature):
        st.warning("This campaign was prepared from an older source snapshot. Refresh the campaign from current sources before generating or revising.")
        return

    rag_status = _get_rag_index_status(session)
    if not _rag_status_is_ready(rag_status):
        _render_rag_index_status(rag_status)
        return

    provider = _build_rag_context_provider()
    ui_state.set_action_in_progress(st.session_state, "generation", True)
    try:
        with st.spinner("Generating draft..."):
            draft = generate_initial_draft(session, context_provider=provider)
    except (ContentPipelineError, OpenAIIntegrationError, PromptTemplateError) as exc:
        _show_error(exc)
        return
    finally:
        ui_state.set_action_in_progress(st.session_state, "generation", False)

    session.approval = None
    ui_state.queue_editor_sync(
        st.session_state,
        channel=session.channel,
        channel_copy=draft.channel_copy,
        reviewer_notes=draft.reviewer_notes,
    )
    ui_state.clear_review_state(st.session_state, session.channel)
    st.success("Draft generated.")


def _run_revision(session: PipelineSession, feedback: str) -> None:
    source_signature = ui_state.get_source_inventory_signature(st.session_state)
    if ui_state.campaign_sources_are_stale(st.session_state, session.channel, source_signature):
        st.warning("This campaign was prepared from an older source snapshot. Refresh the campaign from current sources before generating or revising.")
        return

    rag_status = _get_rag_index_status(session, revision_feedback=feedback)
    if not _rag_status_is_ready(rag_status):
        _render_rag_index_status(rag_status)
        return

    provider = _build_rag_context_provider()
    ui_state.set_action_in_progress(st.session_state, "revision", True)
    try:
        with st.spinner("Revising draft..."):
            draft = revise_current_draft(session, feedback, context_provider=provider)
    except (ContentPipelineError, OpenAIIntegrationError, PromptTemplateError) as exc:
        _show_error(exc)
        return
    finally:
        ui_state.set_action_in_progress(st.session_state, "revision", False)

    session.approval = None
    ui_state.queue_editor_sync(
        st.session_state,
        channel=session.channel,
        channel_copy=draft.channel_copy,
        reviewer_notes=draft.reviewer_notes,
    )
    ui_state.clear_review_state(st.session_state, session.channel)
    st.success("Draft revised.")
def _render_revision_form(session: PipelineSession) -> None:
    st.markdown("##### Revision")
    ui_state.hydrate_revision_feedback(st.session_state, session.channel)
    st.text_area(
        "Feedback for the next revision",
        height=140,
        key=ui_state.revision_feedback_key(session.channel),
        help="Describe the requested changes in plain language.",
        on_change=_capture_revision_feedback,
        args=(session.channel,),
    )

    source_signature = ui_state.get_source_inventory_signature(st.session_state)
    source_stale = ui_state.campaign_sources_are_stale(st.session_state, session.channel, source_signature)
    rag_status = _get_rag_index_status(session, revision_feedback=st.session_state[ui_state.revision_feedback_key(session.channel)])
    _render_rag_index_status(rag_status)
    if source_stale:
        st.warning("This campaign was prepared from an older source snapshot. Refresh the campaign from current sources before generating or revising.")

    revision_disabled = (
        source_stale
        or not _rag_status_is_ready(rag_status)
        or ui_state.action_in_progress(st.session_state, "generation")
        or ui_state.action_in_progress(st.session_state, "revision")
    )
    if not st.button("Revise draft", key="revise_button", use_container_width=True, disabled=revision_disabled):
        return

    feedback = st.session_state[ui_state.revision_feedback_key(session.channel)]
    if not feedback.strip():
        st.warning("Enter feedback before requesting a revision.")
        return
    _run_revision(session, feedback)
def _render_manual_editor(session: PipelineSession) -> None:
    ui_state.apply_pending_editor_sync(st.session_state, session.channel)
    ui_state.hydrate_editor_buffers(st.session_state, session.channel)

    st.markdown("##### Manual edit")
    st.text_area(
        "Channel copy",
        height=260,
        key=ui_state.editor_copy_key(session.channel),
        help="Edit the exact publishable copy before saving.",
        on_change=_capture_editor_changes,
        args=(session.channel,),
    )
    st.text_area(
        "Reviewer notes",
        height=120,
        key=ui_state.editor_notes_key(session.channel),
        help="Optional notes that travel with the current draft.",
        on_change=_capture_editor_changes,
        args=(session.channel,),
    )

    dirty = ui_state.editor_is_dirty(st.session_state, session.channel)
    if session.current_draft is not None:
        st.caption(f"Saved revision: {session.current_draft.revision_number}")
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


def _capture_revision_feedback(channel: str) -> None:
    ui_state.record_revision_feedback(st.session_state, channel)


def _capture_editor_changes(channel: str) -> None:
    ui_state.record_editor_working_values(st.session_state, channel)


def _save_manual_edit(session: PipelineSession) -> None:
    revised_copy = st.session_state[ui_state.editor_copy_key(session.channel)]
    revised_notes = st.session_state[ui_state.editor_notes_key(session.channel)]
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
        channel=session.channel,
        channel_copy=draft.channel_copy,
        reviewer_notes=draft.reviewer_notes,
    )
    ui_state.clear_review_state(st.session_state, session.channel)
    st.success("Manual edit saved.")


def _render_approval_and_downloads(session: PipelineSession) -> None:
    st.markdown("##### Approval and export")
    st.caption(f"Active campaign: {ui_state.channel_display_name(session.channel)}")

    draft = session.current_draft
    if draft is None:
        return

    dirty = ui_state.editor_is_dirty(st.session_state, session.channel)
    approval = session.approval
    already_approved = approval is not None and approval.approved_revision == draft.revision_number

    if already_approved:
        st.success(f"Approved revision {draft.revision_number} by {approval.approved_by}.")
    else:
        approved = st.checkbox(
            f"I confirm revision {draft.revision_number} is the exact copy to approve.",
            key=ui_state.approval_confirm_key(session.channel, draft.revision_number),
            disabled=dirty,
        )
        if st.button("Approve draft", key="approve_button", use_container_width=True, disabled=dirty or not approved):
            _approve_and_export(session)
            approval = session.approval
            already_approved = approval is not None and approval.approved_revision == draft.revision_number

    export_record = ui_state.get_export_record(st.session_state, session.channel)
    if dirty:
        st.caption("Downloads appear after the current draft is approved and saved.")
        return
    if export_record is None:
        if session.approval is not None and already_approved:
            st.caption("The approved draft is ready to export.")
            if st.button("Retry export", key="retry_export_button", use_container_width=True):
                _retry_export(session)
                export_record = ui_state.get_export_record(st.session_state, session.channel)
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
            export_record = ui_state.get_export_record(st.session_state, session.channel)
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
    ui_state.mark_export_ready(st.session_state, export_record, session.channel)
    st.success(success_message)


def _show_error(exc: Exception) -> None:
    st.error(f"Error: {exc}")


if __name__ == "__main__":
    main()
