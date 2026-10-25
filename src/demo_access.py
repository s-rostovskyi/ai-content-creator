"""Small session-scoped shared-password gate for the hosted course demo.

Card 6.1 / Musts M5, M8. This is not user management or a global spend cap.
"""
from __future__ import annotations

from hashlib import sha256
import hmac
import os
from time import monotonic

import streamlit as st

AUTH_KEY = "demo_authenticated_for"
PASSWORD_KEY = "demo_password_input"
ERROR_KEY = "demo_login_failed"
ATTEMPTS_KEY = "demo_login_attempts"
LOCKED_UNTIL_KEY = "demo_login_locked_until"
MAX_LOGIN_ATTEMPTS = 5
COOLDOWN_SECONDS = 60


def _password_tag(password: str) -> str:
    return hmac.new(password.encode("utf-8"), b"patagonia-demo-session", sha256).hexdigest()


def _submit_password() -> None:
    supplied = st.session_state.pop(PASSWORD_KEY, "")
    expected = os.getenv("DEMO_PASSWORD", "")
    now = monotonic()
    locked_until = st.session_state.get(LOCKED_UNTIL_KEY, 0.0)
    if locked_until > now:
        return
    if locked_until:
        st.session_state.pop(LOCKED_UNTIL_KEY, None)
        st.session_state[ATTEMPTS_KEY] = 0
    if expected.strip() and hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
        st.session_state[AUTH_KEY] = _password_tag(expected)
        for key in (ERROR_KEY, ATTEMPTS_KEY, LOCKED_UNTIL_KEY):
            st.session_state.pop(key, None)
        return
    st.session_state.pop(AUTH_KEY, None)
    st.session_state[ERROR_KEY] = True
    attempts = st.session_state.get(ATTEMPTS_KEY, 0) + 1
    st.session_state[ATTEMPTS_KEY] = attempts
    if attempts >= MAX_LOGIN_ATTEMPTS:
        st.session_state[LOCKED_UNTIL_KEY] = now + COOLDOWN_SECONDS


def _sign_out() -> None:
    # Remove campaign/editor/download state as well as the authentication marker.
    st.session_state.clear()


def require_demo_access() -> None:
    if os.getenv("DEMO_ACCESS_ENABLED", "").strip().lower() != "true":
        return
    expected = os.getenv("DEMO_PASSWORD", "")
    if not expected.strip():
        st.error("Demo access is unavailable. The owner must configure the demo password.")
        st.stop()
    tag = st.session_state.get(AUTH_KEY)
    if isinstance(tag, str) and hmac.compare_digest(tag, _password_tag(expected)):
        st.button("Sign out", key="demo_sign_out", on_click=_sign_out)
        return
    if tag is not None:
        st.session_state.clear()
    st.markdown("## Patagonia Content Studio")
    st.caption("Private course demo. Enter the password shared by the owner.")
    locked = st.session_state.get(LOCKED_UNTIL_KEY, 0.0) > monotonic()
    with st.form("demo_login_form", clear_on_submit=True):
        st.text_input("Demo password", type="password", key=PASSWORD_KEY)
        st.form_submit_button("Sign in", on_click=_submit_password, disabled=locked)
    if locked:
        st.warning("Too many attempts. Wait one minute before trying again.")
    elif st.session_state.get(ERROR_KEY):
        st.error("Incorrect password.")
    st.stop()
