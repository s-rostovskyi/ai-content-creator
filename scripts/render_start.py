"""Fail-closed offline startup for the read-only Render demo (card 6.1, M5/M8).

Never loads .env, constructs an API client, builds embeddings or installs packages.
The native Streamlit health endpoint indicates server liveness, not model quality.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.rag_service import RagServiceError, bootstrap_rag_index_from_seed, validate_rag_index_seed


class RenderStartupError(Exception):
    """A safe, actionable deployment configuration error."""


def prepare_render_startup(repo_root: Path = REPO_ROOT) -> list[str]:
    if os.getenv("DEMO_ACCESS_ENABLED", "").strip().lower() != "true":
        raise RenderStartupError("Set DEMO_ACCESS_ENABLED=true for the hosted demo.")
    if not os.getenv("DEMO_PASSWORD", "").strip():
        raise RenderStartupError("Set a nonblank DEMO_PASSWORD privately in Render Environment.")
    if os.getenv("SOURCE_MANAGEMENT_ENABLED", "").strip().lower() not in ("", "false"):
        raise RenderStartupError("Hosted source mutations must be disabled: SOURCE_MANAGEMENT_ENABLED=false. Explicit reuse-only rebuilds use RAG_INDEX_BUILD_ENABLED.")
    for name in ("OPENAI_MODEL", "OPENAI_API_KEY", "OPENAI_EMBEDDING_MODEL", "RAG_INDEX_VECTOR_DIMENSIONS"):
        if not os.getenv(name, "").strip():
            raise RenderStartupError(f"Set {name} in Render Environment.")
    raw_port = os.getenv("PORT", "10000").strip()
    try:
        port = int(raw_port)
    except ValueError:
        raise RenderStartupError("PORT must be a number between 1 and 65535.") from None
    if not 1 <= port <= 65535:
        raise RenderStartupError("PORT must be a number between 1 and 65535.")
    root = Path(repo_root).resolve()
    raw_seed = os.getenv("RAG_INDEX_BOOTSTRAP_SEED_PATH", "").strip()
    if not raw_seed:
        raise RenderStartupError("Set RAG_INDEX_BOOTSTRAP_SEED_PATH to the approved deployment seed.")
    seed = Path(raw_seed)
    if not seed.is_absolute():
        seed = root / seed
    if not seed.is_file():
        raise RenderStartupError("The prepared deployment seed is missing. Package and publish the compatible seed before deploying.")
    try:
        validate_rag_index_seed(repo_root=root, seed_path=seed)
        bootstrap_rag_index_from_seed(repo_root=root, seed_path=seed)
    except (RagServiceError, OSError):
        raise RenderStartupError(
            "Prepared index restore failed. Check seed, corpus snapshot, embedding model, version and dimensions. "
            "No embedding rebuild or API call was attempted."
        ) from None
    return [sys.executable, "-m", "streamlit", "run", str(root / "app.py"),
            "--server.address=0.0.0.0", f"--server.port={port}", "--server.headless=true",
            "--browser.gatherUsageStats=false"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline-validated Render demo startup")
    parser.add_argument("--check", action="store_true", help="validate configuration and restore/reuse the runtime index without starting a server")
    args = parser.parse_args(argv)
    try:
        command = prepare_render_startup()
    except RenderStartupError as exc:
        print(f"Render startup blocked: {exc}", file=sys.stderr)
        return 1
    print("Render startup preflight passed; compatible runtime index available.", flush=True)
    if args.check:
        return 0
    os.execv(sys.executable, command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
