"""Human-operated application panel, gated by the existing private account."""

from __future__ import annotations

import streamlit as st

from job_hunter import account_ui
from job_hunter.account_session import AccountSession
from job_hunter.application_browser import (
    ApplicationBrowser, BROWSER_KEY, BrowserError, load_browser_config,
)
from job_hunter.session_workspace import WORKSPACE_KEY


def _account():
    session = st.session_state.get(account_ui.ACCOUNT_KEY)
    if not isinstance(session, AccountSession) or not session.ready:
        return None
    if not account_ui._authorize_session(st.session_state, session):
        return None
    return session


def render_application_browser(workspace, job, destination: str) -> None:
    try:
        config = load_browser_config(st.secrets)
    except BrowserError as exc:
        _close_existing()
        st.warning(str(exc))
        return
    if not config.enabled:
        _close_existing()
        return
    account = _account()
    if account is None:
        _close_existing()
        st.info("Apply here requires a configured private account. The original application page is still available.")
        return
    controller = st.session_state.get(BROWSER_KEY)
    if controller is not None and controller.owner_id != account.identity.owner_id:
        controller.close()
        st.session_state.pop(BROWSER_KEY, None)
        controller = None
    active = controller is not None and controller.is_alive()
    if not active:
        st.caption("Browserbase processes this remote browser, including information you enter or attach. "
                   "Recording and session logs are disabled; provider retention policies still apply. "
                   "Sessions last up to 15 minutes. Platform sign-ins are not saved between sessions.")
        consent = st.checkbox("Use Browserbase for this application", key=f"_browser_consent_{job.id}")
        if st.button("Apply here", icon=":material/web:", type="primary",
                     disabled=not consent or not destination or job.availability == "expired"):
            controller = ApplicationBrowser(account.identity.owner_id, job.id, destination, config,
                                            account.identity.expires_at)
            st.session_state[BROWSER_KEY] = controller
            controller.start()
            st.rerun(scope="app")
    if controller is not None:
        _render_live_browser(job.id)


def _close_existing() -> None:
    controller = st.session_state.get(BROWSER_KEY)
    if controller is not None and controller.is_alive():
        controller.close()


@st.fragment(run_every="2s")
def _render_live_browser(selected_job_id: int) -> None:
    account = _account()
    if account is None:
        return
    controller = st.session_state.get(BROWSER_KEY)
    if controller is None:
        return
    try:
        config = load_browser_config(st.secrets)
        if config != controller.config:
            controller.close()
            st.warning("Browser configuration changed. Close this session before starting another.")
        controller.touch(account.identity.owner_id)
    except BrowserError as exc:
        controller.close()
        st.warning(str(exc))
        return
    workspace = st.session_state.get(WORKSPACE_KEY)
    current_job = next((job for job in workspace.list_jobs() if job.id == controller.job_id), None) if workspace else None
    if current_job is None or current_job.availability == "expired":
        controller.close()
    snapshot = controller.snapshot()
    if st.button("Close application browser", icon=":material/close:", disabled=not controller.is_alive()):
        controller.close()
        st.rerun(scope="app")
    if snapshot.state in {"closed", "error"}:
        st.warning(snapshot.message)
        # Refresh controls outside this fragment once when the worker settles.
        marker = id(controller)
        if st.session_state.get("_browser_finished") != marker:
            st.session_state["_browser_finished"] = marker
            st.rerun(scope="app")
        return
    if selected_job_id != controller.job_id:
        st.info(f"The application browser belongs to job #{controller.job_id}. Close it before opening a different job.")
        return
    if snapshot.state != "ready":
        st.info(snapshot.message)
        return
    st.caption(f"{snapshot.seconds_remaining // 60}:{snapshot.seconds_remaining % 60:02d} remaining | {snapshot.message}")
    request = snapshot.upload_request
    if request is not None:
        st.warning(f"Document requested by {request.hostname}. Attaching sends it to this site through Browserbase.")
        cv = workspace.cv if workspace else None
        if cv is not None and st.button("Attach saved CV", icon=":material/attach_file:", key=f"_attach_cv_{request.request_id}"):
            _send_document(controller, account, request, cv.filename, cv.content)
        document = st.file_uploader("Document for this application", type=["pdf", "doc", "docx"],
                                    max_upload_size=5, key=f"_application_document_{request.request_id}")
        if st.button("Attach selected document", icon=":material/upload_file:", disabled=document is None,
                     key=f"_attach_file_{request.request_id}"):
            _send_document(controller, account, request, document.name, document.getvalue())
    st.iframe(snapshot.live_url, height=780)


def _send_document(controller, account, request, filename, content) -> None:
    try:
        controller.upload(account.identity.owner_id, request.request_id, filename, content)
        st.toast("Attaching document...")
    except BrowserError as exc:
        st.warning(str(exc))
