"""Optional private Google account gate and account controls for Streamlit."""

from __future__ import annotations

from typing import Mapping, MutableMapping

import streamlit as st

from job_hunter.account_config import AccountAccessError, AccountConfigError, identity_from_claims, load_account_config
from job_hunter.account_session import AccountSession
from job_hunter.account_snapshot import RestoredAccount, SnapshotError
from job_hunter.account_store import AccountStorageError, SupabaseAccountStore
from job_hunter.session_workspace import WORKSPACE_KEY


ACCOUNT_KEY = "account_session"
CLAIM_KEYS = ("iss", "sub", "email", "email_verified", "aud", "exp")


def prepare_account(state: MutableMapping[str, object], secrets: Mapping[str, object]) -> bool:
    try:
        config = load_account_config(secrets)
    except AccountConfigError as exc:
        clear_session(state)
        st.error(str(exc))
        st.stop()
    if not config.enabled:
        if ACCOUNT_KEY in state:
            clear_session(state)
        return False
    if not st.user.is_logged_in:
        clear_session(state)
        st.title("Job Hunter")
        st.subheader("Sign in to your private workspace")
        st.caption("Your CV, search settings, jobs and application records are saved privately to your account.")
        st.button("Sign in with Google", icon=":material/login:", on_click=login)
        st.stop()
    try:
        identity = identity_from_claims(_claims(), config)
    except AccountAccessError as exc:
        clear_session(state)
        st.error(str(exc))
        st.button("Sign out", icon=":material/logout:", on_click=logout)
        st.stop()

    session = state.get(ACCOUNT_KEY)
    if (not isinstance(session, AccountSession) or session.identity.owner_id != identity.owner_id
            or session.config != config):
        clear_session(state)
        session = AccountSession(identity, config, SupabaseAccountStore(config))
        state[ACCOUNT_KEY] = session
    session.identity = identity
    if not session.load_attempted:
        with st.spinner("Loading your saved workspace..."):
            restore_account(state, session)
    if not session.ready:
        st.error(session.error or "Saved workspace could not be loaded. No saved data has been replaced.")
        st.button("Retry loading saved data", on_click=_retry_load, args=(state, session), icon=":material/refresh:")
        st.button("Sign out", icon=":material/logout:", on_click=logout)
        st.stop()
    _render_account_controls(state, session)
    return True


def persist_account(state: MutableMapping[str, object], *, retry: bool = False) -> bool:
    session = state.get(ACCOUNT_KEY)
    if not isinstance(session, AccountSession):
        return False
    if not _authorize_session(state, session):
        return False
    workspace = state.get(WORKSPACE_KEY)
    if workspace is None:
        return False
    return session.flush(workspace, state.get("search_settings", {}),
                         str(state.get("search_mode", "Criteria-based search")), retry=retry)


def _authorize_session(state: MutableMapping[str, object], session: AccountSession) -> bool:
    # Widget callbacks execute before main's gate, so validate them separately.
    try:
        config = load_account_config(st.secrets)
        if config != session.config:
            raise AccountAccessError()
        identity = identity_from_claims(_claims(), config)
        if not st.user.is_logged_in or identity.owner_id != session.identity.owner_id:
            raise AccountAccessError()
    except (AccountAccessError, AccountConfigError):
        clear_session(state)
        st.rerun(scope="app")
        return False
    session.identity = identity
    return True


def render_save_status(state: MutableMapping[str, object]) -> None:
    session = state.get(ACCOUNT_KEY)
    if isinstance(session, AccountSession):
        if session.error:
            st.warning(f"Not saved to your account: {session.error} Unsaved changes can be lost on sign-out or restart.")
        else:
            st.caption(session.message)


def clear_session(state: MutableMapping[str, object]) -> None:
    controller = state.get("search_controller")
    if controller is not None:
        controller.cancel()
    state.clear()


def login() -> None:
    clear_session(st.session_state)
    st.login("google")


def logout() -> None:
    clear_session(st.session_state)
    st.logout()


def restore_account(state: MutableMapping[str, object], session: AccountSession) -> bool:
    controller = state.pop("search_controller", None)
    if controller is not None:
        controller.cancel()
    try:
        restored = session.restore()
    except (AccountStorageError, SnapshotError):
        return False
    _apply_restored(state, session, restored)
    return True


def _apply_restored(state: MutableMapping[str, object], session: AccountSession, restored: RestoredAccount) -> None:
    clear_session(state)
    state[ACCOUNT_KEY] = session
    state[WORKSPACE_KEY] = restored.workspace
    state["search_settings"] = restored.settings
    state["search_mode"] = restored.mode


def _claims() -> dict[str, object]:
    return {name: st.user.get(name) for name in CLAIM_KEYS}


def _retry_load(state: MutableMapping[str, object], session: AccountSession) -> None:
    if _authorize_session(state, session):
        restore_account(state, session)


def _retry_save(state: MutableMapping[str, object]) -> None:
    persist_account(state, retry=True)


def _reload(state: MutableMapping[str, object], session: AccountSession) -> None:
    if state.get("_account_reload_confirm") is True and _authorize_session(state, session):
        restore_account(state, session)


def _delete(state: MutableMapping[str, object], session: AccountSession) -> None:
    if state.get("_account_delete_confirm") is not True:
        return
    if not _authorize_session(state, session):
        return
    try:
        restored = session.clear()
    except AccountStorageError:
        return
    _apply_restored(state, session, restored)


def _render_account_controls(state: MutableMapping[str, object], session: AccountSession) -> None:
    with st.sidebar:
        st.subheader("Account")
        st.caption(f"Signed in as {session.identity.email}")
        render_save_status(state)
        if session.error and not session.conflicted:
            st.button("Retry saving", on_click=_retry_save, args=(state,), icon=":material/cloud_upload:")
        st.button("Sign out", on_click=logout, icon=":material/logout:")
        with st.expander("Saved data"):
            st.checkbox("Discard unsaved changes and reload saved data", key="_account_reload_confirm")
            st.button("Reload saved data", disabled=state.get("_account_reload_confirm") is not True,
                      on_click=_reload, args=(state, session), icon=":material/refresh:")
            st.caption("Deleting saved data removes your CV, settings, queue and application history. Provider backups may retain older data under their retention policy.")
            st.checkbox("Permanently delete my saved account data", key="_account_delete_confirm")
            st.button("Delete saved data", disabled=state.get("_account_delete_confirm") is not True or session.conflicted,
                      on_click=_delete, args=(state, session), icon=":material/delete:")
