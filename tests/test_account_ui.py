import unittest
from unittest.mock import MagicMock, patch

from job_hunter import account_ui
from job_hunter.account_config import identity_from_claims, load_account_config
from job_hunter.account_session import AccountSession
from job_hunter.account_store import AccountStorageError, StoredAccount
from job_hunter.session_workspace import SessionWorkspace, WORKSPACE_KEY
from test_account_config import account_secrets, google_claims


class StopRendering(Exception):
    pass


class AccountUITest(unittest.TestCase):
    def test_disabled_accounts_preserve_existing_guest_cv(self):
        workspace = SessionWorkspace()
        workspace.save_cv("synthetic.docx", b"synthetic", "synthetic experience")
        state = {WORKSPACE_KEY: workspace}
        with patch.object(account_ui, "st") as st:
            self.assertFalse(account_ui.prepare_account(state, {}))
            st.login.assert_not_called()
        self.assertIs(state[WORKSPACE_KEY], workspace)

    def test_signed_out_private_app_cannot_reach_storage(self):
        with patch.object(account_ui, "st") as st, patch.object(account_ui, "SupabaseAccountStore") as store:
            st.user.is_logged_in = False
            st.stop.side_effect = StopRendering
            with self.assertRaises(StopRendering):
                account_ui.prepare_account({}, account_secrets())
            store.assert_not_called()
            self.assertTrue(any(call.args[0] == "Sign in with Google" for call in st.button.call_args_list))

    def test_denied_google_user_clears_private_session_before_stopping(self):
        controller = MagicMock()
        state = {WORKSPACE_KEY: SessionWorkspace(), "search_controller": controller}
        with patch.object(account_ui, "st") as st, patch.object(account_ui, "SupabaseAccountStore") as store:
            st.user.is_logged_in = True
            st.user.get.side_effect = google_claims(email="denied@example.test").get
            st.stop.side_effect = StopRendering
            with self.assertRaises(StopRendering):
                account_ui.prepare_account(state, account_secrets())
            store.assert_not_called()
        self.assertNotIn(WORKSPACE_KEY, state)
        controller.cancel.assert_called_once()

    def test_clear_session_cancels_worker_and_removes_all_private_state(self):
        controller = MagicMock()
        state = {WORKSPACE_KEY: SessionWorkspace(), "search_controller": controller,
                 "search_settings": {"hard_skip_keywords": ["private"]}, "cv_upload_0": b"private",
                 "application_status_1": True}
        account_ui.clear_session(state)
        self.assertEqual(state, {})
        controller.cancel.assert_called_once()

    def test_logout_clears_before_native_logout(self):
        state = {WORKSPACE_KEY: SessionWorkspace()}
        with patch.object(account_ui, "st") as st:
            st.session_state = state
            st.logout.side_effect = lambda: self.assertEqual(state, {})
            account_ui.logout()
            st.logout.assert_called_once()

    def test_confirmed_reload_cancels_old_controller_and_restores_atomically(self):
        config = load_account_config(account_secrets())
        identity = identity_from_claims(google_claims(), config)
        store = MagicMock()
        store.load.return_value = StoredAccount(4, None)
        session = AccountSession(identity, config, store)
        controller = MagicMock()
        state = {account_ui.ACCOUNT_KEY: session, "search_controller": controller, "search_mode": "CV-based search", "search_settings": {"private": "old"}}
        self.assertTrue(account_ui.restore_account(state, session))
        self.assertIs(state[account_ui.ACCOUNT_KEY], session)
        self.assertEqual(state["search_mode"], "Criteria-based search")
        self.assertEqual(state["search_settings"]["target_roles"], [])
        self.assertEqual(session.revision, 4)
        controller.cancel.assert_called_once()

    def test_destructive_callbacks_require_confirmation_and_current_identity(self):
        secrets = account_secrets()
        config = load_account_config(secrets)
        session = MagicMock(spec=AccountSession)
        session.config = config
        session.identity = identity_from_claims(google_claims(), config)
        for callback, key, operation in (
            (account_ui._delete, "_account_delete_confirm", session.clear),
            (account_ui._reload, "_account_reload_confirm", session.restore),
        ):
            operation.reset_mock()
            state = {account_ui.ACCOUNT_KEY: session, WORKSPACE_KEY: SessionWorkspace()}
            callback(state, session)
            operation.assert_not_called()
            state[key] = True
            with patch.object(account_ui, "st") as st:
                st.secrets = secrets
                st.user.is_logged_in = True
                st.user.get.side_effect = google_claims(subject="different-owner").get
                st.rerun.side_effect = StopRendering
                with self.assertRaises(StopRendering):
                    callback(state, session)
            operation.assert_not_called()
            self.assertEqual(state, {})

    def test_failed_delete_keeps_workspace(self):
        secrets = account_secrets()
        config = load_account_config(secrets)
        session = AccountSession(identity_from_claims(google_claims(), config), config, MagicMock())
        session.ready = True
        session.revision = 4
        session.store.clear.side_effect = AccountStorageError("Synthetic outage")
        workspace = SessionWorkspace()
        state = {account_ui.ACCOUNT_KEY: session, WORKSPACE_KEY: workspace, "_account_delete_confirm": True}
        with patch.object(account_ui, "st") as st:
            st.secrets = secrets
            st.user.is_logged_in = True
            st.user.get.side_effect = google_claims().get
            account_ui._delete(state, session)
        self.assertIs(state[WORKSPACE_KEY], workspace)
        self.assertIn("Synthetic outage", session.error)

    def test_expired_identity_cancels_search_before_save(self):
        secrets = account_secrets()
        config = load_account_config(secrets)
        store = MagicMock()
        session = AccountSession(identity_from_claims(google_claims(), config), config, store)
        controller = MagicMock()
        state = {account_ui.ACCOUNT_KEY: session, WORKSPACE_KEY: SessionWorkspace(), "search_controller": controller}
        with patch.object(account_ui, "st") as st:
            st.secrets = secrets
            st.user.is_logged_in = True
            st.user.get.side_effect = dict(google_claims(), exp=1).get
            st.rerun.side_effect = StopRendering
            with self.assertRaises(StopRendering):
                account_ui.persist_account(state)
        self.assertEqual(state, {})
        store.save.assert_not_called()
        controller.cancel.assert_called_once()

    def test_access_revocation_blocks_callbacks_and_fragment_saves(self):
        for operation in ("delete", "save"):
            secrets = account_secrets()
            config = load_account_config(secrets)
            store = MagicMock()
            session = AccountSession(identity_from_claims(google_claims(), config), config, store)
            session.ready = True
            session.revision = 1
            state = {account_ui.ACCOUNT_KEY: session, WORKSPACE_KEY: SessionWorkspace(), "_account_delete_confirm": True}
            secrets["accounts"]["allowed_emails"] = ["other@example.test"]
            with patch.object(account_ui, "st") as st:
                st.secrets = secrets
                st.user.is_logged_in = True
                st.user.get.side_effect = google_claims().get
                st.rerun.side_effect = StopRendering
                with self.assertRaises(StopRendering):
                    if operation == "delete":
                        account_ui._delete(state, session)
                    else:
                        account_ui.persist_account(state)
            store.clear.assert_not_called()
            store.save.assert_not_called()
            self.assertEqual(state, {})

    def test_failed_confirmed_reload_cancels_controller_but_keeps_local_data(self):
        secrets = account_secrets()
        config = load_account_config(secrets)
        store = MagicMock()
        store.load.side_effect = AccountStorageError("Synthetic outage")
        session = AccountSession(identity_from_claims(google_claims(), config), config, store)
        workspace, controller = SessionWorkspace(), MagicMock()
        state = {account_ui.ACCOUNT_KEY: session, WORKSPACE_KEY: workspace,
                 "search_controller": controller, "_account_reload_confirm": True}
        with patch.object(account_ui, "st") as st:
            st.secrets = secrets
            st.user.is_logged_in = True
            st.user.get.side_effect = google_claims().get
            account_ui._reload(state, session)
        self.assertIs(state[WORKSPACE_KEY], workspace)
        controller.cancel.assert_called_once()
        self.assertFalse(session.ready)


if __name__ == "__main__":
    unittest.main()
