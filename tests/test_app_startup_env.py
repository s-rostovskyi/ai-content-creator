from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _prepare_temp_app_repo(tmp_path: Path, env_text: str | None) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / "app.py", repo_root / "app.py")
    shutil.copytree(REPO_ROOT / "src", repo_root / "src")
    if env_text is not None:
        (repo_root / ".env").write_text(env_text, encoding="utf-8")
    return repo_root


def _load_app_module(repo_root: Path):
    module_name = f"temp_app_{repo_root.name}_{id(repo_root)}"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, repo_root / "app.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_app_enables_source_management_when_repo_env_sets_true(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = _prepare_temp_app_repo(tmp_path, "SOURCE_MANAGEMENT_ENABLED=true\n")
    monkeypatch.syspath_prepend(str(repo_root))
    monkeypatch.delenv("SOURCE_MANAGEMENT_ENABLED", raising=False)

    module = _load_app_module(repo_root)

    assert module.SOURCE_MANAGEMENT_ENABLED is True


@pytest.mark.parametrize("env_text", [None, "SOURCE_MANAGEMENT_ENABLED=false\n"])
def test_app_defaults_source_management_disabled_when_repo_env_is_missing_or_false(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    env_text: str | None,
) -> None:
    repo_root = _prepare_temp_app_repo(tmp_path, env_text)
    monkeypatch.syspath_prepend(str(repo_root))
    monkeypatch.delenv("SOURCE_MANAGEMENT_ENABLED", raising=False)

    module = _load_app_module(repo_root)

    assert module.SOURCE_MANAGEMENT_ENABLED is False


@pytest.mark.parametrize("process_value", ["true", "false"])
def test_app_prefers_existing_environment_over_repo_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    process_value: str,
) -> None:
    repo_root = _prepare_temp_app_repo(tmp_path, "SOURCE_MANAGEMENT_ENABLED=false\n")
    monkeypatch.syspath_prepend(str(repo_root))
    monkeypatch.setenv("SOURCE_MANAGEMENT_ENABLED", process_value)

    module = _load_app_module(repo_root)

    assert module.SOURCE_MANAGEMENT_ENABLED is (process_value == "true")


def test_app_loads_repo_env_independently_of_working_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = _prepare_temp_app_repo(tmp_path, "SOURCE_MANAGEMENT_ENABLED=true\n")
    unrelated_cwd = tmp_path / "unrelated-workdir"
    unrelated_cwd.mkdir()
    monkeypatch.chdir(unrelated_cwd)
    monkeypatch.syspath_prepend(str(repo_root))
    monkeypatch.delenv("SOURCE_MANAGEMENT_ENABLED", raising=False)

    module = _load_app_module(repo_root)

    assert module.SOURCE_MANAGEMENT_ENABLED is True
