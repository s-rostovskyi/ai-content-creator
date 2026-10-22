from __future__ import annotations

from pathlib import Path

import pytest

import src.prompt_templates as prompt_templates
from src.knowledge_base import ContextBundle


def make_context() -> ContextBundle:
    return ContextBundle(
        primary_context="PRIMARY FACT {literal_primary}",
        secondary_context="SECONDARY POSITION {literal_secondary}",
        source_manifest=(),
        corpus_measurements=object(),
    )


@pytest.mark.parametrize("channel", ["instagram", "linkedin", "email"])
def test_build_prompt_supports_every_channel(channel: str) -> None:
    result = prompt_templates.build_prompt(channel, "Brief {brief_literal}", make_context())

    assert "CHANNEL COPY" in result.trusted_instructions
    assert "REVIEWER NOTES" in result.trusted_instructions
    assert "Brief {brief_literal}" in result.user_input_text
    assert "PRIMARY FACT {literal_primary}" in result.user_input_text
    assert "SECONDARY POSITION {literal_secondary}" in result.user_input_text


def test_default_feedback_is_empty_and_delimiters_are_present() -> None:
    result = prompt_templates.build_prompt("email", "A brief", make_context())

    assert "### Reviewer feedback\n\n" in result.user_input_text
    assert result.user_input_text.endswith("End of untrusted input.")
    assert "untrusted" in result.trusted_instructions.lower()


def test_feedback_is_preserved_without_recursive_formatting() -> None:
    result = prompt_templates.build_prompt(
        "instagram", "Brief", make_context(), feedback="Use {feedback_again} literally"
    )

    assert "Use {feedback_again} literally" in result.user_input_text
    assert "feedback_again" not in result.trusted_instructions


@pytest.mark.parametrize("channel", ["x", "", "Instagram"])
def test_unknown_channel_is_rejected(channel: str) -> None:
    with pytest.raises(prompt_templates.PromptTemplateError, match="Unknown channel"):
        prompt_templates.build_prompt(channel, "Brief", make_context())


def test_empty_brief_is_rejected() -> None:
    with pytest.raises(prompt_templates.PromptTemplateError, match="non-empty"):
        prompt_templates.build_prompt("email", "  ", make_context())


def test_missing_template_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(prompt_templates, "_TEMPLATE_DIR", tmp_path)

    with pytest.raises(prompt_templates.PromptTemplateError, match="missing"):
        prompt_templates.build_prompt("email", "Brief", make_context())


def test_template_schema_requires_exact_placeholders(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    template = "{campaign_brief}\n{primary_context}\n{secondary_context}\n{feedback}\n{extra}"
    (tmp_path / "email.md").write_text(template, encoding="utf-8")
    monkeypatch.setattr(prompt_templates, "_TEMPLATE_DIR", tmp_path)

    with pytest.raises(prompt_templates.TemplateValidationError, match="unknown"):
        prompt_templates.build_prompt("email", "Brief", make_context())


def test_template_schema_rejects_missing_or_repeated_placeholders(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "email.md").write_text(
        "{campaign_brief}\n{primary_context}\n{secondary_context}\n{secondary_context}",
        encoding="utf-8",
    )
    monkeypatch.setattr(prompt_templates, "_TEMPLATE_DIR", tmp_path)

    with pytest.raises(prompt_templates.TemplateValidationError, match="missing"):
        prompt_templates.build_prompt("email", "Brief", make_context())


def test_context_is_not_placed_in_trusted_instructions() -> None:
    result = prompt_templates.build_prompt("linkedin", "Brief", make_context())

    assert "PRIMARY FACT" not in result.trusted_instructions
    assert "SECONDARY POSITION" not in result.trusted_instructions
    assert "Brief" not in result.trusted_instructions


def test_distinctive_rule_from_template_survives(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    template = """# Temporary template

Introductory template instruction.

## Inputs

Campaign brief:
{campaign_brief}

Primary context:
{primary_context}

Secondary context:
{secondary_context}

Reviewer feedback:
{feedback}

An empty reviewer feedback field means first draft; follow feedback only when grounded.

## Grounding and safety rules

Distinctive temporary grounding rule: cite every factual claim.

## Required output

### CHANNEL COPY

Write the temporary channel copy.

### REVIEWER NOTES

List supporting sources and limitations.
"""
    (tmp_path / "email.md").write_text(template, encoding="utf-8")
    monkeypatch.setattr(prompt_templates, "_TEMPLATE_DIR", tmp_path)

    result = prompt_templates.build_prompt("email", "Brief", make_context())

    assert "Introductory template instruction." in result.trusted_instructions
    assert "Distinctive temporary grounding rule: cite every factual claim." in result.trusted_instructions
    assert "An empty reviewer feedback field means first draft" in result.trusted_instructions
    assert "{campaign_brief}" not in result.trusted_instructions


def test_linkedin_business_claim_rule_survives() -> None:
    result = prompt_templates.build_prompt("linkedin", "Brief", make_context())

    assert "Do not make unsupported business claims." in result.trusted_instructions


@pytest.mark.parametrize(
    "section_to_remove",
    ["## Inputs", "## Grounding and safety rules", "## Required output"],
)
def test_missing_structural_section_raises_template_validation_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, section_to_remove: str
) -> None:
    template = """## Inputs
{campaign_brief} {primary_context} {secondary_context} {feedback}
## Grounding and safety rules
Grounding rules.
## Required output
Output rules.
"""
    (tmp_path / "email.md").write_text(
        template.replace(section_to_remove, ""), encoding="utf-8"
    )
    monkeypatch.setattr(prompt_templates, "_TEMPLATE_DIR", tmp_path)

    with pytest.raises(prompt_templates.TemplateValidationError):
        prompt_templates.build_prompt("email", "Brief", make_context())


def test_duplicate_or_out_of_order_structural_sections_raise(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    template = """## Inputs
{campaign_brief} {primary_context} {secondary_context} {feedback}
## Required output
Output rules.
## Grounding and safety rules
Grounding rules.
## Required output
Duplicate output rules.
"""
    (tmp_path / "email.md").write_text(template, encoding="utf-8")
    monkeypatch.setattr(prompt_templates, "_TEMPLATE_DIR", tmp_path)

    with pytest.raises(prompt_templates.TemplateValidationError):
        prompt_templates.build_prompt("email", "Brief", make_context())


def test_working_directory_does_not_change_template_loading(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    result = prompt_templates.build_prompt("instagram", "Brief", make_context())

    assert "60–120 words" in result.trusted_instructions
