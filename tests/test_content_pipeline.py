import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import src.content_pipeline as pipeline
import src.main as pipeline_main
from src.content_pipeline import (
    ApprovalError,
    ContentPipelineError,
    DraftFormatError,
    ExportError,
    GenerationLimitExceededError,
    PipelineSession,
    ResolvedGenerationContext,
    approve_current_draft,
    create_pipeline_session,
    edit_current_draft,
    export_approved_current_draft,
    generate_initial_draft,
    revise_current_draft,
)
from src.document_processor import MarkdownCorpusError
from src.knowledge_base import ContextSourceManifestEntry, assemble_context_bundle
from src.llm_integration import GeneratedText, OpenAIConnectionError, UsageMetrics
from src.rag_retrieval import RetrievalBlockedError, RetrievalStaleCorpusError

BRIEF = (
    "Draft an Instagram caption introducing the Patagonia Men's Nano Puff Jacket, style 84212, to an "
    "English-speaking US audience planning everyday outings and outdoor trips. Focus on verified packability "
    "and practical features. Use the supplied industry context only where relevant; do not force statistics or "
    "competitor mentions into the caption. Avoid prices, discounts, urgency and unsupported environmental claims. "
    "Invite readers to explore the product details."
)

VALID_RESPONSE_ONE = """### CHANNEL COPY

Keep the shell near the door and you are ready for a walk, a rainy commute, or a spur-of-the-moment trip. Patagonia's Men's Nano Puff Jacket, style 84212, brings lightweight warmth and packable convenience without the bulk. Zippered handwarmer pockets and an adjustable hem keep it practical when plans change. Explore the product details.

### REVIEWER NOTES

- Supporting source paths: knowledge_base/primary/product_facts.md and knowledge_base/primary/repair_and_reuse.md.
- Facts used: style 84212, lightweight warmth, packability, handwarmer pockets, adjustable hem.
- Limitations: no prices, discounts, availability, or unsupported environmental claims.
"""

VALID_RESPONSE_TWO = """### CHANNEL COPY

When the forecast turns and plans stay flexible, this jacket is ready to go. Patagonia's Men's Nano Puff Jacket, style 84212, packs down small, delivers lightweight warmth, and keeps everyday outings simple. Zip the handwarmer pockets, adjust the hem, and head out. Explore the product details.

### REVIEWER NOTES

- Supporting source paths: knowledge_base/primary/product_facts.md.
- Facts used: packable build, lightweight warmth, zippered handwarmer pockets, adjustable hem.
- Limitations: still no prices, discounts, or unsupported environmental claims.
"""

MALFORMED_RESPONSE = """### CHANNEL COPY

Only copy, no notes.
"""


def _generated_text(text: str, *, response_id: str = "resp_123", model: str = "gpt-5.4-mini-2026-03-17", elapsed_seconds: float = 1.25) -> GeneratedText:
    usage = UsageMetrics(
        input_tokens=11,
        input_tokens_details={"cached_tokens": 3, "cache_write_tokens": 1},
        output_tokens=7,
        output_tokens_details={"reasoning_tokens": 2},
        total_tokens=18,
    )
    return GeneratedText(
        generated_text=text,
        response_id=response_id,
        model=model,
        elapsed_seconds=elapsed_seconds,
        usage=usage,
    )


def _fake_generator_factory(responses: list[GeneratedText], calls: list[dict[str, object]]):
    def fake_generation_function(**kwargs):
        calls.append(kwargs)
        if not responses:
            raise AssertionError("fake generation function was called too many times")
        return responses.pop(0)

    return fake_generation_function


def _make_rag_prompt_context() -> SimpleNamespace:
    return SimpleNamespace(
        primary_context="RAG PRIMARY CONTEXT",
        secondary_context="RAG SECONDARY CONTEXT",
        source_manifest=(
            ContextSourceManifestEntry(
                repository_relative_path="knowledge_base/primary/rag-context.md",
                knowledge_base="primary",
                document_title="RAG Context",
                source_urls=("https://example.com/rag-context",),
                source_url_text="https://example.com/rag-context",
                publisher="Patagonia",
                published_updated="2026-10-22",
                accessed="2026-10-23",
                evidence_type="official statement",
                section_count=1,
            ),
        ),
    )


@dataclass
class _FakeContextProvider:
    prompt_context: object
    context_mode: str = "rag"
    retrieval_provenance: dict[str, object] | None = None
    error: Exception | None = None
    calls: list[dict[str, object]] = field(default_factory=list)

    def resolve(self, session, *, revision_feedback: str = "", current_draft=None):
        self.calls.append(
            {
                "revision_feedback": revision_feedback,
                "current_draft_revision": None if current_draft is None else current_draft.revision_number,
            }
        )
        if self.error is not None:
            raise self.error
        return ResolvedGenerationContext(
            context_mode=self.context_mode,
            prompt_context=self.prompt_context,
            retrieval_provenance=self.retrieval_provenance,
        )


def test_initial_generation_parses_sections_and_preserves_metadata() -> None:
    context_bundle = assemble_context_bundle(REPO_ROOT)
    session = create_pipeline_session("instagram", BRIEF, context_bundle)
    calls: list[dict[str, object]] = []
    fake_generation_function = _fake_generator_factory([_generated_text(VALID_RESPONSE_ONE)], calls)

    draft = generate_initial_draft(session, generation_function=fake_generation_function)

    assert draft.revision_number == 1
    assert draft.origin == "generation"
    assert draft.raw_response == VALID_RESPONSE_ONE
    assert draft.channel_copy.startswith("Keep the shell near the door")
    assert "Reviewer notes" not in draft.channel_copy
    assert draft.reviewer_notes.startswith("- Supporting source paths")
    assert draft.source_manifest == context_bundle.source_manifest
    assert draft.response_metadata is not None
    assert draft.response_metadata.response_id == "resp_123"
    assert draft.response_metadata.model == "gpt-5.4-mini-2026-03-17"
    assert draft.response_metadata.usage is not None
    assert draft.response_metadata.usage.total_tokens == 18
    assert draft.context_mode == "full_corpus"
    assert draft.retrieval_provenance is None
    assert session.current_draft == draft
    assert session.history == [draft]
    assert session.paid_attempts_used == 1
    assert session.remaining_paid_attempts == 2
    assert BRIEF in calls[0]["user_input"]
    assert "### Context mode\nfull_corpus" in calls[0]["user_input"]
    assert "Reviewer feedback" in calls[0]["user_input"]


def test_revision_includes_previous_copy_and_feedback_in_untrusted_input() -> None:
    context_bundle = assemble_context_bundle(REPO_ROOT)
    session = create_pipeline_session("instagram", BRIEF, context_bundle)
    calls: list[dict[str, object]] = []
    fake_generation_function = _fake_generator_factory(
        [_generated_text(VALID_RESPONSE_ONE, response_id="resp_init"), _generated_text(VALID_RESPONSE_TWO, response_id="resp_rev")],
        calls,
    )

    first_draft = generate_initial_draft(session, generation_function=fake_generation_function)
    revised_draft = revise_current_draft(session, "Tighten the CTA and keep the tone a little more direct.", generation_function=fake_generation_function)

    assert revised_draft.revision_number == 2
    assert revised_draft.origin == "revision"
    assert session.current_draft == revised_draft
    assert session.history == [first_draft, revised_draft]
    assert session.paid_attempts_used == 2
    revision_prompt = calls[1]["user_input"]
    assert first_draft.channel_copy in revision_prompt
    assert "Tighten the CTA and keep the tone a little more direct." in revision_prompt
    assert "## Current channel copy" in revision_prompt
    assert "## Human feedback" in revision_prompt


def test_malformed_output_rejected_and_previous_draft_remains_intact() -> None:
    context_bundle = assemble_context_bundle(REPO_ROOT)
    session = create_pipeline_session("instagram", BRIEF, context_bundle)
    calls: list[dict[str, object]] = []
    fake_generation_function = _fake_generator_factory(
        [_generated_text(VALID_RESPONSE_ONE, response_id="resp_init"), _generated_text(MALFORMED_RESPONSE, response_id="resp_bad")],
        calls,
    )

    original_draft = generate_initial_draft(session, generation_function=fake_generation_function)

    with pytest.raises(DraftFormatError):
        revise_current_draft(session, "Please add the missing notes section.", generation_function=fake_generation_function)

    assert session.current_draft == original_draft
    assert session.history == [original_draft]
    assert session.paid_attempts_used == 2


def test_approval_requires_exact_current_copy_and_is_invalidated_after_edit_and_revision() -> None:
    context_bundle = assemble_context_bundle(REPO_ROOT)
    session = create_pipeline_session("instagram", BRIEF, context_bundle)
    calls: list[dict[str, object]] = []
    fake_generation_function = _fake_generator_factory(
        [_generated_text(VALID_RESPONSE_ONE, response_id="resp_init"), _generated_text(VALID_RESPONSE_TWO, response_id="resp_rev")],
        calls,
    )

    draft = generate_initial_draft(session, generation_function=fake_generation_function)
    approval = approve_current_draft(session, approved_copy=draft.channel_copy, approved_revision=draft.revision_number)
    assert session.approval == approval

    with pytest.raises(ApprovalError):
        approve_current_draft(session, approved_copy="wrong copy", approved_revision=draft.revision_number)

    edited_draft = edit_current_draft(session, draft.channel_copy + "\nEdited line.")
    assert edited_draft.revision_number == 2
    assert session.approval is None

    reapproved = approve_current_draft(
        session,
        approved_copy=edited_draft.channel_copy,
        approved_revision=edited_draft.revision_number,
    )
    assert session.approval == reapproved

    revised_draft = revise_current_draft(session, "Change the opening sentence slightly.", generation_function=fake_generation_function)
    assert revised_draft.revision_number == 3
    assert session.approval is None



def test_failed_revision_consumes_attempt_budget_and_preserves_previous_draft() -> None:
    context_bundle = assemble_context_bundle(REPO_ROOT)
    session = create_pipeline_session("instagram", BRIEF, context_bundle)
    calls: list[dict[str, object]] = []
    fake_generation_function = _fake_generator_factory(
        [_generated_text(VALID_RESPONSE_ONE, response_id="resp_init"), _generated_text(MALFORMED_RESPONSE, response_id="resp_bad")],
        calls,
    )

    original_draft = generate_initial_draft(session, generation_function=fake_generation_function)

    with pytest.raises(DraftFormatError):
        revise_current_draft(session, "Keep everything else the same.", generation_function=fake_generation_function)

    assert session.current_draft == original_draft
    assert session.paid_attempts_used == 2


def test_paid_attempt_limit_stops_after_one_generation_and_two_revisions() -> None:
    context_bundle = assemble_context_bundle(REPO_ROOT)
    session = create_pipeline_session("instagram", BRIEF, context_bundle)
    calls: list[dict[str, object]] = []
    fake_generation_function = _fake_generator_factory(
        [
            _generated_text(VALID_RESPONSE_ONE, response_id="resp_init"),
            _generated_text(VALID_RESPONSE_TWO, response_id="resp_rev1"),
            _generated_text(VALID_RESPONSE_ONE, response_id="resp_rev2"),
        ],
        calls,
    )

    generate_initial_draft(session, generation_function=fake_generation_function)
    revise_current_draft(session, "First revision", generation_function=fake_generation_function)
    revise_current_draft(session, "Second revision", generation_function=fake_generation_function)

    with pytest.raises(GenerationLimitExceededError):
        revise_current_draft(session, "Third revision should fail", generation_function=fake_generation_function)

    assert len(calls) == 3
    assert session.paid_attempts_used == 3


def test_initial_generation_uses_rag_context_provider_and_labels_context_mode() -> None:
    session_context = SimpleNamespace(
        primary_context="LEGACY FULL PRIMARY CONTEXT",
        secondary_context="LEGACY FULL SECONDARY CONTEXT",
        source_manifest=(),
    )
    session = create_pipeline_session("instagram", BRIEF, session_context)
    rag_context = _make_rag_prompt_context()
    provenance = {
        "query_digest": "rag-digest",
        "retrieval_settings": {
            "primary_top_k": 2,
            "secondary_top_k": 1,
            "max_context_characters": 6000,
        },
        "query_usage": {"input_tokens": 5, "total_tokens": 5},
        "query_elapsed_seconds": 0.25,
    }
    provider = _FakeContextProvider(prompt_context=rag_context, retrieval_provenance=provenance)
    calls: list[dict[str, object]] = []
    fake_generation_function = _fake_generator_factory([_generated_text(VALID_RESPONSE_ONE)], calls)

    draft = generate_initial_draft(
        session,
        context_provider=provider,
        generation_function=fake_generation_function,
    )

    assert provider.calls == [{"revision_feedback": "", "current_draft_revision": None}]
    assert draft.context_mode == "rag"
    assert draft.retrieval_provenance == provenance
    assert draft.source_manifest == rag_context.source_manifest
    assert "### Context mode\nrag" in calls[0]["user_input"]
    assert "RAG PRIMARY CONTEXT" in calls[0]["user_input"]
    assert "LEGACY FULL PRIMARY CONTEXT" not in calls[0]["user_input"]


def test_revision_feedback_participates_in_retrieval_context_provider() -> None:
    session_context = SimpleNamespace(
        primary_context="LEGACY FULL PRIMARY CONTEXT",
        secondary_context="LEGACY FULL SECONDARY CONTEXT",
        source_manifest=(),
    )
    session = create_pipeline_session("instagram", BRIEF, session_context)
    provider = _FakeContextProvider(
        prompt_context=_make_rag_prompt_context(),
        retrieval_provenance={"query_digest": "rag-digest"},
    )
    calls: list[dict[str, object]] = []
    fake_generation_function = _fake_generator_factory(
        [_generated_text(VALID_RESPONSE_ONE, response_id="resp_init"), _generated_text(VALID_RESPONSE_TWO, response_id="resp_rev")],
        calls,
    )

    first_draft = generate_initial_draft(
        session,
        context_provider=provider,
        generation_function=fake_generation_function,
    )
    revised_draft = revise_current_draft(
        session,
        "Make the opening more direct and keep the same facts.",
        context_provider=provider,
        generation_function=fake_generation_function,
    )

    assert "Make the opening more direct and keep the same facts." in provider.calls[1]["revision_feedback"]
    assert first_draft.channel_copy in provider.calls[1]["revision_feedback"]
    assert revised_draft.context_mode == "rag"
    assert "### Context mode\nrag" in calls[1]["user_input"]


def test_blocked_rag_retrieval_consumes_attempt_and_skips_generation() -> None:
    session_context = SimpleNamespace(
        primary_context="LEGACY FULL PRIMARY CONTEXT",
        secondary_context="LEGACY FULL SECONDARY CONTEXT",
        source_manifest=(),
    )
    session = create_pipeline_session("instagram", BRIEF, session_context)
    provider = _FakeContextProvider(
        prompt_context=_make_rag_prompt_context(),
        error=RetrievalBlockedError("blocked"),
    )
    calls: list[dict[str, object]] = []
    fake_generation_function = _fake_generator_factory([_generated_text(VALID_RESPONSE_ONE)], calls)

    with pytest.raises(RetrievalBlockedError):
        generate_initial_draft(
            session,
            context_provider=provider,
            generation_function=fake_generation_function,
        )

    assert provider.calls == [{"revision_feedback": "", "current_draft_revision": None}]
    assert session.paid_attempts_used == 1
    assert session.current_draft is None
    assert len(calls) == 0


def test_stale_rag_retrieval_preserves_draft_and_approval_on_revision() -> None:
    session_context = SimpleNamespace(
        primary_context="LEGACY FULL PRIMARY CONTEXT",
        secondary_context="LEGACY FULL SECONDARY CONTEXT",
        source_manifest=(),
    )
    session = create_pipeline_session("instagram", BRIEF, session_context)
    initial_provider = _FakeContextProvider(
        prompt_context=_make_rag_prompt_context(),
        retrieval_provenance={"query_digest": "rag-digest"},
    )
    failing_provider = _FakeContextProvider(
        prompt_context=_make_rag_prompt_context(),
        error=RetrievalStaleCorpusError("stale"),
    )
    calls: list[dict[str, object]] = []
    fake_generation_function = _fake_generator_factory([_generated_text(VALID_RESPONSE_ONE, response_id="resp_init")], calls)

    original_draft = generate_initial_draft(
        session,
        context_provider=initial_provider,
        generation_function=fake_generation_function,
    )
    approval = approve_current_draft(session, approved_copy=original_draft.channel_copy, approved_revision=original_draft.revision_number)

    with pytest.raises(RetrievalStaleCorpusError):
        revise_current_draft(
            session,
            "Update the CTA and keep the packability fact.",
            context_provider=failing_provider,
            generation_function=fake_generation_function,
        )

    assert session.current_draft == original_draft
    assert session.approval == approval
    assert session.paid_attempts_used == 2
    assert len(calls) == 1


def test_export_writes_unique_files_and_keeps_notes_separate_from_copy(tmp_path: Path) -> None:
    context_bundle = assemble_context_bundle(REPO_ROOT)
    session = create_pipeline_session("instagram", BRIEF, context_bundle)
    calls: list[dict[str, object]] = []
    fake_generation_function = _fake_generator_factory([_generated_text(VALID_RESPONSE_ONE)], calls)

    draft = generate_initial_draft(session, generation_function=fake_generation_function)
    approve_current_draft(session, approved_copy=draft.channel_copy, approved_revision=draft.revision_number)

    first_export = export_approved_current_draft(session, output_directory=tmp_path)
    second_export = export_approved_current_draft(session, output_directory=tmp_path)

    assert first_export.markdown_path != second_export.markdown_path
    assert first_export.json_path != second_export.json_path
    assert first_export.markdown_path.exists()
    assert first_export.json_path.exists()
    assert second_export.markdown_path.exists()
    assert second_export.json_path.exists()

    markdown_text = first_export.markdown_path.read_text(encoding="utf-8")
    sidecar = json.loads(first_export.json_path.read_text(encoding="utf-8"))

    assert markdown_text.strip() == draft.channel_copy.strip()
    assert draft.reviewer_notes not in markdown_text
    assert sidecar["reviewer_notes"] == draft.reviewer_notes
    assert sidecar["revision_number"] == draft.revision_number
    assert sidecar["approval"]["approved_revision"] == draft.revision_number
    assert sidecar["source_manifest"]
    assert sidecar["context_mode"] == "full_corpus"
    assert sidecar["retrieval_provenance"] is None
    assert sidecar["response_metadata"]["response_id"] == "resp_123"



def test_export_requires_approval() -> None:
    context_bundle = assemble_context_bundle(REPO_ROOT)
    session = create_pipeline_session("instagram", BRIEF, context_bundle)
    calls: list[dict[str, object]] = []
    fake_generation_function = _fake_generator_factory([_generated_text(VALID_RESPONSE_ONE)], calls)

    generate_initial_draft(session, generation_function=fake_generation_function)

    with pytest.raises(ExportError):
        export_approved_current_draft(session)



def test_revision_failure_followed_by_manual_edit_remains_usable(monkeypatch) -> None:
    edited = SimpleNamespace(revision_number=2, channel_copy="Edited copy", reviewer_notes="Edited notes")

    def fake_generate_initial_draft(session):
        draft = SimpleNamespace(revision_number=1, channel_copy="Initial copy", reviewer_notes="Initial notes")
        session.current_draft = draft
        session.history = [draft]
        return draft

    monkeypatch.setattr(pipeline_main, "generate_initial_draft", fake_generate_initial_draft)
    monkeypatch.setattr(pipeline_main, "revise_current_draft", lambda *args, **kwargs: (_ for _ in ()).throw(GenerationLimitExceededError("limit reached")))
    monkeypatch.setattr(pipeline_main, "edit_current_draft", lambda *args, **kwargs: edited)

    prompts: list[str] = []
    responses = iter(["r", "Need a shorter opening.", "e", "Edited copy", "END", "", "q"] )

    def fake_input(prompt: str = "") -> str:
        prompts.append(prompt)
        return next(responses)

    output: list[str] = []
    exit_code = pipeline_main.run_cli(
        ["--channel", "instagram", "--brief", BRIEF],
        input_func=fake_input,
        print_func=output.append,
    )

    assert exit_code == 0
    assert any("limit reached" in line for line in output)
    assert any("CHANNEL COPY" in line for line in output)
    assert any("Edited copy" in line for line in output)


def test_attempt_limit_followed_by_quit_does_not_crash(monkeypatch) -> None:
    def fake_generate_initial_draft(session):
        draft = SimpleNamespace(revision_number=1, channel_copy="Initial copy", reviewer_notes="Initial notes")
        session.current_draft = draft
        session.history = [draft]
        return draft

    monkeypatch.setattr(pipeline_main, "generate_initial_draft", fake_generate_initial_draft)
    monkeypatch.setattr(pipeline_main, "revise_current_draft", lambda *args, **kwargs: (_ for _ in ()).throw(GenerationLimitExceededError("attempt limit reached")))

    responses = iter(["r", "Please revise", "q"] )

    def fake_input(prompt: str = "") -> str:
        return next(responses)

    output: list[str] = []
    exit_code = pipeline_main.run_cli(
        ["--channel", "instagram", "--brief", BRIEF],
        input_func=fake_input,
        print_func=output.append,
    )

    assert exit_code == 0
    assert any("attempt limit reached" in line for line in output)
    assert any("Session closed without approval or export." in line for line in output)


def test_openai_connection_error_during_revision_remains_recoverable(monkeypatch) -> None:
    captured_session: dict[str, object] = {}

    def fake_generate_initial_draft(session):
        draft = SimpleNamespace(revision_number=1, channel_copy="Initial copy", reviewer_notes="Initial notes")
        session.current_draft = draft
        session.history = [draft]
        captured_session["session"] = session
        return draft

    monkeypatch.setattr(pipeline_main, "generate_initial_draft", fake_generate_initial_draft)
    monkeypatch.setattr(
        pipeline_main,
        "revise_current_draft",
        lambda *args, **kwargs: (_ for _ in ()).throw(OpenAIConnectionError("connection lost")),
    )
    monkeypatch.setattr(
        pipeline_main,
        "approve_current_draft",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("approval should not run")),
    )
    monkeypatch.setattr(
        pipeline_main,
        "export_approved_current_draft",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("export should not run")),
    )

    responses = iter(["r", "Please revise", "q"])

    def fake_input(prompt: str = "") -> str:
        return next(responses)

    output: list[str] = []
    exit_code = pipeline_main.run_cli(
        ["--channel", "instagram", "--brief", BRIEF],
        input_func=fake_input,
        print_func=output.append,
    )

    session = captured_session["session"]

    assert exit_code == 0
    assert any("connection lost" in line for line in output)
    assert any("Session closed without approval or export." in line for line in output)
    assert session.current_draft.channel_copy == "Initial copy"
    assert session.approval is None


def test_corpus_error_produces_sanitized_cli_error(monkeypatch) -> None:
    monkeypatch.setattr(pipeline_main, "assemble_context_bundle", lambda *args, **kwargs: (_ for _ in ()).throw(MarkdownCorpusError("boom")))

    output: list[str] = []
    exit_code = pipeline_main.run_cli(
        ["--channel", "instagram", "--brief", BRIEF, "--dry-run"],
        print_func=output.append,
    )

    assert exit_code == 1
    assert any("Failed to load knowledge base corpus" in line for line in output)


def test_export_failure_preserves_draft_and_approval(monkeypatch, tmp_path: Path) -> None:
    context_bundle = assemble_context_bundle(REPO_ROOT)
    session = create_pipeline_session("instagram", BRIEF, context_bundle)
    calls: list[dict[str, object]] = []
    fake_generation_function = _fake_generator_factory([_generated_text(VALID_RESPONSE_ONE)], calls)
    draft = generate_initial_draft(session, generation_function=fake_generation_function)
    approval = approve_current_draft(session, approved_copy=draft.channel_copy, approved_revision=draft.revision_number)

    original_write = pipeline._write_text_exclusive
    call_count = {"value": 0}

    def failing_write(path: Path, text: str) -> None:
        call_count["value"] += 1
        if call_count["value"] == 2:
            raise OSError("disk full")
        original_write(path, text)

    monkeypatch.setattr(pipeline, "_write_text_exclusive", failing_write)

    with pytest.raises(ExportError):
        export_approved_current_draft(session, output_directory=tmp_path)

    assert session.current_draft == draft
    assert session.approval == approval
    assert list(tmp_path.iterdir()) == []


def test_export_directory_creation_failure_is_wrapped(monkeypatch, tmp_path: Path) -> None:
    context_bundle = assemble_context_bundle(REPO_ROOT)
    session = create_pipeline_session("instagram", BRIEF, context_bundle)
    calls: list[dict[str, object]] = []
    fake_generation_function = _fake_generator_factory([_generated_text(VALID_RESPONSE_ONE)], calls)
    draft = generate_initial_draft(session, generation_function=fake_generation_function)
    approval = approve_current_draft(session, approved_copy=draft.channel_copy, approved_revision=draft.revision_number)

    def failing_mkdir(self, parents: bool = False, exist_ok: bool = False) -> None:
        raise PermissionError("cannot create export directory")

    monkeypatch.setattr(pipeline.Path, "mkdir", failing_mkdir)

    with pytest.raises(ExportError, match="Could not prepare export directory."):
        export_approved_current_draft(session, output_directory=tmp_path / "missing" / "exports")

    assert session.current_draft == draft
    assert session.approval == approval
    assert not (tmp_path / "missing" / "exports").exists()


def test_existing_export_files_are_not_overwritten(monkeypatch, tmp_path: Path) -> None:
    context_bundle = assemble_context_bundle(REPO_ROOT)
    session = create_pipeline_session("instagram", BRIEF, context_bundle)
    calls: list[dict[str, object]] = []
    fake_generation_function = _fake_generator_factory([_generated_text(VALID_RESPONSE_ONE)], calls)
    draft = generate_initial_draft(session, generation_function=fake_generation_function)
    approve_current_draft(session, approved_copy=draft.channel_copy, approved_revision=draft.revision_number)

    monkeypatch.setattr(pipeline, "_export_timestamp_token", lambda: "20260101T000000Z")
    monkeypatch.setattr(pipeline, "uuid4", lambda: SimpleNamespace(hex="deadbeefcafebabe"))

    expected_markdown = tmp_path / "instagram-rev1-20260101T000000Z-deadbeef.md"
    expected_json = tmp_path / "instagram-rev1-20260101T000000Z-deadbeef.json"
    expected_markdown.write_text("existing markdown", encoding="utf-8")
    expected_json.write_text("existing json", encoding="utf-8")

    with pytest.raises(ExportError):
        export_approved_current_draft(session, output_directory=tmp_path)

    assert expected_markdown.read_text(encoding="utf-8") == "existing markdown"
    assert expected_json.read_text(encoding="utf-8") == "existing json"
    assert session.current_draft == draft
    assert session.approval is not None


def test_unknown_channel_is_rejected_before_generation() -> None:
    context_bundle = assemble_context_bundle(REPO_ROOT)

    with pytest.raises(ContentPipelineError):
        create_pipeline_session("twitter", BRIEF, context_bundle)


def test_prepared_product_identity_survives_edit_approval_export_and_blocks_fallback(tmp_path):
    product_id = "torrentshell_85241"
    context = _make_rag_prompt_context()
    session = create_pipeline_session("instagram", "Introduce 85241", context, product_id=product_id)
    calls = []
    with pytest.raises(ContentPipelineError, match="no full-corpus fallback"):
        generate_initial_draft(session, generation_function=lambda **kwargs: pytest.fail("must not call generation"))
    session.paid_attempts_used = 0
    provider = _FakeContextProvider(prompt_context=context, context_mode="rag", retrieval_provenance={"product_id": product_id})
    generate_initial_draft(session, context_provider=provider,
                           generation_function=_fake_generator_factory([_generated_text("### CHANNEL COPY\nRain shell details.\n### REVIEWER NOTES\nSource: 85241.")], calls))
    assert "Selected product:" in calls[0]["instructions"]
    assert "85241" in calls[0]["instructions"]
    edit_current_draft(session, "Edited rain shell details.", revised_reviewer_notes="Reviewed source 85241.")
    approve_current_draft(session, approved_copy=session.current_draft.channel_copy, approved_revision=session.current_draft.revision_number, reviewer_name="Test reviewer")
    exported = export_approved_current_draft(session, output_directory=tmp_path)
    payload = json.loads(exported.json_path.read_text(encoding="utf-8"))
    assert payload["product_id"] == product_id
    assert payload["retrieval_provenance"]["product_id"] == product_id
