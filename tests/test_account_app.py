from pathlib import Path
from contextlib import contextmanager
from datetime import date
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from job_hunter import account_ui
from job_hunter.session_workspace import WORKSPACE_KEY
from test_account_config import account_secrets, google_claims
from test_account_snapshot import private_workspace
from test_account_store import response


APP_PATH = str(Path(__file__).resolve().parents[1] / "src" / "app.py")


class NativeUser:
    def __init__(self, claims=None):
        self.is_logged_in = claims is not None
        self.claims = claims or {}

    def get(self, key, default=None):
        return self.claims.get(key, default)


class MemoryRPC:
    def __init__(self):
        self.rows = {}
        self.writes = 0

    def __call__(self, url, *, json, **kwargs):
        owner = json["p_owner_id"]
        revision, payload = self.rows.get(owner, (0, None))
        if url.endswith("job_hunter_load"):
            return response({"revision": revision, "payload": payload})
        if json["p_expected_revision"] != revision:
            return response({}, 409)
        self.writes += 1
        self.rows[owner] = revision + 1, json["p_payload"]
        return response({"revision": revision + 1})


def private_app(secrets):
    test = AppTest.from_file(APP_PATH)
    test.secrets.update(secrets)
    return test


@contextmanager
def signed_in(rpc, claims=None):
    from job_hunter.account_store import SupabaseAccountStore
    with patch.object(account_ui.st, "user", NativeUser(claims or google_claims())), patch.object(
        account_ui, "SupabaseAccountStore", side_effect=lambda config: SupabaseAccountStore(config, post=rpc)
    ):
        yield


class AccountAppTest(unittest.TestCase):
    def test_remembered_login_restores_and_saves_after_id_token_expiry(self):
        secrets, rpc = account_secrets(), MemoryRPC()
        with signed_in(rpc):
            first = private_app(secrets).run(timeout=10)
            first.session_state[WORKSPACE_KEY] = private_workspace()
            first.run(timeout=10)
        with signed_in(rpc, dict(google_claims(), exp=1)):
            remembered = private_app(secrets).run(timeout=10)
            self.assertEqual(len(remembered.exception), 0)
            self.assertFalse(remembered.error)
            self.assertIsNotNone(remembered.session_state[WORKSPACE_KEY].cv)
            self.assertEqual(remembered.session_state[WORKSPACE_KEY].list_jobs()[0].application_status, "applied")
            next(widget for widget in remembered.multiselect if widget.label == "Hard skip keywords").set_value(["remember this"]).run(timeout=10)
            self.assertFalse(remembered.warning)
            restored = private_app(secrets).run(timeout=10)
            self.assertEqual(restored.session_state["search_settings"]["hard_skip_keywords"], ["remember this"])
        saved_rows = dict(rpc.rows)
        user = NativeUser(google_claims())
        user.is_logged_in = False
        with patch.object(account_ui.st, "user", user):
            remembered.run(timeout=10)
            self.assertIn("Sign in with Google", [button.label for button in remembered.button])
            self.assertNotIn(WORKSPACE_KEY, remembered.session_state)
        self.assertEqual(rpc.rows, saved_rows)

    def test_conflict_is_shown_once_in_sidebar_without_overwriting_other_tab(self):
        secrets, rpc = account_secrets(), MemoryRPC()
        with signed_in(rpc):
            first = private_app(secrets).run(timeout=10)
            second = private_app(secrets).run(timeout=10)
            next(widget for widget in first.multiselect if widget.label == "Hard skip keywords").set_value(["first tab"]).run(timeout=10)
            saved_rows = dict(rpc.rows)
            next(widget for widget in second.multiselect if widget.label == "Hard skip keywords").set_value(["second tab"]).run(timeout=10)
            self.assertEqual(len(second.exception), 0)
            self.assertEqual(len(second.warning), 1)
            self.assertEqual(len(second.sidebar.warning), 1)
            self.assertEqual(rpc.rows, saved_rows)
            self.assertEqual(second.session_state["search_settings"]["hard_skip_keywords"], ["second tab"])
            reload_button = next(button for button in second.button if button.label == "Reload saved data")
            self.assertTrue(reload_button.disabled)
            next(widget for widget in second.checkbox if widget.label == "Discard unsaved changes and reload saved data").check().run(timeout=10)
            next(button for button in second.button if button.label == "Reload saved data").click().run(timeout=10)
            self.assertFalse(second.warning)
            self.assertEqual(second.session_state["search_settings"]["hard_skip_keywords"], ["first tab"])

    def test_new_save_error_is_visible_in_sidebar_with_working_retry(self):
        secrets, rpc = account_secrets(), MemoryRPC()
        unavailable = False

        def transport(url, **kwargs):
            if unavailable and url.endswith("job_hunter_save"):
                return response({}, 503)
            return rpc(url, **kwargs)

        with signed_in(transport):
            test = private_app(secrets).run(timeout=10)
            unavailable = True
            next(widget for widget in test.multiselect if widget.label == "Hard skip keywords").set_value(["keep this"]).run(timeout=10)
            self.assertEqual(len(test.exception), 0)
            self.assertEqual(len(test.warning), 1)
            self.assertEqual(len(test.sidebar.warning), 1)
            unavailable = False
            next(button for button in test.button if button.label == "Retry saving").click().run(timeout=10)
            self.assertFalse(test.warning)
            restored = private_app(secrets).run(timeout=10)
            self.assertEqual(restored.session_state["search_settings"]["hard_skip_keywords"], ["keep this"])

    def test_accepted_background_results_save_before_terminal_refresh(self):
        import app
        from unittest.mock import MagicMock
        from job_hunter.account_config import identity_from_claims, load_account_config
        from job_hunter.account_session import AccountSession
        from job_hunter.account_store import SupabaseAccountStore
        from job_hunter.matching import MatchResult
        from job_hunter.queue_types import JobInput
        from job_hunter.search_runner import CompletedMatch, RunSnapshot
        secrets, rpc = account_secrets(), MemoryRPC()
        config = load_account_config(secrets)
        session = AccountSession(identity_from_claims(google_claims(), config), config, SupabaseAccountStore(config, post=rpc))
        restored = session.restore()
        workspace = restored.workspace
        workspace.activate_run("finished")
        controller = MagicMock()
        match = CompletedMatch("finished", JobInput("Analyst", "Synthetic Company", "Kuala Lumpur", "Power BI", "https://www.linkedin.com/jobs/view/999"),
                               MatchResult(95, "shortlist", (), (), "Synthetic", "", False))
        controller.drain.return_value = ((), (match,))
        controller.snapshot.return_value = RunSnapshot(run_id="finished", state="completed", completed=1)
        state = {account_ui.ACCOUNT_KEY: session, WORKSPACE_KEY: workspace,
                 "search_settings": restored.settings, "search_mode": restored.mode}
        with signed_in(rpc), patch.object(app, "st") as st, patch.object(app, "_get_controller", return_value=controller), patch.object(account_ui.st, "secrets", secrets):
            st.session_state = state
            st.columns.return_value = (MagicMock(), MagicMock())
            st.button.return_value = False
            st.rerun.side_effect = lambda **kwargs: self.assertEqual(rpc.writes, 1)
            app._render_run_fragment.__wrapped__(workspace)
        saved = AccountSession(session.identity, config, SupabaseAccountStore(config, post=rpc)).restore()
        self.assertEqual(saved.workspace.list_jobs()[0].title, "Analyst")

    def test_private_signed_out_app_has_login_not_search_controls(self):
        with patch.object(account_ui.st, "user", NativeUser()):
            test = private_app(account_secrets()).run(timeout=10)
        self.assertEqual(len(test.exception), 0)
        self.assertIn("Sign in with Google", [button.label for button in test.button])
        self.assertNotIn("Run search and score jobs", [button.label for button in test.button])

    def test_private_cv_uploader_displays_account_limit(self):
        with signed_in(MemoryRPC()):
            test = private_app(account_secrets()).run(timeout=10)
            next(widget for widget in test.radio if widget.label == "Matching mode").set_value("CV-based search").run(timeout=10)
            test.segmented_control[0].set_value("Profile & CV").run(timeout=10)
            self.assertEqual(test.get("file_uploader")[0].proto.max_upload_size_mb, 5)

    def test_guest_cv_uploader_displays_same_limit(self):
        test = AppTest.from_file(APP_PATH).run(timeout=10)
        next(widget for widget in test.radio if widget.label == "Matching mode").set_value(
            "CV-based search"
        ).run(timeout=10)
        test.segmented_control[0].set_value("Profile & CV").run(timeout=10)
        self.assertEqual(test.get("file_uploader")[0].proto.max_upload_size_mb, 5)

    def test_enabled_incomplete_configuration_has_no_guest_bypass(self):
        test = AppTest.from_file(APP_PATH)
        test.secrets["accounts"] = {"enabled": True}
        test.run(timeout=10)
        self.assertEqual(len(test.exception), 0)
        self.assertTrue(test.error)
        self.assertNotIn("Run search and score jobs", [button.label for button in test.button])

    def test_signed_in_cv_criteria_and_applied_history_restore_after_restart(self):
        secrets = account_secrets()
        rpc = MemoryRPC()
        with patch.object(account_ui.st, "user", NativeUser(google_claims())), patch("job_hunter.account_store.requests.post", side_effect=rpc):
            # Inject the transport explicitly because the adapter's default is bound at import.
            from job_hunter.account_store import SupabaseAccountStore
            with patch.object(account_ui, "SupabaseAccountStore", side_effect=lambda config: SupabaseAccountStore(config, post=rpc)):
                first = private_app(secrets).run(timeout=10)
                self.assertEqual(len(first.exception), 0)
                first.session_state[WORKSPACE_KEY] = private_workspace()
                first.run(timeout=10)
                next(widget for widget in first.radio if widget.label == "Matching mode").set_value(
                    "CV-based search"
                ).run(timeout=10)
                self.assertEqual(
                    next(widget for widget in first.multiselect if widget.label == "Required description keywords").value,
                    ["Power BI"],
                )
                next(widget for widget in first.multiselect if widget.label == "Hard skip keywords").set_value(["custom exclusion"]).run(timeout=10)
                first.segmented_control[0].set_value("Job queue").run(timeout=10)
                first.segmented_control[0].set_value("Search jobs").run(timeout=10)
                self.assertEqual(next(widget for widget in first.multiselect if widget.label == "Hard skip keywords").value, ["custom exclusion"])
                self.assertEqual(len(first.exception), 0)
                second = private_app(secrets).run(timeout=10)
                self.assertEqual(len(second.exception), 0)
                workspace = second.session_state[WORKSPACE_KEY]
                self.assertIsNotNone(workspace.cv)
                self.assertEqual(workspace.list_jobs()[0].application_status, "applied")
                self.assertEqual(second.session_state["search_settings"]["hard_skip_keywords"], ["custom exclusion"])
                self.assertEqual(second.session_state["search_settings"]["primary_keywords"], ["Power BI"])
                self.assertRegex(second.session_state["search_settings"]["cv_profile_digest"], r"^[a-f0-9]{64}$")
                self.assertIn("Profile & CV", second.segmented_control[0].options)
                self.assertNotIn("Synthetic experience", str(rpc.rows))

    def test_real_queue_edits_and_cv_removal_persist_without_history_loss(self):
        secrets, rpc = account_secrets(), MemoryRPC()
        with signed_in(rpc):
            test = private_app(secrets).run(timeout=10)
            test.session_state[WORKSPACE_KEY] = private_workspace()
            test.run(timeout=10)
            test.segmented_control[0].set_value("Job queue").run(timeout=10)
            next(widget for widget in test.segmented_control if widget.label == "Applications").set_value("All").run(timeout=10)
            next(widget for widget in test.checkbox if widget.label == "I have applied to this job").uncheck().run(timeout=10)
            self.assertEqual(test.session_state[WORKSPACE_KEY].list_jobs()[0].application_status, "not_applied")
            next(widget for widget in test.checkbox if widget.label == "I have applied to this job").check().run(timeout=10)
            next(widget for widget in test.date_input if widget.label == "Posting date").set_value(date(2026, 1, 1))
            next(widget for widget in test.selectbox if widget.label == "Expiry").set_value("not_expired")
            next(widget for widget in test.button if widget.label == "Save posting details").click().run(timeout=10)
            next(widget for widget in test.radio if widget.label == "Matching mode").set_value("CV-based search").run(timeout=10)
            test.segmented_control[0].set_value("Profile & CV").run(timeout=10)
            next(widget for widget in test.button if widget.label == "Remove saved CV").click().run(timeout=10)
            self.assertEqual(len(test.exception), 0)
            self.assertIsNone(test.session_state[WORKSPACE_KEY].cv)
            restored = private_app(secrets).run(timeout=10)
            self.assertEqual(len(restored.exception), 0)
            workspace = restored.session_state[WORKSPACE_KEY]
            self.assertIsNone(workspace.cv)
            record = workspace.list_jobs()[0]
            self.assertEqual(record.application_status, "applied")
            self.assertTrue(record.application_recorded_at)
            self.assertIn("manually", record.application_evidence)
            self.assertEqual(record.posted_date, "2026-01-01")
            self.assertEqual(record.availability, "not_expired")

    def test_storage_load_failure_blocks_workspace_and_writes(self):
        secrets, rpc = account_secrets(), MemoryRPC()
        with signed_in(lambda *args, **kwargs: response({}, 503)):
            test = private_app(secrets).run(timeout=10)
            self.assertEqual(len(test.exception), 0)
            self.assertTrue(test.error)
            self.assertNotIn("Run search and score jobs", [button.label for button in test.button])
            self.assertNotIn(WORKSPACE_KEY, test.session_state)
        self.assertEqual(rpc.writes, 0)

    def test_two_allowed_accounts_have_isolated_saved_workspaces(self):
        secrets, rpc = account_secrets(), MemoryRPC()
        secrets["accounts"]["allowed_emails"].append("second@example.test")
        with signed_in(rpc):
            test = private_app(secrets).run(timeout=10)
            test.session_state[WORKSPACE_KEY] = private_workspace()
            test.run(timeout=10)
        with signed_in(rpc, google_claims(subject="second-owner", email="second@example.test")):
            test.run(timeout=10)
            self.assertEqual(len(test.exception), 0)
            self.assertIsNone(test.session_state[WORKSPACE_KEY].cv)
            self.assertEqual(test.session_state[WORKSPACE_KEY].list_jobs(), [])
        with signed_in(rpc):
            restored = private_app(secrets).run(timeout=10)
            self.assertEqual(restored.session_state[WORKSPACE_KEY].list_jobs()[0].application_status, "applied")


if __name__ == "__main__":
    unittest.main()
