import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import src.main as cli


def test_dry_run_builds_prompt_from_real_corpus_and_skips_generation(monkeypatch) -> None:
    called = {"generation": False}

    def fail_generation(*args, **kwargs):
        called["generation"] = True
        raise AssertionError("generation should not be called during dry-run")

    monkeypatch.setattr(cli, "generate_initial_draft", fail_generation)

    output: list[str] = []
    exit_code = cli.run_cli(
        ["--channel", "instagram", "--brief", "Test brief for dry run.", "--dry-run"],
        print_func=output.append,
    )

    assert exit_code == 0
    assert called["generation"] is False
    report = json.loads(output[0])
    assert report["mode"] == "dry-run"
    assert report["corpus_measurements"]["primary_document_count"] == 5
    assert report["corpus_measurements"]["secondary_document_count"] == 2
    assert report["corpus_measurements"]["total_document_count"] == 7
    assert "Test brief for dry run." in report["prompt"]["user_input_text"]


def test_live_quit_never_implies_approval_or_export(monkeypatch) -> None:
    draft = SimpleNamespace(revision_number=1, channel_copy="Copy text", reviewer_notes="Notes text")

    monkeypatch.setattr(cli, "generate_initial_draft", lambda session: draft)

    def fail_approval(*args, **kwargs):
        raise AssertionError("approval should not be called when quitting")

    def fail_export(*args, **kwargs):
        raise AssertionError("export should not be called when quitting")

    monkeypatch.setattr(cli, "approve_current_draft", fail_approval)
    monkeypatch.setattr(cli, "export_approved_current_draft", fail_export)

    prompts: list[str] = []

    def fake_input(prompt: str = "") -> str:
        prompts.append(prompt)
        return "q"

    output: list[str] = []
    exit_code = cli.run_cli(
        ["--channel", "instagram", "--brief", "Test brief for live quit."],
        input_func=fake_input,
        print_func=output.append,
    )

    assert exit_code == 0
    assert any("CHANNEL COPY" in line for line in output)
    assert any("Session closed without approval or export." in line for line in output)
    assert prompts
