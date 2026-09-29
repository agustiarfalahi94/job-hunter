from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

from job_hunter import account_ui
from job_hunter.application_browser import BROWSER_KEY, BrowserSnapshot
from job_hunter.session_workspace import WORKSPACE_KEY
from test_account_app import MemoryRPC, private_app, signed_in
from test_account_config import account_secrets, google_claims
from test_account_snapshot import private_workspace


APP_PATH = str(Path(__file__).resolve().parents[1] / "src/app.py")


def enabled_secrets():
    return {**account_secrets(), "BROWSERBASE_ENABLED": True,
            "BROWSERBASE_API_KEY": "synthetic-private-key",
            "BROWSERBASE_PROJECT_ID": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"}


def open_queue(test):
    test.session_state[WORKSPACE_KEY] = private_workspace()
    test.run(timeout=10)
    test.segmented_control[0].set_value("Job queue").run(timeout=10)
    next(widget for widget in test.segmented_control if widget.label == "Applications").set_value("All").run(timeout=10)
    return test


class ApplicationBrowserUITest(unittest.TestCase):
    def test_turning_feature_off_closes_existing_session(self):
        from job_hunter import application_ui
        controller = Mock()
        with patch.object(application_ui, "st") as st:
            st.secrets = {"BROWSERBASE_ENABLED": False}
            st.session_state = {BROWSER_KEY: controller}
            application_ui.render_application_browser(private_workspace(), Mock(), "https://example.com")
        controller.close.assert_called_once()

    def test_guest_cannot_start_browser_even_with_provider_configured(self):
        test = AppTest.from_file(APP_PATH)
        test.secrets.update({key: value for key, value in enabled_secrets().items() if key.startswith("BROWSERBASE")})
        open_queue(test.run(timeout=10))
        self.assertEqual(len(test.exception), 0)
        self.assertNotIn("Apply here", [button.label for button in test.button])
        self.assertTrue(any("private account" in element.value for element in test.info))

    def test_remembered_login_can_start_browser_with_consent_after_id_token_expiry(self):
        from job_hunter import application_ui
        controller = Mock()
        controller.config = None
        controller.snapshot.return_value = BrowserSnapshot("ready", "Ready", "https://www.browserbase.com/devtools?test=1")
        controller.is_alive.return_value = True
        def build(owner, job_id, destination, config):
            controller.owner_id, controller.job_id, controller.config = owner, job_id, config
            return controller
        with signed_in(MemoryRPC(), dict(google_claims(), exp=1)), patch.object(application_ui, "ApplicationBrowser", side_effect=build) as factory:
            test = open_queue(private_app(enabled_secrets()).run(timeout=10))
            start = next(button for button in test.button if button.label == "Apply here")
            self.assertTrue(start.disabled)
            next(box for box in test.checkbox if box.label == "Use Browserbase for this application").check().run(timeout=10)
            next(button for button in test.button if button.label == "Apply here").click().run(timeout=10)
            controller.owner_id = test.session_state[account_ui.ACCOUNT_KEY].identity.owner_id
            controller.job_id = 1
            controller.config = factory.call_args.args[3]
            test.run(timeout=10)
            self.assertEqual(len(test.exception), 0)
            self.assertEqual(factory.call_count, 1)
            controller.start.assert_called_once()
            self.assertIn("Close application browser", [button.label for button in test.button])
            self.assertTrue(test.get("iframe"))
            self.assertNotIn("synthetic-private-key", str(test.get("iframe")[0].proto))

    def test_clear_session_stops_remote_browser_before_discarding_owner(self):
        controller = Mock()
        state = {BROWSER_KEY: controller, WORKSPACE_KEY: private_workspace()}
        account_ui.clear_session(state)
        controller.close.assert_called_once()
        self.assertEqual(state, {})

    def test_disabled_browser_preserves_external_apply_and_existing_status(self):
        test = open_queue(AppTest.from_file(APP_PATH).run(timeout=10))
        self.assertEqual(len(test.exception), 0)
        self.assertTrue(test.get("link_button"))
        self.assertNotIn("Apply here", [button.label for button in test.button])
        self.assertEqual(test.session_state[WORKSPACE_KEY].list_jobs()[0].application_status, "applied")


if __name__ == "__main__":
    unittest.main()
