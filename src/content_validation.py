from __future__ import annotations

from dataclasses import dataclass
import re


INSTAGRAM_WORD_MIN = 60
INSTAGRAM_WORD_MAX = 120
INSTAGRAM_HASHTAG_MAX = 3

LINKEDIN_WORD_MIN = 120
LINKEDIN_WORD_MAX = 200

EMAIL_SUBJECT_CHAR_MAX = 50
EMAIL_PREHEADER_CHAR_MAX = 90
EMAIL_BODY_WORD_MIN = 150
EMAIL_BODY_WORD_MAX = 250

_HASHTAG_PATTERN = re.compile(r"(?<!\w)#\w[\w-]*")
_EMAIL_LABEL_PATTERN = re.compile(r"^(Subject|Preheader|Body|CTA):\s*(.*)$")


@dataclass(frozen=True)
class FormatMeasurements:
    word_count: int
    hashtag_count: int | None = None
    subject_char_count: int | None = None
    preheader_char_count: int | None = None
    body_word_count: int | None = None
    cta_word_count: int | None = None


@dataclass(frozen=True)
class EmailSections:
    subject: str
    preheader: str
    body: str
    cta: str | None


@dataclass(frozen=True)
class ChannelFormatValidation:
    channel: str
    passed: bool
    measurements: FormatMeasurements
    warnings: tuple[str, ...]
    email_sections: EmailSections | None = None


def validate_channel_format(channel: str, channel_copy: str) -> ChannelFormatValidation:
    if channel == "instagram":
        return _validate_instagram(channel_copy)
    if channel == "linkedin":
        return _validate_linkedin(channel_copy)
    if channel == "email":
        return _validate_email(channel_copy)
    raise ValueError(f"Unsupported channel: {channel}")


def format_validation_summary(validation: ChannelFormatValidation) -> str:
    if validation.channel == "instagram":
        measurements = validation.measurements
        return (
            f"Instagram caption: {measurements.word_count} words; "
            f"{measurements.hashtag_count or 0} hashtags."
        )
    if validation.channel == "linkedin":
        measurements = validation.measurements
        return f"LinkedIn post: {measurements.word_count} words."
    measurements = validation.measurements
    if validation.email_sections is None:
        return "Email copy could not be parsed into Subject, Preheader and Body sections."
    return (
        "Email copy: "
        f"{measurements.word_count} words total; "
        f"subject {measurements.subject_char_count or 0}/{EMAIL_SUBJECT_CHAR_MAX} chars; "
        f"preheader {measurements.preheader_char_count or 0}/{EMAIL_PREHEADER_CHAR_MAX} chars; "
        f"body {measurements.body_word_count or 0}/{EMAIL_BODY_WORD_MAX} words."
    )


def _validate_instagram(channel_copy: str) -> ChannelFormatValidation:
    word_count = _word_count(channel_copy)
    hashtag_count = len(_HASHTAG_PATTERN.findall(channel_copy))
    warnings: list[str] = []
    if word_count < INSTAGRAM_WORD_MIN or word_count > INSTAGRAM_WORD_MAX:
        warnings.append(
            f"Instagram captions must be {INSTAGRAM_WORD_MIN}-{INSTAGRAM_WORD_MAX} words; current draft is {word_count}."
        )
    if hashtag_count > INSTAGRAM_HASHTAG_MAX:
        warnings.append(f"Instagram captions may use at most {INSTAGRAM_HASHTAG_MAX} hashtags; current draft has {hashtag_count}.")
    return ChannelFormatValidation(
        channel="instagram",
        passed=not warnings,
        measurements=FormatMeasurements(word_count=word_count, hashtag_count=hashtag_count),
        warnings=tuple(warnings),
    )


def _validate_linkedin(channel_copy: str) -> ChannelFormatValidation:
    word_count = _word_count(channel_copy)
    warnings: list[str] = []
    if word_count < LINKEDIN_WORD_MIN or word_count > LINKEDIN_WORD_MAX:
        warnings.append(
            f"LinkedIn posts must be {LINKEDIN_WORD_MIN}-{LINKEDIN_WORD_MAX} words; current draft is {word_count}."
        )
    return ChannelFormatValidation(
        channel="linkedin",
        passed=not warnings,
        measurements=FormatMeasurements(word_count=word_count),
        warnings=tuple(warnings),
    )


def _validate_email(channel_copy: str) -> ChannelFormatValidation:
    word_count = _word_count(channel_copy)
    lines = channel_copy.splitlines()
    issues: list[str] = []

    subject_indices = _find_label_indices(lines, "Subject")
    preheader_indices = _find_label_indices(lines, "Preheader")
    body_indices = _find_label_indices(lines, "Body")
    cta_indices = _find_label_indices(lines, "CTA")

    if len(subject_indices) != 1:
        issues.append("Email copy is missing a Subject: section." if not subject_indices else "Email copy contains multiple Subject: sections.")
    if len(preheader_indices) != 1:
        issues.append("Email copy is missing a Preheader: section." if not preheader_indices else "Email copy contains multiple Preheader: sections.")
    if len(body_indices) != 1:
        issues.append("Email copy is missing a Body: section." if not body_indices else "Email copy contains multiple Body: sections.")

    if len(subject_indices) != 1 or len(preheader_indices) != 1 or len(body_indices) != 1:
        measurements = FormatMeasurements(word_count=word_count)
        return ChannelFormatValidation(
            channel="email",
            passed=False,
            measurements=measurements,
            warnings=tuple(issues),
        )

    subject_index = subject_indices[0]
    preheader_index = preheader_indices[0]
    body_index = body_indices[0]
    cta_index = cta_indices[0] if len(cta_indices) == 1 else None

    if len(cta_indices) > 1:
        issues.append("Email copy contains multiple CTA: sections.")

    if not (subject_index < preheader_index < body_index):
        issues.append("Email sections must appear in the order Subject, Preheader, Body.")

    subject_text = _section_text(lines, subject_index, preheader_index)
    preheader_text = _section_text(lines, preheader_index, body_index)

    if cta_index is not None and cta_index > body_index:
        body_end = cta_index
        cta_text = _section_text(lines, cta_index, len(lines))
        cta_word_count = _word_count(cta_text)
    else:
        body_end = len(lines)
        cta_text = None
        cta_word_count = 0

    body_text = _section_text(lines, body_index, body_end)

    if not subject_text:
        issues.append("Email subject cannot be blank.")
    if not preheader_text:
        issues.append("Email preheader cannot be blank.")
    if not body_text:
        issues.append("Email body cannot be blank.")
    if cta_index is not None and not cta_text:
        issues.append("Email CTA cannot be blank.")

    subject_chars = len(subject_text)
    preheader_chars = len(preheader_text)
    body_word_count = _word_count(body_text) + cta_word_count

    if subject_chars > EMAIL_SUBJECT_CHAR_MAX:
        issues.append(
            f"Email subject must be at most {EMAIL_SUBJECT_CHAR_MAX} characters; current draft is {subject_chars}."
        )
    if preheader_chars > EMAIL_PREHEADER_CHAR_MAX:
        issues.append(
            f"Email preheader must be at most {EMAIL_PREHEADER_CHAR_MAX} characters; current draft is {preheader_chars}."
        )
    if body_word_count < EMAIL_BODY_WORD_MIN or body_word_count > EMAIL_BODY_WORD_MAX:
        issues.append(
            f"Email body must be {EMAIL_BODY_WORD_MIN}-{EMAIL_BODY_WORD_MAX} words; current draft is {body_word_count}."
        )

    sections = EmailSections(subject=subject_text, preheader=preheader_text, body=body_text, cta=cta_text)
    return ChannelFormatValidation(
        channel="email",
        passed=not issues,
        measurements=FormatMeasurements(
            word_count=word_count,
            subject_char_count=subject_chars,
            preheader_char_count=preheader_chars,
            body_word_count=body_word_count,
            cta_word_count=cta_word_count,
        ),
        warnings=tuple(issues),
        email_sections=sections,
    )


def _find_label_indices(lines: list[str], label: str) -> list[int]:
    return [index for index, line in enumerate(lines) if _line_label(line) == label]


def _line_label(line: str) -> str | None:
    match = _EMAIL_LABEL_PATTERN.match(line.strip())
    if match is None:
        return None
    return match.group(1)


def _section_text(lines: list[str], start_index: int | None, end_index: int) -> str:
    if start_index is None:
        return ""
    section_line = lines[start_index].strip()
    section_lines = lines[start_index + 1 : end_index]
    match = _EMAIL_LABEL_PATTERN.match(section_line)
    head = match.group(2) if match is not None else section_line
    if section_lines:
        return "\n".join([head, *section_lines]).strip()
    return head.strip()

def _word_count(text: str) -> int:
    return len(text.split()) if text.strip() else 0


__all__ = [
    "ChannelFormatValidation",
    "EmailSections",
    "FormatMeasurements",
    "format_validation_summary",
    "validate_channel_format",
]
