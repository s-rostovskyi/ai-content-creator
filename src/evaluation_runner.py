from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Callable, Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from src.content_pipeline import parse_generated_sections
from src.knowledge_base import ContextBundle, CorpusMeasurements, assemble_context_bundle
from src.llm_integration import (
    GeneratedText,
    OpenAISettings,
    build_openai_client,
    generate_response,
    load_openai_settings,
)
from src.prompt_templates import PromptParts, build_prompt

Channel = Literal["instagram", "linkedin", "email"]
Condition = Literal["generic", "contextual"]

DEFAULT_MAX_OUTPUT_TOKENS = 2000
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_RUNS_DIR = Path(__file__).resolve().parents[1] / "docs" / "evaluation" / "runs"
EVALUATION_CHANNELS: tuple[Channel, ...] = ("instagram", "linkedin", "email")
EVALUATION_CONDITIONS: tuple[Condition, ...] = ("generic", "contextual")
GENERIC_CONTEXT_NOTE = (
    "Verified source context is unavailable for this generic baseline. Do not invent facts, source links, "
    "statistics, or brand claims."
)
EVALUATION_BRIEFS: dict[Channel, str] = {
    "instagram": (
        "Draft an Instagram caption introducing the Patagonia Men's Nano Puff Jacket, style 84212, to an "
        "English-speaking US audience planning everyday outings and outdoor trips. Focus on verified packability "
        "and practical features. Avoid prices, discounts, urgency and unsupported environmental claims. Invite "
        "readers to explore the product details."
    ),
    "linkedin": (
        "Draft a LinkedIn post introducing the Patagonia Men's Nano Puff Jacket, style 84212, to an "
        "English-speaking US audience. Emphasize verified product features, practical use cases, and a clear, "
        "professional tone. Avoid prices, discounts, urgency and unsupported environmental claims. Invite readers to "
        "explore the product details."
    ),
    "email": (
        "Draft an email newsletter feature introducing the Patagonia Men's Nano Puff Jacket, style 84212, to an "
        "English-speaking US audience. Include a concise subject-line-friendly angle, a short body draft, and a "
        "useful call to action. Stay within verified product facts. Avoid prices, discounts, urgency and unsupported "
        "environmental claims."
    ),
}


@dataclass(frozen=True)
class EvaluationRequestPlan:
    request_index: int
    channel: Channel
    condition: Condition
    brief: str
    prompt: PromptParts
    settings: dict[str, object]
    corpus_identity: dict[str, object] | None


@dataclass(frozen=True)
class EvaluationRequestRecord:
    request_index: int
    channel: Channel
    condition: Condition
    brief: str
    timestamp: str
    settings: dict[str, object]
    prompt: dict[str, str]
    corpus_identity: dict[str, object] | None
    status: str
    response: dict[str, object] | None = None
    parsed: dict[str, str] | None = None
    error: str | None = None
    files: dict[str, str] | None = None


@dataclass(frozen=True)
class EvaluationRunResult:
    mode: Literal["dry-run", "live"]
    planned_requests: int
    completed_requests: int
    records: tuple[EvaluationRequestRecord, ...]
    run_directory: str | None = None
    error: str | None = None


GenerationFunction = Callable[..., GeneratedText]
SettingsLoader = Callable[[str | Path | None], OpenAISettings]
ClientBuilder = Callable[..., object]


def build_request_plans(
    repo_root: str | Path | None = None,
    *,
    contextual_bundle: ContextBundle | None = None,
) -> tuple[tuple[EvaluationRequestPlan, ...], ContextBundle]:
    root_path = _resolve_repo_root(repo_root)
    contextual_bundle = contextual_bundle or assemble_context_bundle(root_path)
    plans: list[EvaluationRequestPlan] = []
    request_index = 1
    for channel in EVALUATION_CHANNELS:
        brief = EVALUATION_BRIEFS[channel]
        for condition in EVALUATION_CONDITIONS:
            prompt, corpus_identity = _build_prompt_for_condition(channel, brief, contextual_bundle, condition)
            plans.append(
                EvaluationRequestPlan(
                    request_index=request_index,
                    channel=channel,
                    condition=condition,
                    brief=brief,
                    prompt=prompt,
                    settings={
                        "model": None,
                        "max_output_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
                        "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
                    },
                    corpus_identity=corpus_identity,
                )
            )
            request_index += 1
    return tuple(plans), contextual_bundle


def run_evaluation(
    *,
    live: bool = False,
    repo_root: str | Path | None = None,
    runs_dir: str | Path | None = None,
    generation_function: GenerationFunction = generate_response,
    settings_loader: SettingsLoader = load_openai_settings,
    client_builder: ClientBuilder = build_openai_client,
) -> EvaluationRunResult:
    root_path = _resolve_repo_root(repo_root)
    plans, contextual_bundle = build_request_plans(root_path)

    if not live:
        records = tuple(_plan_to_record(plan) for plan in plans)
        return EvaluationRunResult(
            mode="dry-run",
            planned_requests=len(plans),
            completed_requests=0,
            records=records,
        )

    base_runs_dir = _resolve_runs_dir(root_path, runs_dir)
    run_dir = _create_run_directory(base_runs_dir)
    settings = settings_loader(root_path)
    client = client_builder(settings, timeout_seconds=DEFAULT_TIMEOUT_SECONDS)

    completed_records: list[EvaluationRequestRecord] = []
    manifest = _new_manifest(run_dir, plans, settings, contextual_bundle)
    _write_json(run_dir / "manifest.json", manifest)

    for plan in plans:
        plan_with_model = _apply_model_setting(plan, settings.model)
        try:
            record = _run_single_request(
                run_dir=run_dir,
                plan=plan_with_model,
                client=client,
                settings=settings,
                generation_function=generation_function,
            )
        except Exception as exc:
            error_message = _sanitize_error(exc)
            error_record = _make_error_record(plan_with_model, error_message)
            error_path = run_dir / f"{_request_stem(plan_with_model)}-error.json"
            _write_json(error_path, asdict(error_record))
            completed_records.append(error_record)
            manifest["status"] = "failed"
            manifest["error"] = error_message
            manifest["completed_requests"] = len([record for record in completed_records if record.status == "completed"])
            manifest["records"].append(
                {
                    "request_index": plan_with_model.request_index,
                    "channel": plan_with_model.channel,
                    "condition": plan_with_model.condition,
                    "status": "failed",
                    "error": error_message,
                    "file": str(error_path),
                }
            )
            _write_json(run_dir / "manifest.json", manifest)
            return EvaluationRunResult(
                mode="live",
                planned_requests=len(plans),
                completed_requests=len([record for record in completed_records if record.status == "completed"]),
                records=tuple(completed_records),
                run_directory=str(run_dir),
                error=error_message,
            )

        completed_records.append(record)
        manifest["completed_requests"] = len(completed_records)
        manifest["records"].append(
            {
                "request_index": record.request_index,
                "channel": record.channel,
                "condition": record.condition,
                "status": record.status,
                "file": record.files["json"] if record.files else None,
            }
        )
        _write_json(run_dir / "manifest.json", manifest)

    manifest["status"] = "complete"
    _write_json(run_dir / "manifest.json", manifest)
    return EvaluationRunResult(
        mode="live",
        planned_requests=len(plans),
        completed_requests=len(completed_records),
        records=tuple(completed_records),
        run_directory=str(run_dir),
    )


def render_run_json(result: EvaluationRunResult) -> str:
    return json.dumps(asdict(result), indent=2, ensure_ascii=False)


def _build_prompt_for_condition(
    channel: Channel,
    brief: str,
    contextual_bundle: ContextBundle,
    condition: Condition,
) -> tuple[PromptParts, dict[str, object] | None]:
    if condition == "contextual":
        prompt = build_prompt(channel, brief, contextual_bundle)
        corpus_identity = {
            "source_manifest": [asdict(entry) for entry in contextual_bundle.source_manifest],
            "corpus_measurements": asdict(contextual_bundle.corpus_measurements),
        }
        return prompt, corpus_identity

    empty_bundle = ContextBundle(
        primary_context="",
        secondary_context="",
        source_manifest=(),
        corpus_measurements=CorpusMeasurements(
            primary_document_count=0,
            secondary_document_count=0,
            total_document_count=0,
            utf8_corpus_bytes=0,
            primary_context_characters=0,
            secondary_context_characters=0,
            serialized_context_characters=0,
            max_serialized_characters=0,
        ),
    )
    prompt = build_prompt(channel, brief, empty_bundle)
    augmented_user_input = "\n\n".join((prompt.user_input_text.rstrip(), GENERIC_CONTEXT_NOTE)).strip()
    return PromptParts(trusted_instructions=prompt.trusted_instructions, user_input_text=augmented_user_input), None


def _run_single_request(
    *,
    run_dir: Path,
    plan: EvaluationRequestPlan,
    client: object,
    settings: OpenAISettings,
    generation_function: GenerationFunction,
) -> EvaluationRequestRecord:
    timestamp = datetime.now(ZoneInfo("Europe/Berlin")).isoformat()
    result = generation_function(
        instructions=plan.prompt.trusted_instructions,
        user_input=plan.prompt.user_input_text,
        client=client,
        settings=settings,
        max_output_tokens=int(plan.settings["max_output_tokens"]),
        timeout_seconds=float(plan.settings["timeout_seconds"]),
    )
    parsed_sections = parse_generated_sections(result.generated_text)
    record = EvaluationRequestRecord(
        request_index=plan.request_index,
        channel=plan.channel,
        condition=plan.condition,
        brief=plan.brief,
        timestamp=timestamp,
        settings=plan.settings,
        prompt={
            "trusted_instructions": plan.prompt.trusted_instructions,
            "user_input_text": plan.prompt.user_input_text,
        },
        corpus_identity=plan.corpus_identity,
        status="completed",
        response={
            "raw_response": result.generated_text,
            "response_id": result.response_id,
            "model": result.model,
            "elapsed_seconds": result.elapsed_seconds,
            "usage": asdict(result.usage) if result.usage is not None else None,
        },
        parsed={
            "channel_copy": parsed_sections.channel_copy,
            "reviewer_notes": parsed_sections.reviewer_notes,
        },
        files={},
    )
    file_stem = _request_stem(plan)
    json_path = run_dir / f"{file_stem}.json"
    _write_json(json_path, asdict(record))
    return EvaluationRequestRecord(**{**asdict(record), "files": {"json": str(json_path)}})


def _plan_to_record(plan: EvaluationRequestPlan) -> EvaluationRequestRecord:
    return EvaluationRequestRecord(
        request_index=plan.request_index,
        channel=plan.channel,
        condition=plan.condition,
        brief=plan.brief,
        timestamp="",
        settings=plan.settings,
        prompt={
            "trusted_instructions": plan.prompt.trusted_instructions,
            "user_input_text": plan.prompt.user_input_text,
        },
        corpus_identity=plan.corpus_identity,
        status="planned",
    )


def _make_error_record(plan: EvaluationRequestPlan, error_message: str) -> EvaluationRequestRecord:
    return EvaluationRequestRecord(
        request_index=plan.request_index,
        channel=plan.channel,
        condition=plan.condition,
        brief=plan.brief,
        timestamp=datetime.now(ZoneInfo("Europe/Berlin")).isoformat(),
        settings=plan.settings,
        prompt={
            "trusted_instructions": plan.prompt.trusted_instructions,
            "user_input_text": plan.prompt.user_input_text,
        },
        corpus_identity=plan.corpus_identity,
        status="failed",
        error=error_message,
        files={},
    )


def _new_manifest(
    run_dir: Path,
    plans: tuple[EvaluationRequestPlan, ...],
    settings: OpenAISettings,
    contextual_bundle: ContextBundle,
) -> dict[str, object]:
    return {
        "mode": "live",
        "status": "running",
        "run_directory": str(run_dir),
        "started_at": datetime.now(ZoneInfo("Europe/Berlin")).isoformat(),
        "planned_requests": len(plans),
        "completed_requests": 0,
        "settings": {
            "model": settings.model,
            "max_output_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
            "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        },
        "contextual_corpus": {
            "source_manifest": [asdict(entry) for entry in contextual_bundle.source_manifest],
            "corpus_measurements": asdict(contextual_bundle.corpus_measurements),
        },
        "records": [],
        "error": None,
    }


def _apply_model_setting(plan: EvaluationRequestPlan, model: str) -> EvaluationRequestPlan:
    return EvaluationRequestPlan(
        request_index=plan.request_index,
        channel=plan.channel,
        condition=plan.condition,
        brief=plan.brief,
        prompt=plan.prompt,
        settings={
            **plan.settings,
            "model": model,
        },
        corpus_identity=plan.corpus_identity,
    )


def _request_stem(plan: EvaluationRequestPlan) -> str:
    return f"{plan.request_index:02d}-{plan.channel}-{plan.condition}"


def _resolve_repo_root(repo_root: str | Path | None) -> Path:
    if repo_root is None:
        return Path(__file__).resolve().parents[1]
    return Path(repo_root).resolve()


def _resolve_runs_dir(repo_root: Path, runs_dir: str | Path | None) -> Path:
    if runs_dir is None:
        return repo_root / "docs" / "evaluation" / "runs"
    return Path(runs_dir).resolve()


def _create_run_directory(base_runs_dir: Path) -> Path:
    base_runs_dir.mkdir(parents=True, exist_ok=True)
    run_dir = base_runs_dir / f"{datetime.now(ZoneInfo('Europe/Berlin')).strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:8]}"
    run_dir.mkdir(parents=False, exist_ok=False)
    return run_dir


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _sanitize_error(exc: Exception) -> str:
    return str(exc).strip() or exc.__class__.__name__


__all__ = [
    "Channel",
    "Condition",
    "DEFAULT_MAX_OUTPUT_TOKENS",
    "DEFAULT_RUNS_DIR",
    "DEFAULT_TIMEOUT_SECONDS",
    "EVALUATION_BRIEFS",
    "EVALUATION_CHANNELS",
    "EVALUATION_CONDITIONS",
    "EvaluationRequestPlan",
    "EvaluationRequestRecord",
    "EvaluationRunResult",
    "build_request_plans",
    "render_run_json",
    "run_evaluation",
]
