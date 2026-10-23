from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.rag_service import build_rag_index, plan_rag_index_build, render_rag_build_plan, render_rag_build_result


def _sanitize_error(exc: Exception) -> str:
    return str(exc).strip() or exc.__class__.__name__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RAG index build orchestrator")
    parser.add_argument("--live", action="store_true", help="perform the live index build")
    parser.add_argument("--index-path", type=Path, default=None, help="override the runtime index path")
    parser.add_argument(
        "--embedding-model",
        default=None,
        help="explicit embedding model for dry-run planning or live override checks",
    )
    parser.add_argument(
        "--max-batch-size",
        type=int,
        default=None,
        help="override the embedding batch size limit",
    )
    parser.add_argument(
        "--max-input-characters",
        type=int,
        default=None,
        help="override the per-input character limit",
    )
    parser.add_argument(
        "--max-total-characters",
        type=int,
        default=None,
        help="override the per-batch character limit",
    )
    args = parser.parse_args(argv)

    service_kwargs = {
        "repo_root": REPO_ROOT,
        "index_path": args.index_path,
        "embedding_model_id": args.embedding_model,
    }
    if args.max_batch_size is not None:
        service_kwargs["max_batch_size"] = args.max_batch_size
    if args.max_input_characters is not None:
        service_kwargs["max_input_characters"] = args.max_input_characters
    if args.max_total_characters is not None:
        service_kwargs["max_total_characters"] = args.max_total_characters

    try:
        if args.live:
            result = build_rag_index(**service_kwargs)
            print(render_rag_build_result(result))
        else:
            plan = plan_rag_index_build(**service_kwargs)
            print(render_rag_build_plan(plan))
    except Exception as exc:
        print(f"Error: {_sanitize_error(exc)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
