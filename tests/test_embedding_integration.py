from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from openai import AuthenticationError

from src.embedding_integration import (
    DEFAULT_MAX_EMBEDDING_BATCH_SIZE,
    DEFAULT_MAX_INPUT_CHARACTERS,
    OpenAIEmbeddingConfigurationError,
    OpenAIEmbeddingResponseError,
    OpenAIEmbeddingSettings,
    OpenAIEmbeddingAuthenticationError,
    OpenAIEmbeddingRequestError,
    EmbeddedBatch,
    build_openai_embeddings_client,
    embed_texts,
    load_embedding_settings,
)


class FakeEmbeddingsService:
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
        self.embeddings = FakeEmbeddingsService(response=response, exc=exc)


class ExplodingOpenAI:
    def __init__(self, *args, **kwargs) -> None:
        raise AssertionError('client should not be constructed during settings loading')



def _httpx_response(status_code: int) -> httpx.Response:
    request = httpx.Request('POST', 'https://api.openai.com/v1/embeddings')
    return httpx.Response(status_code, request=request)



def _build_embedding_response(*, model: str = 'text-embedding-3-small', data: list[SimpleNamespace] | None = None, usage: object | None = None) -> SimpleNamespace:
    if data is None:
        data = [
            SimpleNamespace(index=1, embedding=[0.0, 1.0]),
            SimpleNamespace(index=0, embedding=[1.0, 0.0]),
        ]
    return SimpleNamespace(model=model, data=data, usage=usage)



def test_load_embedding_settings_respects_env_precedence_and_repo_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = tmp_path / 'repo'
    repo_root.mkdir()
    (repo_root / '.env').write_text(
        'OPENAI_API_KEY=file-key\nOPENAI_EMBEDDING_MODEL=file-model\n',
        encoding='utf-8',
    )
    monkeypatch.setenv('OPENAI_API_KEY', 'env-key')
    monkeypatch.setenv('OPENAI_EMBEDDING_MODEL', 'env-model')
    (tmp_path / 'elsewhere').mkdir()
    monkeypatch.chdir(tmp_path / 'elsewhere')

    settings = load_embedding_settings(repo_root)

    assert settings == OpenAIEmbeddingSettings(api_key='env-key', model='env-model')
    assert 'env-key' not in repr(settings)



def test_load_embedding_settings_does_not_construct_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = tmp_path / 'repo'
    repo_root.mkdir()
    (repo_root / '.env').write_text(
        'OPENAI_API_KEY=file-key\nOPENAI_EMBEDDING_MODEL=file-model\n',
        encoding='utf-8',
    )
    monkeypatch.setattr('src.embedding_integration.OpenAI', ExplodingOpenAI)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_EMBEDDING_MODEL', raising=False)

    settings = load_embedding_settings(repo_root)

    assert settings == OpenAIEmbeddingSettings(api_key='file-key', model='file-model')



def test_embed_texts_orders_vectors_and_captures_usage(tmp_path: Path) -> None:
    response = _build_embedding_response(
        model='text-embedding-3-small',
        usage=SimpleNamespace(prompt_tokens=7, total_tokens=7),
    )
    fake_client = FakeClient(response=response)
    settings = OpenAIEmbeddingSettings(api_key='test-key', model='text-embedding-3-small')

    result = embed_texts(
        ['first chunk', 'second chunk'],
        client=fake_client,
        settings=settings,
        timeout_seconds=1.25,
    )

    assert isinstance(result, EmbeddedBatch)
    assert result.requested_model == 'text-embedding-3-small'
    assert result.returned_model == 'text-embedding-3-small'
    assert result.vectors == ((1.0, 0.0), (0.0, 1.0))
    assert result.usage == type(result.usage)(prompt_tokens=7, total_tokens=7)
    assert result.elapsed_seconds >= 0
    assert fake_client.embeddings.calls[0]['input'] == ['first chunk', 'second chunk']
    assert fake_client.embeddings.calls[0]['model'] == 'text-embedding-3-small'
    assert fake_client.embeddings.calls[0]['encoding_format'] == 'float'
    assert fake_client.embeddings.calls[0]['timeout'] == 1.25


@pytest.mark.parametrize(
    'response',
    [
        _build_embedding_response(data=[SimpleNamespace(index=0, embedding=[1.0, 0.0])]),
        _build_embedding_response(data=[SimpleNamespace(index=0, embedding=[1.0, 0.0]), SimpleNamespace(index=0, embedding=[0.0, 1.0])]),
        _build_embedding_response(data=[SimpleNamespace(index=0, embedding=[1.0, float('nan')]), SimpleNamespace(index=1, embedding=[0.0, 1.0])]),
    ],
)
def test_embed_texts_rejects_malformed_response_payloads(response: SimpleNamespace) -> None:
    fake_client = FakeClient(response=response)
    settings = OpenAIEmbeddingSettings(api_key='test-key', model='text-embedding-3-small')

    with pytest.raises(OpenAIEmbeddingResponseError):
        embed_texts(['alpha', 'beta'], client=fake_client, settings=settings)


@pytest.mark.parametrize(
    'texts, kwargs',
    [
        ([], {}),
        (['   '], {}),
        (['alpha', 'beta', 'gamma'], {'max_batch_size': 2}),
        (['x' * (DEFAULT_MAX_INPUT_CHARACTERS + 1)], {}),
        (['alpha', 123], {}),
    ],
)
def test_embed_texts_rejects_invalid_inputs_before_client_call(texts, kwargs):
    fake_client = FakeClient(response=_build_embedding_response())
    settings = OpenAIEmbeddingSettings(api_key='test-key', model='text-embedding-3-small')

    with pytest.raises(OpenAIEmbeddingConfigurationError):
        embed_texts(texts, client=fake_client, settings=settings, **kwargs)

    assert fake_client.embeddings.calls == []


@pytest.mark.parametrize(
    'exc, expected_error',
    [
        (AuthenticationError('bad key', response=_httpx_response(401), body=None), OpenAIEmbeddingAuthenticationError),
        (RuntimeError('secret-token-should-not-leak'), OpenAIEmbeddingRequestError),
    ],
)
def test_embed_texts_sanitizes_failure_paths(exc: Exception, expected_error: type[Exception]) -> None:
    fake_client = FakeClient(exc=exc)
    settings = OpenAIEmbeddingSettings(api_key='test-key', model='text-embedding-3-small')

    with pytest.raises(expected_error) as exc_info:
        embed_texts(['alpha'], client=fake_client, settings=settings)

    message = str(exc_info.value)
    assert 'bad key' not in message
    assert 'secret-token-should-not-leak' not in message



def test_build_openai_embeddings_client_disables_retries() -> None:
    client = build_openai_embeddings_client(
        OpenAIEmbeddingSettings(api_key='test-key', model='text-embedding-3-small'),
        timeout_seconds=5.0,
    )

    assert client.max_retries == 0
