from contextlib import contextmanager
from dataclasses import replace
import time
import unittest
from unittest.mock import Mock, patch

import requests

from job_hunter.application_browser import (
    BrowserConfig, BrowserError, BrowserbaseClient, ApplicationBrowser,
    UploadRequest, attach_document, load_browser_config, validate_destination,
)


SESSION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
LIVE_URL = "https://www.browserbase.com/devtools-fullscreen?sessionId=synthetic"
CONNECT_URL = "wss://connect.browserbase.com?apiKey=synthetic"


def response(payload, status=200):
    value = Mock(status_code=status)
    value.json.return_value = payload
    return value


class BrowserProviderTest(unittest.TestCase):
    def test_disabled_by_default_and_strict_enabled_configuration(self):
        self.assertFalse(load_browser_config({}, {}).enabled)
        self.assertFalse(load_browser_config({"BROWSERBASE_ENABLED": False}, {"BROWSERBASE_ENABLED": "true"}).enabled)
        for secrets in ({"BROWSERBASE_ENABLED": "yes"}, {"BROWSERBASE_ENABLED": True},
                        {"BROWSERBASE_ENABLED": True, "BROWSERBASE_API_KEY": "secret"}):
            with self.subTest(secrets=secrets), self.assertRaises(BrowserError):
                load_browser_config(secrets, {})
        config = load_browser_config({"BROWSERBASE_ENABLED": True,
                                      "BROWSERBASE_API_KEY": "private-key",
                                      "BROWSERBASE_PROJECT_ID": SESSION_ID}, {})
        self.assertEqual(config.timeout_seconds, 900)
        self.assertNotIn("private-key", repr(config))

    def test_requests_disable_recording_automation_and_redirects(self):
        request = Mock(return_value=response({"id": SESSION_ID, "connectUrl": CONNECT_URL}))
        client = BrowserbaseClient(BrowserConfig(True, "private-key", SESSION_ID), request=request)
        created = client.create(600)
        self.assertEqual(created.session_id, SESSION_ID)
        self.assertNotIn(CONNECT_URL, repr(created))
        sent = request.call_args.kwargs
        self.assertEqual(sent["json"]["timeout"], 600)
        self.assertFalse(sent["json"]["keepAlive"])
        self.assertFalse(sent["json"]["proxies"])
        for setting in ("recordSession", "logSession", "solveCaptchas", "advancedStealth"):
            self.assertIs(sent["json"]["browserSettings"][setting], False)
        self.assertFalse(sent["allow_redirects"])
        self.assertEqual(sent["timeout"], (5, 15))
        self.assertNotIn("context", sent["json"]["browserSettings"])

    def test_remote_errors_are_safe_and_never_retry_creation(self):
        for outcome in (response({"error": "private-key"}, 401),
                        response({}, 429), response({}, 503), response({}, 302),
                        requests.Timeout("private-key")):
            request = Mock(side_effect=[outcome])
            client = BrowserbaseClient(BrowserConfig(True, "private-key", SESSION_ID), request=request)
            with self.assertRaises(BrowserError) as caught:
                client.create(900)
            self.assertNotIn("private-key", str(caught.exception))
            self.assertEqual(request.call_count, 1)

    def test_invalid_control_url_releases_created_session(self):
        request = Mock(side_effect=[response({"id": SESSION_ID, "connectUrl": "wss://evil.test"}), response({})])
        client = BrowserbaseClient(BrowserConfig(True, "key", SESSION_ID), request=request)
        with self.assertRaises(BrowserError):
            client.create(900)
        self.assertEqual(request.call_args.args[1], f"https://api.browserbase.com/v1/sessions/{SESSION_ID}")
        self.assertEqual(request.call_args.kwargs["json"], {"status": "REQUEST_RELEASE"})

    def test_live_url_validation(self):
        for url in ("https://evil.test", "http://www.browserbase.com/a", "https://browserbase.com.evil.test/a",
                    "https://user@www.browserbase.com/a", "https://www.browserbase.com:8443/a",
                    "HTTPS://www.browserbase.com/<script>alert(1)</script>"):
            client = BrowserbaseClient(BrowserConfig(), request=Mock(return_value=response({"debuggerUrl": url})))
            with self.subTest(url=url), self.assertRaises(BrowserError):
                client.live_url(SESSION_ID)

    def test_initial_url_must_be_public_https_without_credentials(self):
        with patch("job_hunter.application_browser._hostname_resolves_public", return_value=True):
            self.assertEqual(validate_destination("https://careers.example.com/job/123"), "https://careers.example.com/job/123")
            for url in ("file:///etc/passwd", "http://example.com", "https://user:pass@example.com",
                        "https://localhost/x", "https://127.0.0.1", "https://example.com:81/x", "https://[::1]", "https://example.com\\@evil.test"):
                with self.subTest(url=url), self.assertRaises(BrowserError):
                    validate_destination(url)
        with patch("job_hunter.application_browser._hostname_resolves_public", return_value=False):
            with self.assertRaises(BrowserError):
                validate_destination("https://internal.example.com")


class UploadTest(unittest.TestCase):
    def chooser(self):
        chooser = Mock()
        chooser.element.owner_frame.return_value.url = "https://careers.example.com/apply"
        return chooser

    def test_attachment_goes_to_requested_input_only_and_stays_in_memory(self):
        chooser = self.chooser()
        request = UploadRequest("one", "https://careers.example.com/apply")
        attach_document(chooser, request, "one", "cv.pdf", b"%PDF-synthetic")
        sent = chooser.set_files.call_args.args[0]
        self.assertEqual(sent["buffer"], b"%PDF-synthetic")
        self.assertEqual(sent["mimeType"], "application/pdf")

    def test_expired_request_rejects_attachment(self):
        chooser = self.chooser()
        request = replace(UploadRequest("one", "https://careers.example.com/apply"), expires_at=time.monotonic() - 1)
        with self.assertRaises(BrowserError):
            attach_document(chooser, request, "one", "cv.pdf", b"cv")
        chooser.set_files.assert_not_called()

    def test_rejects_changed_target_stale_request_and_invalid_file(self):
        request = UploadRequest("one", "https://careers.example.com/apply")
        for request_id, filename, data, url in (
            ("old", "cv.pdf", b"cv", request.frame_url),
            ("one", "cv.pdf", b"cv", "https://other.example.com/apply"),
            ("one", "cv.html", b"cv", request.frame_url),
            ("one", "cv.pdf", b"x" * (5 * 1024 * 1024 + 1), request.frame_url),
            ("one", "cv.pdf", b"", request.frame_url),
        ):
            chooser = self.chooser()
            chooser.element.owner_frame.return_value.url = url
            with self.subTest(filename=filename, request_id=request_id), self.assertRaises(BrowserError):
                attach_document(chooser, request, request_id, filename, data)
            chooser.set_files.assert_not_called()


class BrowserLifecycleTest(unittest.TestCase):
    def test_navigation_dispatched_during_upload_validation_cancels_attachment(self):
        controller = ApplicationBrowser("owner", 1, "https://example.com/job", BrowserConfig(), time.time() + 3600)
        chooser = Mock()
        chooser.element.owner_frame.return_value.url = "https://example.com/job"
        request = UploadRequest("one", "https://example.com/job")
        controller._chooser, controller._request = chooser, request
        controller._publish(state="ready", upload_request=request)
        controller.upload("owner", "one", "cv.pdf", b"synthetic")
        def validate_element(*args):
            controller._invalidate_upload()
            return True
        chooser.element.evaluate.side_effect = validate_element
        controller._attach_pending()
        chooser.set_files.assert_not_called()
        self.assertIsNone(controller.snapshot().upload_request)
        self.assertNotIn("Document attached", controller.snapshot().message)

    def test_tab_close_keeps_other_application_tab_alive(self):
        from playwright.sync_api import Error
        client = Mock()
        client.create.return_value.session_id = SESSION_ID
        client.create.return_value.connect_url = CONNECT_URL
        client.live_url.return_value = LIVE_URL
        browser, context, first, second = Mock(), Mock(), Mock(), Mock()
        browser.contexts = [context]
        context.pages = [first, second]
        @contextmanager
        def connect(url):
            yield browser
        controller = ApplicationBrowser("owner", 1, "https://example.com/job", BrowserConfig(True, "key", SESSION_ID),
                                        time.time() + 3600, client=client, connect=connect)
        def close_first(*args):
            context.pages = [second]
            first.is_closed.return_value = True
            raise Error("Target page has been closed")
        first.wait_for_timeout.side_effect = close_first
        second.wait_for_timeout.side_effect = lambda *_: controller.close()
        with patch("job_hunter.application_browser.validate_destination", side_effect=lambda value: value):
            controller.start()
            controller.join(2)
        self.assertFalse(controller.is_alive())
        second.wait_for_timeout.assert_called_once()
        self.assertEqual(controller.snapshot().state, "closed")
        client.release.assert_called_once_with(SESSION_ID)

    def test_expiry_and_missing_heartbeat_release_session(self):
        for reason in ("heartbeat", "identity", "timeout"):
            with self.subTest(reason=reason):
                client = Mock()
                client.create.return_value.session_id = SESSION_ID
                client.create.return_value.connect_url = CONNECT_URL
                client.live_url.return_value = LIVE_URL
                browser, context, page = Mock(), Mock(), Mock()
                browser.contexts = [context]
                context.pages = [page]

                @contextmanager
                def connect(url):
                    yield browser

                controller = ApplicationBrowser("owner", 1, "https://example.com/job",
                                                BrowserConfig(True, "key", SESSION_ID, 0 if reason == "timeout" else 900),
                                                time.time() + 3600, client=client, connect=connect)

                def loaded(*args, **kwargs):
                    if reason == "heartbeat":
                        controller._heartbeat = time.monotonic() - 61
                    elif reason == "identity":
                        controller.identity_expires_at = time.time() - 1

                page.goto.side_effect = loaded
                with patch("job_hunter.application_browser.validate_destination", side_effect=lambda value: value):
                    controller.start()
                    controller.join(2)
                self.assertFalse(controller.is_alive())
                client.release.assert_called_once_with(SESSION_ID)
                self.assertEqual(controller.snapshot().state, "closed")
                self.assertEqual(controller.snapshot().live_url, "")
                self.assertIn("expired", controller.snapshot().message)
                page.wait_for_timeout.assert_not_called()

    def test_changed_owner_immediately_hides_view_and_stops_worker(self):
        controller = ApplicationBrowser("owner", 1, "https://example.com/job", BrowserConfig(), time.time() + 3600)
        controller._publish(state="ready", live_url=LIVE_URL)
        with self.assertRaises(BrowserError):
            controller.touch("different-owner")
        self.assertEqual(controller.snapshot().live_url, "")
        self.assertTrue(controller._stop.is_set())

    def test_close_is_idempotent_after_worker_has_finished(self):
        controller = ApplicationBrowser("owner", 1, "https://example.com/job", BrowserConfig(), time.time() + 3600)
        controller.start()
        controller.join(2)
        terminal = controller.snapshot()
        controller.close()
        self.assertEqual(controller.snapshot(), terminal)

    def test_disabled_configuration_never_creates_session(self):
        client = Mock()
        controller = ApplicationBrowser("owner", 1, "https://example.com/job", BrowserConfig(),
                                        time.time() + 3600, client=client)
        with patch("job_hunter.application_browser.validate_destination", side_effect=lambda value: value):
            controller.start()
            controller.join(2)
        client.create.assert_not_called()

    def test_close_during_creation_releases_without_exposing_view(self):
        from threading import Event
        started, proceed = Event(), Event()
        client = Mock()
        def create(timeout):
            started.set()
            proceed.wait(2)
            return type("Created", (), {"session_id": SESSION_ID, "connect_url": CONNECT_URL})()
        client.create.side_effect = create
        controller = ApplicationBrowser("owner", 1, "https://example.com/job", BrowserConfig(True, "key", SESSION_ID),
                                        time.time() + 3600, client=client)
        with patch("job_hunter.application_browser.validate_destination", side_effect=lambda value: value):
            controller.start()
            self.assertTrue(started.wait(2))
            controller.close()
            proceed.set()
            controller.join(3)
        self.assertFalse(controller.is_alive())
        self.assertEqual(controller.snapshot().live_url, "")
        client.release.assert_called_once_with(SESSION_ID)
        client.live_url.assert_not_called()

    def test_identity_expiry_prevents_provider_call(self):
        client = Mock()
        controller = ApplicationBrowser("owner", 1, "https://example.com/job", BrowserConfig(True, "key", SESSION_ID),
                                        time.time() - 1, client=client)
        controller.start()
        controller.join(2)
        client.create.assert_not_called()
        self.assertEqual(controller.snapshot().state, "error")

    def test_owner_guard_rejects_upload(self):
        controller = ApplicationBrowser("owner", 1, "https://example.com/job", BrowserConfig(), time.time() + 3600)
        with self.assertRaises(BrowserError):
            controller.upload("other", "req", "cv.pdf", b"private")
        self.assertTrue(controller.commands.empty())


if __name__ == "__main__":
    unittest.main()
