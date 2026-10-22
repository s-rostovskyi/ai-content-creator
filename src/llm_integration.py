from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol

from dotenv import load_dotenv
from openai import APIConnectionError, APITimeoutError, AuthenticationError, OpenAI, RateLimitError, APIStatusError

DEFAULT_MAX_OUTPUT_TOKENS = 512
DEFAULT_TIMEOUT_SECONDS = 30.0
MIN_MAX_OUTPUT_TOKENS = 1
MAX_MAX_OUTPUT_TOKENS = 4096


class OpenAIIntegrationError(Exception):
    """Base error for OpenAI client integration failures."""


class OpenAIConfigurationError(OpenAIIntegrationError):
    """Raised when required configuration is missing or invalid."""


class OpenAIRequestError(OpenAIIntegrationError):
    """Raised when the OpenAI request fails for a sanitized non-auth reason."""


class OpenAIAuthenticationError(OpenAIIntegrationError):
    """Raised when authentication fails."""


class OpenAIRateLimitError(OpenAIIntegrationError):
    """Raised when the API rate limits a request."""


class OpenAITimeoutError(OpenAIIntegrationError):
    """Raised when a request times out."""


class OpenAIConnectionError(OpenAIIntegrationError):
    """Raised when the client cannot connect to the API."""


class OpenAIIncompleteResponseError(OpenAIIntegrationError):
    """Raised when the API returns a non-final response."""


class OpenAIEmptyOutputError(OpenAIIntegrationError):
    """Raised when the API returns no usable text output."""


@dataclass(frozen=True)
class OpenAISettings:
    api_key: str = field(repr=False)
    model: str


@dataclass(frozen=True)
class UsageMetrics:
    input_tokens: int | None
    input_tokens_details: dict[str, int] | None
    output_tokens: int | None
    output_tokens_details: dict[str, int] | None
    total_tokens: int | None


@dataclass(frozen=True)
class GeneratedText:
    generated_text: str
    response_id: str
    model: str
    elapsed_seconds: float
    usage: UsageMetrics | None


class _ResponsesService(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class OpenAIClientProtocol(Protocol):
    responses: _ResponsesService



def load_openai_settings(repo_root: str | Path | None = None) -> OpenAISettings:
    root_path = _resolve_repo_root(repo_root)
    load_dotenv(dotenv_path=root_path / ".env", override=False)

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "").strip()
    missing_fields = [name for name, value in (("OPENAI_API_KEY", api_key), ("OPENAI_MODEL", model)) if not value]
    if missing_fields:
        raise OpenAIConfigurationError(
            "Missing required OpenAI configuration: " + ", ".join(missing_fields)
        )
    return OpenAISettings(api_key=api_key, model=model)



def build_openai_client(settings: OpenAISettings, *, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> OpenAI:
    _validate_timeout_seconds(timeout_seconds)
    return OpenAI(api_key=settings.api_key, max_retries=0, timeout=timeout_seconds)



def generate_response(
    instructions: str,
    user_input: str,
    *,
    client: OpenAIClientProtocol | None = None,
    settings: OpenAISettings | None = None,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> GeneratedText:
    _validate_generation_arguments(instructions, user_input, max_output_tokens, timeout_seconds)
    resolved_settings = settings or load_openai_settings()
    active_client = client or build_openai_client(resolved_settings, timeout_seconds=timeout_seconds)

    start = perf_counter()
    try:
        response = active_client.responses.create(
            model=resolved_settings.model,
            instructions=instructions,
            input=user_input,
            max_output_tokens=max_output_tokens,
            timeout=timeout_seconds,
        )
    except AuthenticationError as exc:
        raise OpenAIAuthenticationError("OpenAI authentication failed.") from exc
    except RateLimitError as exc:
        raise OpenAIRateLimitError("OpenAI rate limit reached.") from exc
    except APITimeoutError as exc:
        raise OpenAITimeoutError("OpenAI request timed out.") from exc
    except APIConnectionError as exc:
        raise OpenAIConnectionError("OpenAI connection failed.") from exc
    except APIStatusError as exc:
        raise OpenAIRequestError("OpenAI request failed.") from exc
    elapsed_seconds = perf_counter() - start

    if getattr(response, "status", None) != "completed" or getattr(response, "incomplete_details", None) is not None:
        raise OpenAIIncompleteResponseError("OpenAI returned an incomplete response.")

    generated_text = _extract_generated_text(response)
    if not generated_text.strip():
        raise OpenAIEmptyOutputError("OpenAI returned no usable text output.")

    return GeneratedText(
        generated_text=generated_text,
        response_id=str(getattr(response, "id", "")),
        model=str(getattr(response, "model", resolved_settings.model)),
        elapsed_seconds=elapsed_seconds,
        usage=_extract_usage(getattr(response, "usage", None)),
    )



def _validate_generation_arguments(
    instructions: str,
    user_input: str,
    max_output_tokens: int,
    timeout_seconds: float,
) -> None:
    if not isinstance(instructions, str) or not instructions.strip():
        raise OpenAIConfigurationError("Instructions must be a non-empty string.")
    if not isinstance(user_input, str) or not user_input.strip():
        raise OpenAIConfigurationError("User input must be a non-empty string.")
    if isinstance(max_output_tokens, bool) or not isinstance(max_output_tokens, int):
        raise OpenAIConfigurationError("max_output_tokens must be an integer between 1 and 4096.")
    if not MIN_MAX_OUTPUT_TOKENS <= max_output_tokens <= MAX_MAX_OUTPUT_TOKENS:
        raise OpenAIConfigurationError("max_output_tokens must be an integer between 1 and 4096.")
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
        raise OpenAIConfigurationError("timeout_seconds must be a finite positive number.")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise OpenAIConfigurationError("timeout_seconds must be a finite positive number.")



def _validate_timeout_seconds(timeout_seconds: float) -> None:
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
        raise OpenAIConfigurationError("timeout_seconds must be a finite positive number.")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise OpenAIConfigurationError("timeout_seconds must be a finite positive number.")



def _resolve_repo_root(repo_root: str | Path | None) -> Path:
    if repo_root is None:
        return Path(__file__).resolve().parents[1]
    return Path(repo_root).resolve()



def _extract_generated_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    output_items = getattr(response, "output", None) or []
    text_chunks: list[str] = []
    for message in output_items:
        if getattr(message, "type", None) != "message":
            continue
        for content_item in getattr(message, "content", []) or []:
            if getattr(content_item, "type", None) == "output_text":
                text = getattr(content_item, "text", "")
                if text:
                    text_chunks.append(str(text))
    return "".join(text_chunks)



def _extract_usage(usage: Any) -> UsageMetrics | None:
    if usage is None:
        return None
    return UsageMetrics(
        input_tokens=_optional_int(getattr(usage, "input_tokens", None)),
        input_tokens_details=_int_mapping(getattr(usage, "input_tokens_details", None)),
        output_tokens=_optional_int(getattr(usage, "output_tokens", None)),
        output_tokens_details=_int_mapping(getattr(usage, "output_tokens_details", None)),
        total_tokens=_optional_int(getattr(usage, "total_tokens", None)),
    )



def _int_mapping(details: Any) -> dict[str, int] | None:
    if details is None:
        return None
    if hasattr(details, "model_dump"):
        raw = details.model_dump()
    elif isinstance(details, dict):
        raw = details
    else:
        raw = getattr(details, "__dict__", {})
    mapping: dict[str, int] = {}
    for key, value in raw.items():
        if isinstance(value, int):
            mapping[str(key)] = value
    return mapping or None



def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
