from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.evaluation_runner import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_TIMEOUT_SECONDS,
    EVALUATION_BRIEFS,
    EvaluationRunResult,
    build_request_plans,
    render_run_json,
    run_evaluation,
)
from src.llm_integration import GeneratedText, UsageMetrics


@pytest.fixture()
def fake_settings() -> SimpleNamespace:
    return SimpleNamespace(api_key="sk-test", model="gpt-test")


def _fake_response(index: int, channel: str, condition: str) -> GeneratedText:
    return GeneratedText(
        generated_text=(
            "### CHANNEL COPY\n"
            f"{channel} {condition} copy {index}\n"
            "### REVIEWER NOTES\n"
            f"{channel} {condition} notes {index}\n"
        ),
        response_id=f"resp_{index:02d}_{channel}_{condition}",
        model="gpt-test",
        elapsed_seconds=float(index) + 0.5,
        usage=UsageMetrics(
            input_tokens=index,
            input_tokens_details=None,
            output_tokens=index + 10,
            output_tokens_details=None,
            total_tokens=index + 11,
        ),
    )


def test_dry_run_builds_six_planned_requests_and_skips_generation() -> None:
    called = False

    def fail_generation(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("generation should not run in dry-run mode")

    result = run_evaluation(live=False, repo_root=REPO_ROOT, generation_function=fail_generation)

    assert called is False
    assert isinstance(result, EvaluationRunResult)
    assert result.mode == "dry-run"
    assert result.planned_requests == 6
    assert result.completed_requests == 0
    assert len(result.records) == 6
    assert all(record.status == "planned" for record in result.records)
    assert all(record.settings["max_output_tokens"] == DEFAULT_MAX_OUTPUT_TOKENS for record in result.records)
    assert all(record.settings["timeout_seconds"] == DEFAULT_TIMEOUT_SECONDS for record in result.records)
    assert all(record.prompt["trusted_instructions"] for record in result.records)
    assert all(record.prompt["user_input_text"] for record in result.records)
    assert any("Verified source context is unavailable" in record.prompt["user_input_text"] for record in result.records)


def test_paired_prompts_keep_conditions_separate_and_share_settings() -> None:
    plans, contextual_bundle = build_request_plans(REPO_ROOT)
    paired = {(plan.channel, plan.condition): plan for plan in plans}

    assert contextual_bundle.corpus_measurements.total_document_count == 6
    assert len(contextual_bundle.source_manifest) == 6

    for channel in EVALUATION_BRIEFS:
        generic = paired[(channel, "generic")]
        contextual = paired[(channel, "contextual")]
        assert generic.brief == contextual.brief == EVALUATION_BRIEFS[channel]
        assert generic.prompt.trusted_instructions == contextual.prompt.trusted_instructions
        assert generic.settings["max_output_tokens"] == contextual.settings["max_output_tokens"] == DEFAULT_MAX_OUTPUT_TOKENS
        assert generic.settings["timeout_seconds"] == contextual.settings["timeout_seconds"] == DEFAULT_TIMEOUT_SECONDS
        assert generic.corpus_identity is None
        assert contextual.corpus_identity is not None
        assert contextual.corpus_identity["corpus_measurements"]["total_document_count"] == 6
        assert len(contextual.corpus_identity["source_manifest"]) == 6
        assert "Verified source context is unavailable" in generic.prompt.user_input_text
        assert "Verified source context is unavailable" not in contextual.prompt.user_input_text


def test_live_run_persists_each_completed_result_and_stops_after_error(tmp_path: Path, fake_settings: SimpleNamespace) -> None:
    calls: list[dict[str, object]] = []
    planned_pairs = [
        ("instagram", "generic"),
        ("instagram", "contextual"),
        ("linkedin", "generic"),
        ("linkedin", "contextual"),
        ("email", "generic"),
        ("email", "contextual"),
    ]

    def fake_generation(*, instructions, user_input, client=None, settings=None, max_output_tokens=None, timeout_seconds=None):
        index = len(calls)
        channel, condition = planned_pairs[index]
        calls.append(
            {
                "instructions": instructions,
                "user_input": user_input,
                "model": settings.model,
                "max_output_tokens": max_output_tokens,
                "timeout_seconds": timeout_seconds,
            }
        )
        if index == 2:
            raise RuntimeError("simulated failure after two completed requests")
        return _fake_response(index + 1, channel, condition)

    result = run_evaluation(
        live=True,
        repo_root=REPO_ROOT,
        runs_dir=tmp_path / "runs",
        generation_function=fake_generation,
        settings_loader=lambda _repo_root: fake_settings,
        client_builder=lambda _settings, **_kwargs: object(),
    )

    assert result.mode == "live"
    assert result.planned_requests == 6
    assert result.completed_requests == 2
    assert result.error == "simulated failure after two completed requests"
    assert len(result.records) == 3
    assert result.records[-1].status == "failed"
    assert len(calls) == 3
    assert calls[0]["model"] == "gpt-test"
    assert calls[0]["max_output_tokens"] == DEFAULT_MAX_OUTPUT_TOKENS
    assert calls[0]["timeout_seconds"] == DEFAULT_TIMEOUT_SECONDS

    run_dir = Path(result.run_directory)
    assert run_dir.is_dir()
    completed_json = sorted(path.name for path in run_dir.glob("*.json"))
    assert "manifest.json" in completed_json
    assert any(name == "01-instagram-generic.json" for name in completed_json)
    assert any(name == "02-instagram-contextual.json" for name in completed_json)
    assert any(name.endswith("-error.json") for name in completed_json)
    assert not any(name == "03-linkedin-generic.json" for name in completed_json)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["completed_requests"] == 2
    assert manifest["error"] == "simulated failure after two completed requests"
    assert len(manifest["records"]) == 3
    assert manifest["records"][-1]["status"] == "failed"


def test_result_rendering_preserves_prompts_and_response_payload(tmp_path: Path, fake_settings: SimpleNamespace) -> None:
    def fake_generation(*, instructions, user_input, client=None, settings=None, max_output_tokens=None, timeout_seconds=None):
        index = len([line for line in user_input.splitlines() if line.startswith("###")])
        return _fake_response(1, "instagram", "generic")

    result = run_evaluation(
        live=True,
        repo_root=REPO_ROOT,
        runs_dir=tmp_path / "runs",
        generation_function=fake_generation,
        settings_loader=lambda _repo_root: fake_settings,
        client_builder=lambda _settings, **_kwargs: object(),
    )

    assert result.error is None
    assert result.completed_requests == 6
    assert len(result.records) == 6
    first_record = result.records[0]
    second_record = result.records[1]
    assert first_record.prompt["trusted_instructions"]
    assert first_record.prompt["user_input_text"]
    assert first_record.response["response_id"] == "resp_01_instagram_generic"
    assert first_record.parsed["channel_copy"] == "instagram generic copy 1"
    assert first_record.parsed["reviewer_notes"] == "instagram generic notes 1"
    assert first_record.corpus_identity is None
    assert second_record.corpus_identity is not None
    assert second_record.corpus_identity["corpus_measurements"]["total_document_count"] == 6

    rendered = json.loads(render_run_json(result))
    assert rendered["planned_requests"] == 6
    assert rendered["completed_requests"] == 6
    assert rendered["records"][0]["parsed"]["channel_copy"] == "instagram generic copy 1"


def test_live_run_accepts_custom_runs_base_directory(tmp_path: Path, fake_settings: SimpleNamespace) -> None:
    custom_runs_base = tmp_path / "custom-runs"

    result = run_evaluation(
        live=True,
        repo_root=REPO_ROOT,
        runs_dir=custom_runs_base,
        generation_function=lambda **kwargs: _fake_response(1, "instagram", "generic"),
        settings_loader=lambda _repo_root: fake_settings,
        client_builder=lambda _settings, **_kwargs: object(),
    )

    assert result.run_directory is not None
    run_dir = Path(result.run_directory)
    assert run_dir.parent == custom_runs_base.resolve()
    assert run_dir.is_dir()
