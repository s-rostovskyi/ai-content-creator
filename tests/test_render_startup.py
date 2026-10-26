"""Offline hosted-startup checks; all keys, vectors and corpus files are synthetic."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys

import pytest

from src.document_processor import load_knowledge_base_documents
from src.rag_chunking import build_rag_chunks
from src.rag_index import build_corpus_snapshot, write_vector_index
from src import rag_service

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("render_start_under_test", REPO_ROOT / "scripts/render_start.py")
render_start = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(render_start)


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    for pool in ("primary", "secondary"):
        path = tmp_path / "knowledge_base" / pool / "test.md"
        path.parent.mkdir(parents=True)
        path.write_text(f"# Test {pool}\n\n- Source URL: https://www.patagonia.com/test\n"
                        f"- Publisher: Test publisher\n- Published/updated: Not stated\n"
                        f"- Accessed: 2026-10-25\n- Knowledge base: {pool}\n"
                        "- Evidence type: official statement\n\n## Relevant facts\n\n- Synthetic test fact.\n",
                        encoding="utf-8")
    documents = load_knowledge_base_documents(tmp_path)
    chunks = build_rag_chunks(documents)
    seed = tmp_path / "deploy/seed.sqlite3"
    write_vector_index(seed, corpus_snapshot=build_corpus_snapshot(documents), chunks=chunks,
                       vectors_by_chunk_id={chunk.chunk_id: [1.0, 0.0] for chunk in chunks},
                       embedding_model_id="offline-test-model", vector_dimensions=2)
    for key, value in {
        "DEMO_ACCESS_ENABLED": "true", "DEMO_PASSWORD": "test-only-demo-password",
        "SOURCE_MANAGEMENT_ENABLED": "false", "OPENAI_MODEL": "offline-generation-model",
        "OPENAI_API_KEY": "test-only-not-a-real-key", "OPENAI_EMBEDDING_MODEL": "offline-test-model",
        "RAG_INDEX_VECTOR_DIMENSIONS": "2", "RAG_INDEX_BOOTSTRAP_SEED_PATH": "deploy/seed.sqlite3",
        "PORT": "18765",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(rag_service, "load_embedding_settings", lambda *a, **k: pytest.fail("Loaded credentials"))
    monkeypatch.setattr(rag_service, "embed_texts", lambda *a, **k: pytest.fail("Called API"))
    import dotenv
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: pytest.fail("Read .env"))
    return tmp_path, seed


def test_hosted_startup_restores_then_reuses_index_and_binds_render_port(prepared):
    root, _ = prepared
    command = render_start.prepare_render_startup(root)
    runtime = root / ".rag/rag_index.sqlite3"
    assert runtime.is_file()
    initial = runtime.read_bytes()
    assert command[:4] == [sys.executable, "-m", "streamlit", "run"]
    assert "--server.port=18765" in command
    assert "--server.address=0.0.0.0" in command
    assert "--browser.gatherUsageStats=false" in command
    assert render_start.prepare_render_startup(root) == command
    assert runtime.read_bytes() == initial


@pytest.mark.parametrize("key,value,match", [
    ("DEMO_ACCESS_ENABLED", "false", "DEMO_ACCESS_ENABLED"),
    ("DEMO_PASSWORD", "", "DEMO_PASSWORD"),
    ("SOURCE_MANAGEMENT_ENABLED", "true", "mutations"),
    ("OPENAI_API_KEY", "", "OPENAI_API_KEY"),
    ("OPENAI_MODEL", "", "OPENAI_MODEL"),
    ("RAG_INDEX_BOOTSTRAP_SEED_PATH", "", "SEED_PATH"),
    ("PORT", "not-a-port", "PORT"),
    ("PORT", "70000", "PORT"),
])
def test_unsafe_hosted_configuration_blocks_before_restoring(prepared, monkeypatch, key, value, match):
    root, _ = prepared
    monkeypatch.setenv(key, value)
    with pytest.raises(render_start.RenderStartupError, match=match):
        render_start.prepare_render_startup(root)
    assert not (root / ".rag/rag_index.sqlite3").exists()


@pytest.mark.parametrize("failure", ["missing", "corrupt", "stale", "model", "dimension"])
def test_bad_seed_blocks_and_preserves_existing_index(prepared, monkeypatch, failure):
    root, seed = prepared
    render_start.prepare_render_startup(root)
    runtime = root / ".rag/rag_index.sqlite3"
    original = runtime.read_bytes()
    if failure == "missing":
        seed.unlink()
    elif failure == "corrupt":
        seed.write_bytes(b"not sqlite; test-only-private-value")
    elif failure == "stale":
        path = root / "knowledge_base/primary/test.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n- Another synthetic fact.\n", encoding="utf-8")
    elif failure == "model":
        monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "different-test-model")
    else:
        monkeypatch.setenv("RAG_INDEX_VECTOR_DIMENSIONS", "3")
    with pytest.raises(render_start.RenderStartupError) as error:
        render_start.prepare_render_startup(root)
    assert "test-only-private-value" not in str(error.value)
    assert "test-only-demo-password" not in str(error.value)
    assert runtime.read_bytes() == original


def test_entry_point_checks_without_launch_and_does_not_launch_on_failure(prepared, monkeypatch):
    root, _ = prepared
    prepare = render_start.prepare_render_startup
    monkeypatch.setattr(render_start, "prepare_render_startup", lambda: prepare(root))
    calls = []
    monkeypatch.setattr(os, "execv", lambda executable, command: calls.append((executable, command)))
    assert render_start.main(["--check"]) == 0
    assert calls == []
    assert render_start.main([]) == 0
    assert len(calls) == 1
    monkeypatch.setenv("DEMO_PASSWORD", "")
    assert render_start.main([]) == 1
    assert len(calls) == 1


def test_isolated_streamlit_http_startup_smoke(prepared):
    """Real process/bind/HTTP check on loopback; not Linux/Render or live API acceptance."""
    import shutil
    import socket
    import subprocess
    import time
    import urllib.request
    root, _ = prepared
    shutil.copytree(REPO_ROOT / "src", root / "src")
    (root / "scripts").mkdir()
    shutil.copy2(REPO_ROOT / "scripts/render_start.py", root / "scripts/render_start.py")
    shutil.copy2(REPO_ROOT / "app.py", root / "app.py")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    env = {key: os.environ[key] for key in (
        "DEMO_ACCESS_ENABLED", "DEMO_PASSWORD", "SOURCE_MANAGEMENT_ENABLED", "OPENAI_MODEL",
        "OPENAI_API_KEY", "OPENAI_EMBEDDING_MODEL", "RAG_INDEX_VECTOR_DIMENSIONS", "RAG_INDEX_BOOTSTRAP_SEED_PATH",
    )}
    for key in ("PATH", "SystemRoot", "TEMP", "TMP"):
        if key in os.environ:
            env[key] = os.environ[key]
    env["PORT"] = str(port)
    env["PYTHONIOENCODING"] = "utf-8"
    # Keep both the HTTP listener and the synthetic user's home isolated.
    test_home = root / "test-home"
    test_home.mkdir()
    env["HOME"] = str(test_home)
    env["USERPROFILE"] = str(test_home)
    command = render_start.prepare_render_startup(root)
    command = [value.replace("--server.address=0.0.0.0", "--server.address=127.0.0.1") for value in command]
    # PORT is deliberately supplied by the child environment in the production path.
    command = [f"--server.port={port}" if value.startswith("--server.port=") else value for value in command]
    process = subprocess.Popen(command, cwd=root, env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 25
        last_error = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail("Isolated Streamlit exited before HTTP readiness: " + process.stderr.read().decode("utf-8", errors="replace"))
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=1) as response:
                    assert response.status == 200
                    assert response.read().strip() == b"ok"
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1) as response:
                    assert response.status == 200
                assert (root / ".rag/rag_index.sqlite3").is_file()
                return
            except OSError as error:
                last_error = error
                time.sleep(0.2)
        pytest.fail(f"Isolated HTTP readiness timed out: {type(last_error).__name__}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_hosted_startup_allows_reuse_rebuild_opt_in_with_sources_read_only(prepared, monkeypatch):
    root, _ = prepared
    monkeypatch.setenv("RAG_INDEX_BUILD_ENABLED", "true")
    command = render_start.prepare_render_startup(root)
    assert "--server.port=18765" in command
    monkeypatch.setenv("SOURCE_MANAGEMENT_ENABLED", "true")
    with pytest.raises(render_start.RenderStartupError, match="source mutations"):
        render_start.prepare_render_startup(root)
