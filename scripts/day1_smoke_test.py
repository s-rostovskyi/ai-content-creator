from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.knowledge_base import assemble_context_bundle
from src.llm_integration import OpenAIConfigurationError, build_openai_client, generate_response, load_openai_settings
from src.prompt_templates import PromptTemplateError, build_prompt

BRIEF = (
    "Draft an Instagram caption introducing the Patagonia Men's Nano Puff Jacket, style 84212, to an "
    "English-speaking US audience planning everyday outings and outdoor trips. Focus on verified packability "
    "and practical features. Use the supplied industry context only where relevant; do not force statistics or "
    "competitor mentions into the caption. Avoid prices, discounts, urgency and unsupported environmental claims. "
    "Invite readers to explore the product details."
)
CHANNEL = "instagram"
REQUEST_MODEL = "gpt-5.4-mini"
MAX_OUTPUT_TOKENS = 2000
TIMEOUT_SECONDS = 60.0
EVIDENCE_DIR = REPO_ROOT / "docs" / "evidence"
EVIDENCE_JSON = EVIDENCE_DIR / "day1-smoke-test.json"
EVIDENCE_MD = EVIDENCE_DIR / "day1-smoke-test.md"


def main() -> int:
    parser = argparse.ArgumentParser(description="Day 1 Instagram smoke test")
    parser.add_argument("--live", action="store_true", help="perform the single live OpenAI request")
    parser.add_argument(
        "--overwrite-evidence",
        action="store_true",
        help="overwrite existing evidence files if they already exist",
    )
    args = parser.parse_args()

    try:
        context_bundle = assemble_context_bundle(REPO_ROOT)
        prompt_parts = build_prompt(CHANNEL, BRIEF, context_bundle)
        dry_run_report = _build_base_report(context_bundle, prompt_parts)

        if not args.live:
            print(json.dumps({"mode": "dry-run", **dry_run_report}, indent=2, ensure_ascii=False))
            return 0

        settings = load_openai_settings(REPO_ROOT)
        if settings.model != REQUEST_MODEL:
            raise RuntimeError(
                f"Configured model {settings.model!r} does not match required live smoke-test model {REQUEST_MODEL!r}."
            )

        live_metadata = _prepare_live_metadata(args.overwrite_evidence)
        client = build_openai_client(settings, timeout_seconds=TIMEOUT_SECONDS)
        result = generate_response(
            instructions=prompt_parts.trusted_instructions,
            user_input=prompt_parts.user_input_text,
            client=client,
            settings=settings,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            timeout_seconds=TIMEOUT_SECONDS,
        )

        report = {
            **dry_run_report,
            "mode": "live",
            **live_metadata,
            "request": {
                "model": settings.model,
                "max_output_tokens": MAX_OUTPUT_TOKENS,
                "timeout_seconds": TIMEOUT_SECONDS,
            },
            "response": {
                "response_id": result.response_id,
                "model": result.model,
                "elapsed_seconds": result.elapsed_seconds,
                "generated_text": result.generated_text,
                "usage": asdict(result.usage) if result.usage is not None else None,
            },
            "status": "draft",
            "review_status": "pending human review",
        }

        EVIDENCE_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        EVIDENCE_MD.write_text(_render_markdown(report), encoding="utf-8")

        print(
            json.dumps(
                {
                    "mode": "live",
                    "status": "draft",
                    "response_id": result.response_id,
                    "model": result.model,
                    "elapsed_seconds": result.elapsed_seconds,
                    "usage": report["response"]["usage"],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1



def _prepare_live_metadata(overwrite_evidence: bool) -> dict[str, object]:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    if not os.access(EVIDENCE_DIR, os.W_OK | os.X_OK):
        raise RuntimeError(f"Evidence directory is not writable: {EVIDENCE_DIR}")
    if not overwrite_evidence:
        _ensure_no_existing_evidence()

    timestamp = datetime.now(ZoneInfo("Europe/Berlin")).isoformat()
    commit_id = _git_commit_id()
    working_tree_dirty = _working_tree_dirty()
    return {
        "timestamp": timestamp,
        "git_commit_id": commit_id,
        "working_tree_dirty": working_tree_dirty,
    }



def _ensure_no_existing_evidence() -> None:
    existing_paths = [path for path in (EVIDENCE_JSON, EVIDENCE_MD) if path.exists()]
    if existing_paths:
        raise RuntimeError(
            "Refusing to overwrite existing evidence files: " + ", ".join(str(path) for path in existing_paths)
        )



def _working_tree_dirty() -> bool:
    completed = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return bool(completed.stdout.strip())



def _git_commit_id() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()



def _build_base_report(context_bundle, prompt_parts) -> dict[str, object]:
    measurements = context_bundle.corpus_measurements
    return {
        "channel": CHANNEL,
        "brief": BRIEF,
        "source_manifest": [asdict(entry) for entry in context_bundle.source_manifest],
        "corpus_measurements": asdict(measurements),
        "prompt": {
            "model": REQUEST_MODEL,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "timeout_seconds": TIMEOUT_SECONDS,
            "trusted_instructions": prompt_parts.trusted_instructions,
            "user_input_text": prompt_parts.user_input_text,
        },
    }



def _render_markdown(report: dict[str, object]) -> str:
    prompt = report["prompt"]
    response = report["response"]
    measurements = report["corpus_measurements"]
    source_manifest = report["source_manifest"]
    lines = [
        "# Day 1 Instagram smoke test",
        "",
        f"- Timestamp (Europe/Berlin): {report['timestamp']}",
        f"- Git commit ID: {report['git_commit_id']}",
        f"- Working tree dirty: {report['working_tree_dirty']}",
        f"- Channel: {report['channel']}",
        f"- Status: {report['status']}",
        f"- Review status: {report['review_status']}",
        f"- Request model: {prompt['model']}",
        f"- Max output tokens: {prompt['max_output_tokens']}",
        f"- Timeout seconds: {prompt['timeout_seconds']}",
        f"- Returned model: {response['model']}",
        f"- Response ID: {response['response_id']}",
        f"- Latency (seconds): {response['elapsed_seconds']}",
        f"- Usage: {json.dumps(response['usage'], ensure_ascii=False)}",
        f"- Corpus documents: primary {measurements['primary_document_count']}, secondary {measurements['secondary_document_count']}, total {measurements['total_document_count']}",
        f"- UTF-8 corpus bytes: {measurements['utf8_corpus_bytes']}",
        f"- Serialized context characters: {measurements['serialized_context_characters']} (primary {measurements['primary_context_characters']}, secondary {measurements['secondary_context_characters']})",
        "",
        "## Exact brief",
        report["brief"],
        "",
        "## Exact trusted instructions",
        "```text",
        prompt["trusted_instructions"],
        "```",
        "",
        "## Exact user input",
        "```text",
        prompt["user_input_text"],
        "```",
        "",
        "## Source manifest",
    ]
    for entry in source_manifest:
        lines.append(
            f"- {entry['repository_relative_path']} | {entry['knowledge_base']} | {entry['document_title']} | {', '.join(entry['source_urls'])}"
        )
    lines.extend(
        [
            "",
            "## Returned draft",
            report["response"]["generated_text"],
            "",
            "## Pending human review",
            "- [ ] Human reviewer confirms the caption remains grounded in the source context.",
            "- [ ] Human reviewer confirms no unsupported claims, prices, discounts, urgency, or environmental claims were added.",
            "- [ ] Human reviewer confirms the draft is still marked draft, not approved.",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
