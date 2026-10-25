from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.product_catalog import PRODUCTS
from src.rag_retrieval import (
    DEFAULT_MAX_CONTEXT_CHARACTERS,
    DEFAULT_PRIMARY_MINIMUM_SIMILARITY,
    DEFAULT_PRIMARY_TOP_K,
    DEFAULT_SECONDARY_MINIMUM_SIMILARITY,
    DEFAULT_SECONDARY_TOP_K,
    RagRetrievalError,
    build_rag_retrieval_evidence_payload,
    plan_rag_context_retrieval,
    render_rag_retrieval_plan,
    render_rag_retrieval_result,
    retrieve_rag_context,
)


def _sanitize_error(exc: Exception) -> str:
    return str(exc).strip() or exc.__class__.__name__


def _preflight_evidence_destination(destination: Path) -> Path:
    resolved = destination.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    if resolved.exists():
        raise RagRetrievalError(f"Evidence path already exists: {resolved}")
    return resolved



def _save_rag_retrieval_evidence(
    destination: Path,
    result,
    *,
    channel: str,
    retrieval_settings: dict[str, object],
) -> None:
    resolved = _preflight_evidence_destination(destination)
    payload = build_rag_retrieval_evidence_payload(
        result,
        channel=channel,
        retrieval_settings=retrieval_settings,
        saved_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    )
    tmp_file = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=str(resolved.parent),
            prefix=f"{resolved.name}.",
            suffix=".tmp",
        ) as handle:
            tmp_file = Path(handle.name)
            json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if resolved.exists():
            raise RagRetrievalError(f"Evidence path already exists: {resolved}")
        tmp_file.replace(resolved)
    except Exception:
        if tmp_file is not None and tmp_file.exists():
            tmp_file.unlink()
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RAG retrieval orchestrator")
    parser.add_argument("--live", action="store_true", help="perform the live retrieval request")
    parser.add_argument("--channel", required=True, help="target content channel")
    parser.add_argument("--product", choices=tuple(PRODUCTS), default=None, help="restrict retrieval to a prepared product; omitted retains legacy unscoped mode")
    parser.add_argument("--brief", required=True, help="shared campaign brief")
    parser.add_argument("--feedback", default="", help="optional revision feedback")
    parser.add_argument("--index-path", type=Path, default=None, help="override the runtime index path")
    parser.add_argument("--embedding-model", default=None, help="explicit embedding model to validate")
    parser.add_argument("--primary-top-k", type=int, default=None, help="override the primary search depth")
    parser.add_argument("--secondary-top-k", type=int, default=None, help="override the secondary search depth")
    parser.add_argument(
        "--primary-minimum-similarity",
        type=float,
        default=None,
        help="override the primary cosine threshold",
    )
    parser.add_argument(
        "--secondary-minimum-similarity",
        type=float,
        default=None,
        help="override the secondary cosine threshold",
    )
    parser.add_argument(
        "--max-context-characters",
        type=int,
        default=None,
        help="override the retrieved-context character budget",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=None,
        help="override the embedding request timeout",
    )
    parser.add_argument(
        "--save-evidence",
        type=Path,
        default=None,
        help="write a retrieval evidence JSON file after a live retrieval",
    )
    args = parser.parse_args(argv)

    resolved_primary_top_k = args.primary_top_k if args.primary_top_k is not None else DEFAULT_PRIMARY_TOP_K
    resolved_secondary_top_k = args.secondary_top_k if args.secondary_top_k is not None else DEFAULT_SECONDARY_TOP_K
    resolved_primary_minimum_similarity = (
        args.primary_minimum_similarity if args.primary_minimum_similarity is not None else DEFAULT_PRIMARY_MINIMUM_SIMILARITY
    )
    resolved_secondary_minimum_similarity = (
        args.secondary_minimum_similarity if args.secondary_minimum_similarity is not None else DEFAULT_SECONDARY_MINIMUM_SIMILARITY
    )
    resolved_max_context_characters = (
        args.max_context_characters if args.max_context_characters is not None else DEFAULT_MAX_CONTEXT_CHARACTERS
    )
    resolved_timeout_seconds = args.timeout_seconds

    service_kwargs = {
        "repo_root": REPO_ROOT,
        "index_path": args.index_path,
        "channel": args.channel,
        "campaign_brief": args.brief,
        "revision_feedback": args.feedback,
        "embedding_model_id": args.embedding_model,
        "primary_top_k": resolved_primary_top_k,
        "secondary_top_k": resolved_secondary_top_k,
        "primary_minimum_similarity": resolved_primary_minimum_similarity,
        "secondary_minimum_similarity": resolved_secondary_minimum_similarity,
        "max_context_characters": resolved_max_context_characters,
    }
    if args.product is not None:
        service_kwargs["product_id"] = args.product
    if resolved_timeout_seconds is not None:
        service_kwargs["timeout_seconds"] = resolved_timeout_seconds

    retrieval_settings = {
        "product_id": args.product,
        "primary_top_k": resolved_primary_top_k,
        "secondary_top_k": resolved_secondary_top_k,
        "primary_minimum_similarity": resolved_primary_minimum_similarity,
        "secondary_minimum_similarity": resolved_secondary_minimum_similarity,
        "max_context_characters": resolved_max_context_characters,
        "timeout_seconds": resolved_timeout_seconds,
    }

    try:
        if args.save_evidence is not None and not args.live:
            raise RagRetrievalError("--save-evidence requires --live.")
        if args.save_evidence is not None:
            _preflight_evidence_destination(args.save_evidence)
        if args.live:
            result = retrieve_rag_context(**service_kwargs)
            print(render_rag_retrieval_result(result))
            if args.save_evidence is not None:
                _save_rag_retrieval_evidence(
                    args.save_evidence,
                    result,
                    channel=args.channel,
                    retrieval_settings=retrieval_settings,
                )
            return 1 if result.blocked_reason is not None else 0
        plan = plan_rag_context_retrieval(**service_kwargs)
        print(render_rag_retrieval_plan(plan))
    except RagRetrievalError as exc:
        print(f"Error: {_sanitize_error(exc)}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {_sanitize_error(exc)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
