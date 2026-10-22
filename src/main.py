"""Command-line entry point for the content pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Sequence

from src.content_pipeline import (
    ApprovalError,
    ContentPipelineError,
    approve_current_draft,
    create_pipeline_session,
    edit_current_draft,
    export_approved_current_draft,
    generate_initial_draft,
    revise_current_draft,
)
from src.knowledge_base import MarkdownCorpusError, assemble_context_bundle
from src.llm_integration import OpenAIIntegrationError
from src.prompt_templates import PromptTemplateError, build_prompt

REPO_ROOT = Path(__file__).resolve().parents[1]

InputFunc = Callable[[str], str]
PrintFunc = Callable[..., None]


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Patagonia Content Studio CLI")
    parser.add_argument("--channel", required=True, choices=("instagram", "linkedin", "email"), help="target channel")
    parser.add_argument("--brief", required=True, help="campaign brief")
    parser.add_argument("--dry-run", action="store_true", help="build prompts without loading credentials or calling the API")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    return run_cli(argv)


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    input_func: InputFunc = input,
    print_func: PrintFunc = print,
) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    try:
        context_bundle = assemble_context_bundle(REPO_ROOT)
        if args.dry_run:
            return _run_dry_run(args.channel, args.brief, context_bundle, print_func)

        session = create_pipeline_session(args.channel, args.brief, context_bundle)
        return _run_live_session(session, input_func=input_func, print_func=print_func)
    except MarkdownCorpusError:
        _emit_error(print_func, "Error: Failed to load knowledge base corpus.")
        return 1
    except (ApprovalError, ContentPipelineError, OpenAIIntegrationError, PromptTemplateError, RuntimeError) as exc:
        _emit_error(print_func, f"Error: {exc}")
        return 1


def _run_dry_run(channel: str, brief: str, context_bundle, print_func: PrintFunc) -> int:
    prompt_parts = build_prompt(channel, brief, context_bundle)
    report = {
        "mode": "dry-run",
        "channel": channel,
        "brief": brief,
        "source_manifest": [asdict(entry) for entry in context_bundle.source_manifest],
        "corpus_measurements": asdict(context_bundle.corpus_measurements),
        "prompt": asdict(prompt_parts),
    }
    print_func(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def _run_live_session(session, *, input_func: InputFunc, print_func: PrintFunc) -> int:
    try:
        draft = generate_initial_draft(session)
    except ContentPipelineError as exc:
        _emit_error(print_func, f"Error: {exc}")
        return 1

    _show_draft(draft, print_func)

    while True:
        action = _prompt_action(input_func, print_func)
        if not action or action.lower() in {"q", "quit"}:
            print_func("Session closed without approval or export.")
            return 0

        try:
            if action.lower() in {"r", "revise"}:
                feedback = _read_single_line(input_func, print_func, "Enter reviewer feedback for the next revision:")
                if not feedback.strip():
                    print_func("No feedback entered; keeping the current draft.")
                    continue
                draft = revise_current_draft(session, feedback)
                _show_draft(draft, print_func)
                continue

            if action.lower() in {"e", "edit"}:
                revised_copy = _read_multiline_block(
                    input_func,
                    print_func,
                    "Paste the revised channel copy. Finish with a single line containing END.",
                )
                if not revised_copy.strip():
                    print_func("No edited copy entered; keeping the current draft.")
                    continue
                revised_notes = _read_optional_single_line(
                    input_func,
                    print_func,
                    "Optional reviewer notes for the edited draft (press Enter to keep the current notes):",
                )
                draft = edit_current_draft(
                    session,
                    revised_copy,
                    revised_reviewer_notes=revised_notes if revised_notes is not None else None,
                )
                _show_draft(draft, print_func)
                continue

            if action.lower() in {"a", "approve"}:
                current_draft = session.current_draft
                if current_draft is None:
                    raise ContentPipelineError("No current draft is available for approval.")
                confirmation = _read_single_line(
                    input_func,
                    print_func,
                    f"Type APPROVE to approve revision {current_draft.revision_number}:",
                )
                if confirmation != "APPROVE":
                    print_func("Approval cancelled.")
                    continue
                approve_current_draft(
                    session,
                    approved_copy=current_draft.channel_copy,
                    approved_revision=current_draft.revision_number,
                )
                export_record = export_approved_current_draft(session)
                print_func(f"Exported Markdown: {export_record.markdown_path}")
                print_func(f"Exported JSON: {export_record.json_path}")
                return 0

            print_func("Unknown action. Use revise, edit, approve, or quit.")
        except (ContentPipelineError, OpenAIIntegrationError, PromptTemplateError) as exc:
            _emit_error(print_func, f"Error: {exc}")
            continue


def _emit_error(print_func: PrintFunc, message: str) -> None:
    try:
        print_func(message, file=sys.stderr)
    except TypeError:
        print_func(message)


def _show_draft(draft, print_func: PrintFunc) -> None:
    print_func("CHANNEL COPY")
    print_func(draft.channel_copy)
    print_func("")
    print_func("REVIEWER NOTES")
    print_func(draft.reviewer_notes)
    print_func("")
    print_func(f"Revision: {draft.revision_number}")


def _prompt_action(input_func: InputFunc, print_func: PrintFunc) -> str:
    print_func("")
    print_func("Choose an action: revise, edit, approve, or quit.")
    return _read_single_line(input_func, print_func, "> ").strip()


def _read_single_line(input_func: InputFunc, print_func: PrintFunc, prompt: str) -> str:
    try:
        return input_func(prompt)
    except EOFError:
        print_func("Input closed.")
        return ""


def _read_optional_single_line(input_func: InputFunc, print_func: PrintFunc, prompt: str) -> str | None:
    response = _read_single_line(input_func, print_func, prompt)
    if not response.strip():
        return None
    return response


def _read_multiline_block(input_func: InputFunc, print_func: PrintFunc, prompt: str) -> str:
    print_func(prompt)
    lines: list[str] = []
    while True:
        try:
            line = input_func("")
        except EOFError:
            print_func("Input closed.")
            break
        if line == "END":
            break
        lines.append(line)
    return "\n".join(lines).strip()


if __name__ == "__main__":
    raise SystemExit(main())
