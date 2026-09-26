"""Opt-in real-browser test; uses an intercepted synthetic form, never a job site."""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from threading import Event, Thread
import time
import unittest
from unittest.mock import Mock, patch

from job_hunter.application_browser import ApplicationBrowser, BrowserConfig, BrowserError
from job_hunter.browserbase_provider import CreatedSession


CHROME = os.environ.get("JOB_HUNTER_TEST_CHROME", "")


@unittest.skipUnless(CHROME, "Set JOB_HUNTER_TEST_CHROME to run synthetic browser integration")
class RealBrowserUploadTest(unittest.TestCase):
    def test_redirect_cannot_reach_private_http_destination(self):
        from playwright.sync_api import Error, sync_playwright
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"private destination")
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                kwargs = {} if CHROME == "bundled" else {"executable_path": CHROME}
                browser = playwright.chromium.launch(headless=True, **kwargs)
                try:
                    context = browser.new_context()
                    page = context.new_page()
                    controller = ApplicationBrowser("owner", 1, "https://careers.example.test/apply", BrowserConfig(), time.time() + 3600)
                    controller._track_page(page)
                    context.route("**/*", controller._route_navigation)
                    page.route("https://careers.example.test/**", lambda route: route.fulfill(
                        status=302, headers={"Location": f"http://127.0.0.1:{server.server_port}/private"}))
                    with patch("job_hunter.application_browser._hostname_resolves_public", return_value=True):
                        with self.assertRaises(Error):
                            page.goto("https://careers.example.test/apply", timeout=5000)
                    self.assertEqual(requests, [])
                finally:
                    browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)

    def test_spa_navigation_invalidates_original_file_request(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            kwargs = {} if CHROME == "bundled" else {"executable_path": CHROME}
            browser = playwright.chromium.launch(headless=True, **kwargs)
            try:
                context = browser.new_context()
                page = context.new_page()
                controller = ApplicationBrowser("owner", 1, "https://careers.example.test/apply", BrowserConfig(), time.time() + 3600)
                controller._track_page(page)
                page.route("**/*", lambda route: route.fulfill(content_type="text/html", body='<label>Resume<input type="file"></label>'))
                with patch("job_hunter.application_browser._hostname_resolves_public", return_value=True):
                    page.goto("https://careers.example.test/apply")
                    controller._publish(state="ready")
                    page.get_by_label("Resume").click()
                    until = time.monotonic() + 2
                    while controller.snapshot().upload_request is None and time.monotonic() < until:
                        page.wait_for_timeout(25)
                    request = controller.snapshot().upload_request
                    self.assertIsNotNone(request)
                    page.evaluate("history.pushState({}, '', '/different-application')")
                    page.evaluate("history.pushState({}, '', '/apply')")
                    self.assertIsNone(controller.snapshot().upload_request)
                    with self.assertRaises(BrowserError):
                        controller.upload("owner", request.request_id, "cv.pdf", b"synthetic")
                    self.assertEqual(page.get_by_label("Resume").evaluate("el => el.files.length"), 0)
            finally:
                browser.close()

    def test_live_filechooser_upload_and_cleanup(self):
        from playwright.sync_api import sync_playwright
        observed = []
        page_ready = Event()
        client = Mock()
        client.create.return_value = CreatedSession("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "wss://unused.browserbase.com")
        client.live_url.return_value = "https://www.browserbase.com/devtools?synthetic=1"

        @contextmanager
        def connect(url):
            with sync_playwright() as playwright:
                kwargs = {} if CHROME == "bundled" else {"executable_path": CHROME}
                browser = playwright.chromium.launch(headless=True, **kwargs)
                context = browser.new_context()
                page = context.new_page()
                real_goto = page.goto
                def synthetic_goto(url, **options):
                    context.route("https://careers.example.test/**", lambda route: route.fulfill(
                        content_type="text/html", body='<label>Resume<input type="file" id="resume"></label>'
                        '<button onclick="document.body.dataset.submitted=\'yes\'">Submit</button>'
                    ))
                    result = real_goto(url, **options)
                    page.get_by_label("Resume").click()
                    page_ready.set()
                    return result
                with patch.object(page, "goto", side_effect=synthetic_goto):
                    try:
                        yield browser
                        observed.append(page.locator("#resume").evaluate("el => el.files[0]?.name"))
                        observed.append(page.locator("body").get_attribute("data-submitted"))
                    finally:
                        browser.close()

        controller = ApplicationBrowser("owner", 1, "https://careers.example.test/apply",
                                        BrowserConfig(True, "synthetic", "project"), time.time() + 3600,
                                        client=client, connect=connect)
        with patch("job_hunter.application_browser.validate_destination", side_effect=lambda value: value):
            controller.start()
            try:
                self.assertTrue(page_ready.wait(15), controller.snapshot().message)
                until = time.monotonic() + 5
                while (controller.snapshot().state != "ready" or controller.snapshot().upload_request is None) and time.monotonic() < until:
                    time.sleep(.05)
                request = controller.snapshot().upload_request
                self.assertIsNotNone(request)
                controller.upload("owner", request.request_id, "synthetic.pdf", b"%PDF-synthetic")
                until = time.monotonic() + 5
                while controller.snapshot().upload_request and time.monotonic() < until:
                    time.sleep(.05)
                self.assertIn("Document attached", controller.snapshot().message)
            finally:
                controller.close()
                controller.join(10)
        self.assertFalse(controller.is_alive())
        self.assertEqual(observed, ["synthetic.pdf", None])
        self.assertEqual(controller.snapshot().live_url, "")
        client.release.assert_called_once()
