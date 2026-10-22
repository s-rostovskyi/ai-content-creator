from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError, AuthenticationError, RateLimitError, APIStatusError

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.llm_integration import (
    GeneratedText,
    OpenAIAuthenticationError,
    OpenAIConfigurationError,
    OpenAIConnectionError,
    OpenAIEmptyOutputError,
    OpenAIIncompleteResponseError,
    OpenAIRateLimitError,
    OpenAITimeoutError,
    OpenAIRequestError,
    OpenAISettings,
    UsageMetrics,
    build_openai_client,
    generate_response,
    load_openai_settings,
)


class FakeResponsesService:
    def __init__(self, response: object | None = None, exc: Exception | None = None) -> None:
        self.response = response
        self.exc = exc
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc is not None:
            raise self.exc
        return self.response


class FakeClient:
    def __init__(self, response: object | None = None, exc: Exception | None = None) -> None:
        self.responses = FakeResponsesService(response=response, exc=exc)


class FakeResponse:
    def __init__(
        self,
        *,
        text: str = "Generated text.",
        response_id: str = "resp_test",
        model: str = "gpt-5.4-mini",
        status: str = "completed",
        usage: object | None = None,
        incomplete_details: object | None = None,
    ) -> None:
        self.id = response_id
        self.model = model
        self.status = status
        self.incomplete_details = incomplete_details
        self.usage = usage
        self.output_text = text
        self.output = [
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type="output_text", text=text)],
            )
        ]



def _httpx_response(status_code: int) -> httpx.Response:
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    return httpx.Response(status_code, request=request)



def _httpx_request() -> httpx.Request:
    return httpx.Request("POST", "https://api.openai.com/v1/responses")



def test_load_openai_settings_reads_root_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=file-key\nOPENAI_MODEL=file-model\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    settings = load_openai_settings(tmp_path)

    assert settings == OpenAISettings(api_key="file-key", model="file-model")
    assert "file-key" not in repr(settings)



def test_load_openai_settings_does_not_override_existing_process_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=file-key\nOPENAI_MODEL=file-model\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_MODEL", "env-model")

    settings = load_openai_settings(tmp_path)

    assert settings == OpenAISettings(api_key="env-key", model="env-model")


@pytest.mark.parametrize(
    ("env_key", "env_model", "expected_fragment"),
    [
        (None, None, "OPENAI_API_KEY, OPENAI_MODEL"),
        ("present", None, "OPENAI_MODEL"),
        (None, "present", "OPENAI_API_KEY"),
    ],
)
def test_load_openai_settings_requires_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    env_key: str | None,
    env_model: str | None,
    expected_fragment: str,
) -> None:
    (tmp_path / ".env").write_text("", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    if env_key is not None:
        monkeypatch.setenv("OPENAI_API_KEY", env_key)
    if env_model is not None:
        monkeypatch.setenv("OPENAI_MODEL", env_model)

    with pytest.raises(OpenAIConfigurationError) as exc_info:
        load_openai_settings(tmp_path)

    assert expected_fragment in str(exc_info.value)



def test_generate_response_returns_text_usage_and_request_parameters() -> None:
    usage = SimpleNamespace(
        input_tokens=11,
        input_tokens_details=SimpleNamespace(cached_tokens=3, cache_write_tokens=1),
        output_tokens=7,
        output_tokens_details=SimpleNamespace(reasoning_tokens=2),
        total_tokens=18,
    )
    fake_client = FakeClient(response=FakeResponse(text="Approved output.", usage=usage, response_id="resp_123"))
    settings = OpenAISettings(api_key="test-key", model="gpt-5.4-mini")

    result = generate_response(
        "Write in a concise brand voice.",
        "Draft a launch announcement.",
        client=fake_client,
        settings=settings,
        max_output_tokens=123,
        timeout_seconds=7.5,
    )

    assert isinstance(result, GeneratedText)
    assert result.generated_text == "Approved output."
    assert result.response_id == "resp_123"
    assert result.model == "gpt-5.4-mini"
    assert result.elapsed_seconds >= 0.0
    assert result.usage == UsageMetrics(
        input_tokens=11,
        input_tokens_details={"cached_tokens": 3, "cache_write_tokens": 1},
        output_tokens=7,
        output_tokens_details={"reasoning_tokens": 2},
        total_tokens=18,
    )

    call = fake_client.responses.calls[0]
    assert call["model"] == "gpt-5.4-mini"
    assert call["instructions"] == "Write in a concise brand voice."
    assert call["input"] == "Draft a launch announcement."
    assert call["max_output_tokens"] == 123
    assert call["timeout"] == 7.5
    assert "temperature" not in call


@pytest.mark.parametrize(
    ("exc", "expected_error"),
    [
        (AuthenticationError("bad key", response=_httpx_response(401), body=None), OpenAIAuthenticationError),
        (RateLimitError("too many requests", response=_httpx_response(429), body=None), OpenAIRateLimitError),
        (APITimeoutError(_httpx_request()), OpenAITimeoutError),
        (APIConnectionError(message="connect failed", request=_httpx_request()), OpenAIConnectionError),
        (APIStatusError("server failed", response=_httpx_response(500), body=None), OpenAIRequestError),
    ],
)
def test_generate_response_sanitizes_sdk_failures(
    exc: Exception,
    expected_error: type[Exception],
) -> None:
    fake_client = FakeClient(exc=exc)
    settings = OpenAISettings(api_key="test-key", model="gpt-5.4-mini")

    with pytest.raises(expected_error) as exc_info:
        generate_response("Instructions", "Input", client=fake_client, settings=settings)

    message = str(exc_info.value)
    assert "bad key" not in message
    assert "too many requests" not in message
    assert "connect failed" not in message
    assert "server failed" not in message



def test_generate_response_rejects_incomplete_and_empty_output() -> None:
    incomplete_client = FakeClient(
        response=FakeResponse(
            text="partial output",
            status="incomplete",
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        )
    )
    empty_client = FakeClient(response=FakeResponse(text="", response_id="resp_empty"))
    settings = OpenAISettings(api_key="test-key", model="gpt-5.4-mini")

    with pytest.raises(OpenAIIncompleteResponseError):
        generate_response("Instructions", "Input", client=incomplete_client, settings=settings)

    with pytest.raises(OpenAIEmptyOutputError):
        generate_response("Instructions", "Input", client=empty_client, settings=settings)


@pytest.mark.parametrize(
    "invalid_max_output_tokens",
    [0, 4097, True, 1.5, "10"],
)
def test_generate_response_rejects_invalid_max_output_tokens_without_request(
    invalid_max_output_tokens: object,
) -> None:
    fake_client = FakeClient(response=FakeResponse())
    settings = OpenAISettings(api_key="test-key", model="gpt-5.4-mini")

    with pytest.raises(OpenAIConfigurationError):
        generate_response(
            "Instructions",
            "Input",
            client=fake_client,
            settings=settings,
            max_output_tokens=invalid_max_output_tokens,  # type: ignore[arg-type]
        )

    assert fake_client.responses.calls == []


@pytest.mark.parametrize(
    "invalid_timeout_seconds",
    [0, -1, True, float("inf"), float("nan"), "5"],
)
def test_generate_response_rejects_invalid_timeout_without_request(
    invalid_timeout_seconds: object,
) -> None:
    fake_client = FakeClient(response=FakeResponse())
    settings = OpenAISettings(api_key="test-key", model="gpt-5.4-mini")

    with pytest.raises(OpenAIConfigurationError):
        generate_response(
            "Instructions",
            "Input",
            client=fake_client,
            settings=settings,
            timeout_seconds=invalid_timeout_seconds,  # type: ignore[arg-type]
        )

    assert fake_client.responses.calls == []


@pytest.mark.parametrize(
    "invalid_texts",
    [
        ("", "Input"),
        ("   ", "Input"),
        ("Instructions", ""),
        ("Instructions", "   "),
    ],
)
def test_generate_response_rejects_blank_inputs_without_request(
    invalid_texts: tuple[str, str],
) -> None:
    fake_client = FakeClient(response=FakeResponse())
    settings = OpenAISettings(api_key="test-key", model="gpt-5.4-mini")
    instructions, user_input = invalid_texts

    with pytest.raises(OpenAIConfigurationError):
        generate_response(instructions, user_input, client=fake_client, settings=settings)

    assert fake_client.responses.calls == []



def test_build_openai_client_disables_retries() -> None:
    client = build_openai_client(OpenAISettings(api_key="test-key", model="gpt-5.4-mini"), timeout_seconds=12.0)

    assert client.max_retries == 0
