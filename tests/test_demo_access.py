from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src import demo_access, rag_service

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def demo_env(monkeypatch):
    import dotenv
    # Never load the owner's local credential file during these tests.
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.setenv("DEMO_ACCESS_ENABLED", "true")
    monkeypatch.setenv("DEMO_PASSWORD", "test-only-demo-password")
    monkeypatch.setenv("SOURCE_MANAGEMENT_ENABLED", "false")
    monkeypatch.delenv("RAG_INDEX_BOOTSTRAP_SEED_PATH", raising=False)


def _button(app, label):
    return next(button for button in app.button if button.label == label)


def test_login_failure_success_rerun_logout_and_session_isolation(monkeypatch):
    calls = []
    monkeypatch.setenv("RAG_INDEX_BOOTSTRAP_SEED_PATH", "unused-in-offline-test")
    monkeypatch.setattr(rag_service, "bootstrap_rag_index_from_seed", lambda **kwargs: calls.append(kwargs))
    app = AppTest.from_file(ROOT / "app.py").run()
    assert not app.exception
    assert not app.selectbox
    assert calls == []
    app.text_input(key=demo_access.PASSWORD_KEY).set_value("wrong")
    _button(app, "Sign in").click().run()
    assert any(error.value == "Incorrect password." for error in app.error)
    assert not app.selectbox
    assert calls == []
    assert app.session_state[demo_access.PASSWORD_KEY] == ""
    app.text_input(key=demo_access.PASSWORD_KEY).set_value("test-only-demo-password")
    _button(app, "Sign in").click().run()
    assert not app.exception
    assert len(calls) == 1
    assert app.button(key="demo_sign_out")
    assert "test-only-demo-password" not in repr(app.session_state)
    app.run()
    assert not app.exception
    other = AppTest.from_file(ROOT / "app.py").run()
    assert other.text_input(key=demo_access.PASSWORD_KEY)
    assert not other.selectbox
    app.session_state["private_draft_marker"] = "discard-on-logout"
    app.button(key="demo_sign_out").click().run()
    assert not app.exception
    with pytest.raises(KeyError):
        app.session_state["private_draft_marker"]
    with pytest.raises(KeyError):
        app.session_state[demo_access.AUTH_KEY]
    assert not app.selectbox


def test_missing_password_fails_closed_before_bootstrap(monkeypatch):
    monkeypatch.delenv("DEMO_PASSWORD", raising=False)
    monkeypatch.setenv("RAG_INDEX_BOOTSTRAP_SEED_PATH", "unused")
    monkeypatch.setattr(rag_service, "bootstrap_rag_index_from_seed", lambda **kwargs: pytest.fail("unauthenticated bootstrap"))
    app = AppTest.from_file(ROOT / "app.py").run()
    assert not app.exception
    assert any("configure the demo password" in e.value for e in app.error)
    assert not app.selectbox
    assert not app.text_input


def test_password_rotation_invalidates_existing_session(monkeypatch):
    app = AppTest.from_file(ROOT / "app.py").run()
    app.text_input(key=demo_access.PASSWORD_KEY).set_value("test-only-demo-password")
    _button(app, "Sign in").click().run()
    app.session_state["private_draft_marker"] = "old-session"
    monkeypatch.setenv("DEMO_PASSWORD", "rotated-test-password")
    app.run()
    assert not app.exception
    assert not app.selectbox
    with pytest.raises(KeyError):
        app.session_state["private_draft_marker"]
    assert app.text_input(key=demo_access.PASSWORD_KEY)


def test_failed_login_cooldown_and_expiry(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(demo_access, "monotonic", lambda: clock[0])
    app = AppTest.from_file(ROOT / "app.py").run()
    for _ in range(demo_access.MAX_LOGIN_ATTEMPTS):
        app.text_input(key=demo_access.PASSWORD_KEY).set_value("wrong")
        _button(app, "Sign in").click().run()
    assert _button(app, "Sign in").disabled
    assert app.warning
    clock[0] += demo_access.COOLDOWN_SECONDS + 1
    app.run()
    assert not _button(app, "Sign in").disabled
    app.text_input(key=demo_access.PASSWORD_KEY).set_value("test-only-demo-password")
    _button(app, "Sign in").click().run()
    assert not app.exception
    assert app.button(key="demo_sign_out")


def test_disabled_gate_leaves_local_workflow_unchanged(monkeypatch):
    monkeypatch.setenv("DEMO_ACCESS_ENABLED", "false")
    monkeypatch.delenv("DEMO_PASSWORD", raising=False)
    app = AppTest.from_file(ROOT / "app.py").run()
    assert not app.exception
    assert not any(input.label == "Demo password" for input in app.text_input)
    assert any(box.label == "Channel" for box in app.selectbox)
