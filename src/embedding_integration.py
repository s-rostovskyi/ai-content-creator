from __future__ import annotations

"""OpenAI embeddings adapter with offline-safe validation.

Character limits are preflight guards only; they do not count tokens. The
adapter never loads or creates a client at import time.
"""

import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable, Protocol, Sequence

from dotenv import load_dotenv
from openai import APIConnectionError, APITimeoutError, AuthenticationError, OpenAI, RateLimitError, APIStatusError

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_EMBEDDING_BATCH_SIZE = 32
DEFAULT_MAX_INPUT_CHARACTERS = 8192
DEFAULT_MAX_TOTAL_CHARACTERS = 32768


class OpenAIEmbeddingIntegrationError(Exception):
    """Base error for embeddings integration failures."""


class OpenAIEmbeddingConfigurationError(OpenAIEmbeddingIntegrationError):
    """Raised when required configuration or request arguments are invalid."""


class OpenAIEmbeddingRequestError(OpenAIEmbeddingIntegrationError):
    """Raised when the embeddings request fails for a sanitized non-auth reason."""


class OpenAIEmbeddingAuthenticationError(OpenAIEmbeddingIntegrationError):
    """Raised when authentication fails."""


class OpenAIEmbeddingRateLimitError(OpenAIEmbeddingIntegrationError):
    """Raised when the API rate limits a request."""


class OpenAIEmbeddingTimeoutError(OpenAIEmbeddingIntegrationError):
    """Raised when a request times out."""


class OpenAIEmbeddingConnectionError(OpenAIEmbeddingIntegrationError):
    """Raised when the client cannot connect to the API."""


class OpenAIEmbeddingResponseError(OpenAIEmbeddingIntegrationError):
    """Raised when the API returns a malformed embeddings response."""


@dataclass(frozen=True)
class OpenAIEmbeddingSettings:
    api_key: str = field(repr=False)
    model: str


@dataclass(frozen=True)
class EmbeddingUsageMetrics:
    prompt_tokens: int | None
    total_tokens: int | None


@dataclass(frozen=True)
class EmbeddedBatch:
    input_texts: tuple[str, ...]
    requested_model: str
    returned_model: str
    vectors: tuple[tuple[float, ...], ...]
    elapsed_seconds: float
    usage: EmbeddingUsageMetrics | None


class _EmbeddingsService(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class OpenAIEmbeddingsClientProtocol(Protocol):
    embeddings: _EmbeddingsService



def load_embedding_settings(repo_root: str | Path | None = None) -> OpenAIEmbeddingSettings:
    root_path = _resolve_repo_root(repo_root)
    load_dotenv(dotenv_path=root_path / '.env', override=False)

    api_key = os.getenv('OPENAI_API_KEY', '').strip()
    model = os.getenv('OPENAI_EMBEDDING_MODEL', '').strip()
    missing_fields = [name for name, value in (('OPENAI_API_KEY', api_key), ('OPENAI_EMBEDDING_MODEL', model)) if not value]
    if missing_fields:
        raise OpenAIEmbeddingConfigurationError(
            'Missing required OpenAI embedding configuration: ' + ', '.join(missing_fields)
        )
    return OpenAIEmbeddingSettings(api_key=api_key, model=model)



def build_openai_embeddings_client(
    settings: OpenAIEmbeddingSettings,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> OpenAI:
    _validate_timeout_seconds(timeout_seconds)
    return OpenAI(api_key=settings.api_key, max_retries=0, timeout=timeout_seconds)



def embed_texts(
    texts: Sequence[str],
    *,
    client: OpenAIEmbeddingsClientProtocol | None = None,
    settings: OpenAIEmbeddingSettings | None = None,
    max_batch_size: int = DEFAULT_MAX_EMBEDDING_BATCH_SIZE,
    max_input_characters: int = DEFAULT_MAX_INPUT_CHARACTERS,
    max_total_characters: int = DEFAULT_MAX_TOTAL_CHARACTERS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> EmbeddedBatch:
    normalized_texts = _validate_embedding_inputs(
        texts,
        max_batch_size=max_batch_size,
        max_input_characters=max_input_characters,
        max_total_characters=max_total_characters,
    )
    _validate_timeout_seconds(timeout_seconds)
    resolved_settings = settings or load_embedding_settings()
    active_client = client or build_openai_embeddings_client(resolved_settings, timeout_seconds=timeout_seconds)

    start = perf_counter()
    try:
        response = active_client.embeddings.create(
            input=list(normalized_texts),
            model=resolved_settings.model,
            encoding_format='float',
            timeout=timeout_seconds,
        )
    except AuthenticationError as exc:
        raise OpenAIEmbeddingAuthenticationError('OpenAI embedding authentication failed.') from exc
    except RateLimitError as exc:
        raise OpenAIEmbeddingRateLimitError('OpenAI embedding rate limit reached.') from exc
    except APITimeoutError as exc:
        raise OpenAIEmbeddingTimeoutError('OpenAI embedding request timed out.') from exc
    except APIConnectionError as exc:
        raise OpenAIEmbeddingConnectionError('OpenAI embedding connection failed.') from exc
    except APIStatusError as exc:
        raise OpenAIEmbeddingRequestError('OpenAI embedding request failed.') from exc
    except Exception as exc:  # pragma: no cover - defensive sanitization
        raise OpenAIEmbeddingRequestError('OpenAI embedding request failed.') from exc
    elapsed_seconds = perf_counter() - start
    returned_model = _require_nonempty_string(getattr(response, 'model', None), 'OpenAI returned an embedding response without a model name.')
    ordered_vectors = _order_embedding_vectors(getattr(response, 'data', None), expected_count=len(normalized_texts))
    usage = _extract_usage(getattr(response, 'usage', None))

    return EmbeddedBatch(
        input_texts=normalized_texts,
        requested_model=resolved_settings.model,
        returned_model=returned_model,
        vectors=ordered_vectors,
        elapsed_seconds=elapsed_seconds,
        usage=usage,
    )



def _validate_embedding_inputs(
    texts: Sequence[str],
    *,
    max_batch_size: int,
    max_input_characters: int,
    max_total_characters: int,
) -> tuple[str, ...]:
    if isinstance(texts, (str, bytes, bytearray)):
        raise OpenAIEmbeddingConfigurationError('Embedding requests must be provided as a nonempty batch of strings.')
    if isinstance(max_batch_size, bool) or not isinstance(max_batch_size, int) or max_batch_size <= 0:
        raise OpenAIEmbeddingConfigurationError('max_batch_size must be a positive integer.')
    if isinstance(max_input_characters, bool) or not isinstance(max_input_characters, int) or max_input_characters <= 0:
        raise OpenAIEmbeddingConfigurationError('max_input_characters must be a positive integer.')
    if isinstance(max_total_characters, bool) or not isinstance(max_total_characters, int) or max_total_characters <= 0:
        raise OpenAIEmbeddingConfigurationError('max_total_characters must be a positive integer.')

    try:
        normalized_texts = tuple(texts)
    except TypeError as exc:
        raise OpenAIEmbeddingConfigurationError('Embedding requests must be provided as an iterable of strings.') from exc

    if not normalized_texts:
        raise OpenAIEmbeddingConfigurationError('Embedding requests must contain at least one nonblank string.')
    if len(normalized_texts) > max_batch_size:
        raise OpenAIEmbeddingConfigurationError(f'Embedding batch size exceeds the configured limit of {max_batch_size}.')

    total_characters = 0
    for index, text in enumerate(normalized_texts):
        if not isinstance(text, str):
            raise OpenAIEmbeddingConfigurationError(f'Embedding input at position {index} must be a string.')
        if not text.strip():
            raise OpenAIEmbeddingConfigurationError(f'Embedding input at position {index} must not be blank.')
        if len(text) > max_input_characters:
            raise OpenAIEmbeddingConfigurationError(
                f'Embedding input at position {index} exceeds the configured character limit of {max_input_characters}.',
            )
        total_characters += len(text)
    if total_characters > max_total_characters:
        raise OpenAIEmbeddingConfigurationError(
            f'Embedding batch exceeds the configured total character limit of {max_total_characters}.',
        )
    return normalized_texts



def _order_embedding_vectors(data: Any, *, expected_count: int) -> tuple[tuple[float, ...], ...]:
    if data is None:
        raise OpenAIEmbeddingResponseError('OpenAI returned an embeddings response without data.')
    items = list(data)
    if not items:
        raise OpenAIEmbeddingResponseError('OpenAI returned an embeddings response without vectors.')

    ordered_vectors: list[tuple[float, ...] | None] = [None] * expected_count
    seen_indices: set[int] = set()
    expected_dimension: int | None = None

    for item in items:
        index = getattr(item, 'index', None)
        if isinstance(index, bool) or not isinstance(index, int):
            raise OpenAIEmbeddingResponseError('OpenAI returned an embedding response with an invalid index.')
        if index < 0 or index >= expected_count:
            raise OpenAIEmbeddingResponseError('OpenAI returned an embedding response with an out-of-range index.')
        if index in seen_indices:
            raise OpenAIEmbeddingResponseError('OpenAI returned duplicate embedding indices.')

        vector = _validate_embedding_vector(getattr(item, 'embedding', None), index=index)
        if expected_dimension is None:
            expected_dimension = len(vector)
        elif len(vector) != expected_dimension:
            raise OpenAIEmbeddingResponseError('OpenAI returned embeddings with inconsistent dimensions.')

        ordered_vectors[index] = vector
        seen_indices.add(index)

    if len(seen_indices) != expected_count or any(vector is None for vector in ordered_vectors):
        raise OpenAIEmbeddingResponseError('OpenAI returned an incomplete embeddings response.')

    return tuple(vector for vector in ordered_vectors if vector is not None)



def _validate_embedding_vector(vector: Any, *, index: int) -> tuple[float, ...]:
    try:
        values = tuple(float(value) for value in vector)
    except TypeError as exc:
        raise OpenAIEmbeddingResponseError(f'OpenAI returned a non-iterable embedding at index {index}.') from exc
    except ValueError as exc:
        raise OpenAIEmbeddingResponseError(f'OpenAI returned a non-numeric embedding at index {index}.') from exc
    if not values:
        raise OpenAIEmbeddingResponseError(f'OpenAI returned an empty embedding at index {index}.')
    if not all(math.isfinite(value) for value in values):
        raise OpenAIEmbeddingResponseError(f'OpenAI returned a non-finite embedding at index {index}.')
    if _vector_norm(values) == 0.0:
        raise OpenAIEmbeddingResponseError(f'OpenAI returned a zero embedding at index {index}.')
    return values



def _extract_usage(usage: Any) -> EmbeddingUsageMetrics | None:
    if usage is None:
        return None
    return EmbeddingUsageMetrics(
        prompt_tokens=_optional_int(getattr(usage, 'prompt_tokens', None)),
        total_tokens=_optional_int(getattr(usage, 'total_tokens', None)),
    )



def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value



def _vector_norm(vector: Sequence[float]) -> float:
    return math.sqrt(math.fsum(value * value for value in vector))



def _validate_timeout_seconds(timeout_seconds: float) -> None:
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
        raise OpenAIEmbeddingConfigurationError('timeout_seconds must be a finite positive number.')
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise OpenAIEmbeddingConfigurationError('timeout_seconds must be a finite positive number.')



def _resolve_repo_root(repo_root: str | Path | None) -> Path:
    if repo_root is None:
        return Path(__file__).resolve().parents[1]
    return Path(repo_root).resolve()



def _require_nonempty_string(value: Any, error_message: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    raise OpenAIEmbeddingResponseError(error_message)


__all__ = [
    'DEFAULT_MAX_EMBEDDING_BATCH_SIZE',
    'DEFAULT_MAX_INPUT_CHARACTERS',
    'DEFAULT_MAX_TOTAL_CHARACTERS',
    'DEFAULT_TIMEOUT_SECONDS',
    'EmbeddedBatch',
    'EmbeddingUsageMetrics',
    'OpenAIEmbeddingAuthenticationError',
    'OpenAIEmbeddingConfigurationError',
    'OpenAIEmbeddingConnectionError',
    'OpenAIEmbeddingIntegrationError',
    'OpenAIEmbeddingRateLimitError',
    'OpenAIEmbeddingRequestError',
    'OpenAIEmbeddingResponseError',
    'OpenAIEmbeddingSettings',
    'OpenAIEmbeddingTimeoutError',
    'OpenAIEmbeddingsClientProtocol',
    'build_openai_embeddings_client',
    'embed_texts',
    'load_embedding_settings',
]
