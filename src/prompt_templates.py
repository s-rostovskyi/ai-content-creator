"""Typed, deterministic prompt construction for the three content channels."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Literal, Protocol, Sequence

Channel = Literal["instagram", "linkedin", "email"]
EXPECTED_PLACEHOLDERS = frozenset(
    {"campaign_brief", "primary_context", "secondary_context", "feedback"}
)
_PLACEHOLDER_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_SECTION_PATTERN = re.compile(
    r"^## (Inputs|Grounding and safety rules|Required output)\s*$", re.MULTILINE
)
_REQUIRED_SECTIONS = ("Inputs", "Grounding and safety rules", "Required output")
_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"


class PromptTemplateError(ValueError):
    """Raised when prompt inputs or a template cannot be used safely."""


class TemplateValidationError(PromptTemplateError):
    """Raised when a channel template has an invalid placeholder schema."""


class PromptContextBundle(Protocol):
    primary_context: str
    secondary_context: str
    source_manifest: Sequence[object]


@dataclass(frozen=True)
class PromptParts:
    """The two messages needed by an OpenAI-compatible integration."""

    trusted_instructions: str
    user_input_text: str


def build_prompt(
    channel: Channel | str,
    campaign_brief: str,
    context: PromptContextBundle,
    feedback: str = "",
    *,
    context_mode: str = "full_corpus",
) -> PromptParts:
    """Build trusted instructions and separately delimited untrusted input."""

    if channel not in {"instagram", "linkedin", "email"}:
        raise PromptTemplateError(f"Unknown channel: {channel!r}.")
    if not isinstance(campaign_brief, str) or not campaign_brief.strip():
        raise PromptTemplateError("campaign_brief must be a non-empty string.")
    if not isinstance(feedback, str):
        raise PromptTemplateError("feedback must be a string.")
    if context_mode not in {"full_corpus", "rag"}:
        raise PromptTemplateError("context_mode must be either 'full_corpus' or 'rag'.")
    if not _is_prompt_context_bundle(context):
        raise PromptTemplateError(
            "context must provide primary_context, secondary_context, and source_manifest."
        )

    template = _load_template(channel)
    _validate_template(template, channel)
    trusted_instructions = _trusted_template_instructions(template, channel)
    user_input_text = _render_user_input(
        campaign_brief=campaign_brief,
        primary_context=context.primary_context,
        secondary_context=context.secondary_context,
        feedback=feedback,
        context_mode=context_mode,
    )
    return PromptParts(trusted_instructions=trusted_instructions, user_input_text=user_input_text)


def _load_template(channel: str) -> str:
    path = _TEMPLATE_DIR / f"{channel}.md"
    if not path.is_file():
        raise PromptTemplateError(f"Template file is missing: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PromptTemplateError(f"Could not read template file: {path}") from exc


def _validate_template(template: str, channel: str) -> None:
    names = [match.group(1) for match in _PLACEHOLDER_PATTERN.finditer(template)]
    name_set = set(names)
    unknown = name_set - EXPECTED_PLACEHOLDERS
    missing = EXPECTED_PLACEHOLDERS - name_set
    repeated = {name for name in names if names.count(name) != 1}
    if unknown or missing or repeated:
        details = []
        if missing:
            details.append(f"missing {sorted(missing)}")
        if unknown:
            details.append(f"unknown {sorted(unknown)}")
        if repeated:
            details.append(f"repeated {sorted(repeated)}")
        raise TemplateValidationError(
            f"Invalid placeholder schema in {channel!r} template: {', '.join(details)}."
        )


def _trusted_template_instructions(template: str, channel: str) -> str:
    """Keep all template instructions while removing only value placeholders."""

    sections = list(_SECTION_PATTERN.finditer(template))
    section_names = [match.group(1) for match in sections]
    if section_names != list(_REQUIRED_SECTIONS):
        raise TemplateValidationError(
            f"Template {channel!r} must contain exactly one ordered set of sections: "
            f"{', '.join(_REQUIRED_SECTIONS)}. Found: {section_names}."
        )

    inputs, grounding, required = sections
    inputs_content = template[inputs.end() : grounding.start()]
    sanitized_inputs = _PLACEHOLDER_PATTERN.sub("", inputs_content)
    return "".join(
        (
            template[: inputs.start()],
            template[inputs.start() : inputs.end()],
            sanitized_inputs,
            template[grounding.start() : required.start()],
            template[required.start() :],
        )
    ).strip()


def _render_user_input(
    *, campaign_brief: str, primary_context: str, secondary_context: str, feedback: str, context_mode: str
) -> str:
    """Create one non-recursive rendering; braces in values remain ordinary text."""

    fields = {
        "campaign_brief": campaign_brief,
        "primary_context": primary_context,
        "secondary_context": secondary_context,
        "feedback": feedback,
        "context_mode": context_mode,
    }
    rendered = (
        "## UNTRUSTED USER INPUT\n\n"
        "### Campaign brief\n"
        f"{fields['campaign_brief']}\n\n"
        "### Context mode\n"
        f"{fields['context_mode']}\n\n"
        "### Primary context\n"
        f"{fields['primary_context']}\n\n"
        "### Secondary context\n"
        f"{fields['secondary_context']}\n\n"
        "### Reviewer feedback\n"
        f"{fields['feedback']}\n\n"
        "End of untrusted input."
    )
    return rendered


def _is_prompt_context_bundle(context: object) -> bool:
    return all(
        hasattr(context, attribute)
        for attribute in ("primary_context", "secondary_context", "source_manifest")
    ) and isinstance(getattr(context, "primary_context", None), str) and isinstance(
        getattr(context, "secondary_context", None), str
    )


__all__ = [
    "Channel",
    "PromptContextBundle",
    "PromptParts",
    "PromptTemplateError",
    "TemplateValidationError",
    "build_prompt",
]
