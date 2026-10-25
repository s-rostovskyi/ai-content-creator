from __future__ import annotations

"""Streamlit-facing adapter around the deterministic RAG retrieval layer."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.content_pipeline import ContentPipelineError, GenerationContextProvider, PipelineSession, ResolvedGenerationContext
from src.embedding_integration import (
    DEFAULT_TIMEOUT_SECONDS,
    OpenAIEmbeddingSettings,
    OpenAIEmbeddingsClientProtocol,
)
from src.rag_retrieval import (
    DEFAULT_MAX_CONTEXT_CHARACTERS,
    DEFAULT_PRIMARY_MINIMUM_SIMILARITY,
    DEFAULT_PRIMARY_TOP_K,
    DEFAULT_SECONDARY_MINIMUM_SIMILARITY,
    DEFAULT_SECONDARY_TOP_K,
    RagRetrievalError,
    RetrievalBlockedError,
    RetrievalConfigurationError,
    RetrievalStaleCorpusError,
    build_rag_retrieval_evidence_payload,
    plan_rag_context_retrieval,
    retrieve_rag_context,
)
from src.rag_service import resolve_runtime_index_path

RagIndexState = Literal["ready", "missing", "stale", "incompatible"]


class RagContextError(ContentPipelineError):
    """Base error for Streamlit-facing RAG context failures."""


class RagContextUnavailableError(RagContextError):
    """Raised when the local index or configuration cannot support RAG."""


class RagContextBlockedError(RagContextError):
    """Raised when retrieval runs but does not produce usable primary evidence."""


@dataclass(frozen=True)
class RagIndexStatus:
    state: RagIndexState
    message: str
    details: str
    index_path: Path
    corpus_snapshot_id: str
    existing_index_matches: bool | None
    existing_index_reason: str
    embedding_model_id: str | None


@dataclass(frozen=True)
class RagContextSettings:
    repo_root: Path
    index_path: Path | None = None
    embedding_model_id: str | None = None
    primary_top_k: int = DEFAULT_PRIMARY_TOP_K
    secondary_top_k: int = DEFAULT_SECONDARY_TOP_K
    primary_minimum_similarity: float = DEFAULT_PRIMARY_MINIMUM_SIMILARITY
    secondary_minimum_similarity: float = DEFAULT_SECONDARY_MINIMUM_SIMILARITY
    max_context_characters: int = DEFAULT_MAX_CONTEXT_CHARACTERS
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS


class LiveRagContextProvider(GenerationContextProvider):
    def __init__(
        self,
        *,
        repo_root: str | Path,
        index_path: str | Path | None = None,
        embedding_model_id: str | None = None,
        settings: OpenAIEmbeddingSettings | None = None,
        client: OpenAIEmbeddingsClientProtocol | None = None,
        primary_top_k: int = DEFAULT_PRIMARY_TOP_K,
        secondary_top_k: int = DEFAULT_SECONDARY_TOP_K,
        primary_minimum_similarity: float = DEFAULT_PRIMARY_MINIMUM_SIMILARITY,
        secondary_minimum_similarity: float = DEFAULT_SECONDARY_MINIMUM_SIMILARITY,
        max_context_characters: int = DEFAULT_MAX_CONTEXT_CHARACTERS,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._settings = RagContextSettings(
            repo_root=Path(repo_root).resolve(),
            index_path=None if index_path is None else Path(index_path),
            embedding_model_id=embedding_model_id,
            primary_top_k=primary_top_k,
            secondary_top_k=secondary_top_k,
            primary_minimum_similarity=primary_minimum_similarity,
            secondary_minimum_similarity=secondary_minimum_similarity,
            max_context_characters=max_context_characters,
            timeout_seconds=timeout_seconds,
        )
        self._openai_settings = settings
        self._client = client

    @property
    def repo_root(self) -> Path:
        return self._settings.repo_root

    @property
    def index_path(self) -> Path:
        return resolve_runtime_index_path(self._settings.repo_root, self._settings.index_path)

    def describe_status(
        self,
        *,
        channel: str,
        campaign_brief: str,
        revision_feedback: str = "",
    ) -> RagIndexStatus:
        del revision_feedback
        resolved_model = self._resolved_embedding_model_id()
        plan = plan_rag_context_retrieval(
            repo_root=self._settings.repo_root,
            index_path=self._settings.index_path,
            channel=channel,
            campaign_brief=campaign_brief,
            embedding_model_id=resolved_model,
            primary_top_k=self._settings.primary_top_k,
            secondary_top_k=self._settings.secondary_top_k,
            primary_minimum_similarity=self._settings.primary_minimum_similarity,
            secondary_minimum_similarity=self._settings.secondary_minimum_similarity,
            max_context_characters=self._settings.max_context_characters,
        )
        state, message = self._classify_plan(plan)
        details = self._build_status_details(plan)
        return RagIndexStatus(
            state=state,
            message=message,
            details=details,
            index_path=plan.index_path,
            corpus_snapshot_id=plan.corpus_snapshot.snapshot_id,
            existing_index_matches=plan.existing_index_matches,
            existing_index_reason=plan.existing_index_reason,
            embedding_model_id=plan.embedding_model_id,
        )

    def resolve(
        self,
        session: PipelineSession,
        *,
        revision_feedback: str = "",
        current_draft=None,
    ) -> ResolvedGenerationContext:
        del current_draft
        try:
            result = retrieve_rag_context(
                repo_root=self._settings.repo_root,
                index_path=self._settings.index_path,
                channel=session.channel,
                campaign_brief=session.campaign_brief,
                revision_feedback=revision_feedback,
                product_id=getattr(session, "product_id", None),
                embedding_model_id=self._resolved_embedding_model_id(),
                settings=self._openai_settings,
                client=self._client,
                primary_top_k=self._settings.primary_top_k,
                secondary_top_k=self._settings.secondary_top_k,
                primary_minimum_similarity=self._settings.primary_minimum_similarity,
                secondary_minimum_similarity=self._settings.secondary_minimum_similarity,
                max_context_characters=self._settings.max_context_characters,
                timeout_seconds=self._settings.timeout_seconds,
            )
        except RetrievalBlockedError as exc:
            raise RagContextBlockedError(str(exc) or "RAG retrieval did not produce usable primary evidence.") from exc
        except (RetrievalConfigurationError, RetrievalStaleCorpusError) as exc:
            raise RagContextUnavailableError(str(exc) or exc.__class__.__name__) from exc
        except RagRetrievalError as exc:
            raise RagContextUnavailableError(str(exc) or "RAG retrieval failed.") from exc

        if result.blocked_reason is not None or result.context_bundle is None:
            raise RagContextBlockedError(result.blocked_reason or "RAG retrieval did not produce usable primary evidence.")

        provenance = build_rag_retrieval_evidence_payload(result, channel=session.channel, retrieval_settings=self._retrieval_settings())
        provenance["product_id"] = getattr(session, "product_id", None)
        return ResolvedGenerationContext(
            context_mode="rag",
            prompt_context=result.context_bundle,
            retrieval_provenance=provenance,
        )

    def _resolved_embedding_model_id(self) -> str | None:
        if self._settings.embedding_model_id is not None:
            normalized = self._settings.embedding_model_id.strip()
            return normalized or None
        return None

    def _retrieval_settings(self) -> dict[str, object]:
        return {
            "index_path": str(self.index_path),
            "embedding_model_id": self._resolved_embedding_model_id(),
            "primary_top_k": self._settings.primary_top_k,
            "secondary_top_k": self._settings.secondary_top_k,
            "primary_minimum_similarity": self._settings.primary_minimum_similarity,
            "secondary_minimum_similarity": self._settings.secondary_minimum_similarity,
            "max_context_characters": self._settings.max_context_characters,
            "timeout_seconds": self._settings.timeout_seconds,
        }

    @staticmethod
    def _classify_plan(plan) -> tuple[RagIndexState, str]:
        if plan.existing_index_matches is True:
            return "ready", "RAG index ready."
        if plan.existing_index_reason == "missing":
            return "missing", f"No local RAG index was found at {plan.index_path}."
        if plan.existing_index_reason == "snapshot_mismatch":
            return "stale", "The local RAG index was built from an older source snapshot."
        return "incompatible", "The local RAG index does not match the configured embedding model or settings."

    @staticmethod
    def _build_status_details(plan) -> str:
        model_text = plan.embedding_model_id or "unresolved"
        return (
            f"Index: {plan.index_path} | Corpus snapshot: {plan.corpus_snapshot.snapshot_id} | "
            f"Model: {model_text} | Existing index: {plan.existing_index_reason}"
        )


__all__ = [
    "LiveRagContextProvider",
    "RagContextBlockedError",
    "RagContextError",
    "RagContextSettings",
    "RagContextUnavailableError",
    "RagIndexStatus",
    "RagIndexState",
]
