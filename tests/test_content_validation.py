from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.content_validation import format_validation_summary, validate_channel_format


def _words(count: int) -> str:
    return " ".join(f"w{index}" for index in range(1, count + 1))


def _email_copy(*, subject: str, preheader: str, body: str, cta: str | None = None) -> str:
    parts = [f"Subject: {subject}", "", f"Preheader: {preheader}", "", f"Body: {body}"]
    if cta is not None:
        parts.extend(["", cta])
    return "\n".join(parts)


@pytest.mark.parametrize(
    ("word_count", "expected_passed"),
    [
        (60, True),
        (120, True),
        (59, False),
        (121, False),
    ],
)
def test_instagram_word_count_boundaries(word_count: int, expected_passed: bool) -> None:
    validation = validate_channel_format("instagram", _words(word_count))

    assert validation.passed is expected_passed
    assert validation.measurements.word_count == word_count
    if expected_passed:
        assert validation.warnings == ()
    else:
        assert any("Instagram captions must be 60-120 words" in warning for warning in validation.warnings)


@pytest.mark.parametrize(
    ("word_count", "hashtags", "expected_passed"),
    [
        (60, 3, True),
        (60, 4, False),
    ],
)
def test_instagram_hashtag_limit(word_count: int, hashtags: int, expected_passed: bool) -> None:
    copy = _words(word_count) + (" " + " ".join(f"#tag{index}" for index in range(1, hashtags + 1)) if hashtags else "")
    validation = validate_channel_format("instagram", copy)

    assert validation.passed is expected_passed
    assert validation.measurements.hashtag_count == hashtags
    if expected_passed:
        assert validation.warnings == ()
    else:
        assert any("at most 3 hashtags" in warning for warning in validation.warnings)


@pytest.mark.parametrize(
    ("word_count", "expected_passed"),
    [
        (120, True),
        (200, True),
        (119, False),
        (201, False),
    ],
)
def test_linkedin_word_count_boundaries(word_count: int, expected_passed: bool) -> None:
    validation = validate_channel_format("linkedin", _words(word_count))

    assert validation.passed is expected_passed
    assert validation.measurements.word_count == word_count
    if expected_passed:
        assert validation.warnings == ()
    else:
        assert any("LinkedIn posts must be 120-200 words" in warning for warning in validation.warnings)


@pytest.mark.parametrize(
    ("subject_chars", "preheader_chars", "body_words", "expected_passed"),
    [
        (50, 90, 150, True),
        (51, 90, 150, False),
        (50, 91, 150, False),
        (50, 90, 149, False),
        (50, 90, 250, True),
    ],
)
def test_email_section_boundaries_without_cta(subject_chars: int, preheader_chars: int, body_words: int, expected_passed: bool) -> None:
    validation = validate_channel_format(
        "email",
        _email_copy(
            subject="S" * subject_chars,
            preheader="P" * preheader_chars,
            body=_words(body_words),
            cta=None,
        ),
    )

    assert validation.measurements.subject_char_count == subject_chars
    assert validation.measurements.preheader_char_count == preheader_chars
    assert validation.measurements.body_word_count == body_words
    assert validation.passed is expected_passed
    if expected_passed:
        assert validation.warnings == ()
        assert validation.email_sections is not None
        assert validation.email_sections.cta is None
        assert format_validation_summary(validation).startswith("Email copy: ")
    else:
        assert any("Email" in warning for warning in validation.warnings)


def test_email_inline_cta_is_accepted_without_a_separate_label() -> None:
    validation = validate_channel_format(
        "email",
        _email_copy(
            subject="Ready to pack",
            preheader="A small layer for shifting weather",
            body=" ".join([f"w{index}" for index in range(1, 150)]) + " Explore the details of the jacket.",
            cta=None,
        ),
    )

    assert validation.passed is True
    assert validation.email_sections is not None
    assert validation.email_sections.cta is None
    assert validation.measurements.body_word_count == 155
    assert validation.warnings == ()


def test_email_separate_cta_is_counted_once_in_body_length() -> None:
    validation = validate_channel_format(
        "email",
        _email_copy(
            subject="Ready to pack",
            preheader="A small layer for shifting weather",
            body=_words(145),
            cta="CTA: Explore the details of the jacket.",
        ),
    )

    assert validation.passed is True
    assert validation.email_sections is not None
    assert validation.email_sections.cta == "Explore the details of the jacket."
    assert validation.measurements.body_word_count == 151
    assert validation.warnings == ()


def test_email_separate_cta_can_lift_body_into_range() -> None:
    validation = validate_channel_format(
        "email",
        _email_copy(
            subject="Ready to pack",
            preheader="A small layer for shifting weather",
            body=_words(143),
            cta="CTA: Explore the details of the jacket now.",
        ),
    )

    assert validation.passed is True
    assert validation.email_sections is not None
    assert validation.measurements.body_word_count == 150
    assert validation.warnings == ()


@pytest.mark.parametrize(
    ("copy", "expected_warning_fragment"),
    [
        (
            "Subject: Ready\n\nBody: " + _words(150),
            "missing a Preheader: section",
        ),
        (
            "Subject: Ready\n\nSubject: Duplicate\n\nPreheader: Preview\n\nBody: " + _words(150),
            "multiple Subject: sections",
        ),
    ],
)
def test_email_missing_or_duplicate_labels_are_reported(copy: str, expected_warning_fragment: str) -> None:
    validation = validate_channel_format("email", copy)

    assert validation.passed is False
    assert any(expected_warning_fragment in warning for warning in validation.warnings)
    assert validation.email_sections is None


@pytest.mark.parametrize(
    ("copy", "expected_warning_fragment"),
    [
        (
            _email_copy(subject="", preheader="Preview text", body=_words(150)),
            "Email subject cannot be blank.",
        ),
        (
            _email_copy(subject="Ready", preheader="", body=_words(150)),
            "Email preheader cannot be blank.",
        ),
        (
            _email_copy(subject="Ready", preheader="Preview text", body=""),
            "Email body cannot be blank.",
        ),
        (
            _email_copy(subject="Ready", preheader="Preview text", body=_words(150), cta="CTA: "),
            "Email CTA cannot be blank.",
        ),
        (
            _email_copy(
                subject="Ready",
                preheader="Preview text",
                body=_words(150),
                cta="CTA: One\nCTA: Two",
            ),
            "multiple CTA: sections",
        ),
    ],
)
def test_email_blank_or_duplicate_sections_are_reported(copy: str, expected_warning_fragment: str) -> None:
    validation = validate_channel_format("email", copy)

    assert validation.passed is False
    assert any(expected_warning_fragment in warning for warning in validation.warnings)


def test_preserved_email_acceptance_artifact_parses_structurally() -> None:
    artifact_path = Path("docs/evidence/channel-acceptance/email-rev2-20261022T222413Z-105918ca.json")
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    validation = validate_channel_format("email", artifact["channel_copy"])

    assert validation.email_sections is not None
    assert validation.email_sections.subject
    assert validation.email_sections.preheader
    assert validation.email_sections.body
    assert validation.email_sections.cta is None
    assert not any("missing" in warning.lower() for warning in validation.warnings)
