from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.evaluation_runner import render_run_json, run_evaluation


def _sanitize_error(exc: Exception) -> str:
    return str(exc).strip() or exc.__class__.__name__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generic-versus-contextual evaluation runner")
    parser.add_argument("--live", action="store_true", help="perform the six live OpenAI requests")
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=None,
        help="optional base directory under docs/evaluation/runs for live outputs",
    )
    args = parser.parse_args(argv)

    try:
        result = run_evaluation(live=args.live, repo_root=REPO_ROOT, runs_dir=args.runs_dir)
    except Exception as exc:
        print(f"Error: {_sanitize_error(exc)}", file=sys.stderr)
        return 1

    print(render_run_json(result))
    if result.error is not None:
        print(f"Error: {result.error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
