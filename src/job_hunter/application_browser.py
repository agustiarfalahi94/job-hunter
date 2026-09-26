"""Session-owned remote browser worker; no Streamlit, storage, or auto-submit."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field, replace
import ipaddress
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
import time
from urllib.parse import urlsplit
from uuid import uuid4

from playwright.sync_api import Error as PlaywrightError

from job_hunter.browserbase_provider import (
    BrowserConfig, BrowserError, BrowserbaseClient, load_browser_config,
)
from job_hunter.search import _hostname_resolves_public


BROWSER_KEY = "application_browser"
MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
HEARTBEAT_SECONDS = 60
UPLOAD_REQUEST_SECONDS = 120
DOCUMENT_TYPES = {"pdf": "application/pdf", "doc": "application/msword",
                  "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


def validate_destination(url: str) -> str:
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if (parsed.scheme != "https" or parsed.username or parsed.password or
                parsed.port not in (None, 443) or "\\" in url or
                any(char.isspace() or ord(char) < 32 for char in url) or
                "." not in host or host.endswith((".local", ".localhost", ".internal"))):
            raise ValueError()
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError()
        if not _hostname_resolves_public(host):
            raise ValueError()
    except (TypeError, ValueError):
        raise BrowserError("The application destination must be a public HTTPS website without URL credentials.") from None
    return url


@dataclass(frozen=True)
class UploadRequest:
    request_id: str
    frame_url: str = field(repr=False)
    expires_at: float = field(default_factory=lambda: time.monotonic() + UPLOAD_REQUEST_SECONDS)

    @property
    def hostname(self) -> str:
        return urlsplit(self.frame_url).hostname or ""


@dataclass(frozen=True)
class BrowserSnapshot:
    state: str = "starting"
    message: str = "Starting your private application browser..."
    live_url: str = field(default="", repr=False)
    upload_request: UploadRequest | None = None
    seconds_remaining: int = 900


def attach_document(chooser, request: UploadRequest, request_id: str, filename: str, data: bytes) -> None:
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    extension = name.rsplit(".", 1)[-1].lower()
    if extension not in DOCUMENT_TYPES or not data or len(data) > MAX_DOCUMENT_BYTES:
        raise BrowserError("Choose a non-empty PDF, DOC or DOCX of at most 5 MB.")
    frame = chooser.element.owner_frame()
    if (time.monotonic() >= request.expires_at or request_id != request.request_id or
            frame is None or frame.url != request.frame_url or
            not chooser.element.evaluate("element => element.isConnected")):
        raise BrowserError("The upload field changed. Select the file field again before attaching a document.")
    chooser.set_files({"name": name, "mimeType": DOCUMENT_TYPES[extension], "buffer": data}, timeout=10000)


@contextmanager
def _connect_browser(url: str):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(url, timeout=20000)
        try:
            yield browser
        finally:
            browser.close()


class ApplicationBrowser:
    def __init__(self, owner_id: str, job_id: int, destination: str, config: BrowserConfig,
                 identity_expires_at: float, *, client=None, connect=None):
        self.owner_id, self.job_id = owner_id, job_id
        self.destination, self.config = destination, config
        self.identity_expires_at = identity_expires_at
        self.client = client or BrowserbaseClient(config)
        self.connect = connect or _connect_browser
        self.commands: Queue = Queue(maxsize=1)
        self._stop = Event()
        self._lock = Lock()
        self._snapshot = BrowserSnapshot()
        self._heartbeat = time.monotonic()
        self._thread = Thread(target=self._run, daemon=True, name="application-browser")
        self._chooser = None
        self._request = None
        self._cdp_sessions = {}

    def start(self) -> None:
        self._thread.start()

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def join(self, timeout=None) -> None:
        self._thread.join(timeout)

    def snapshot(self) -> BrowserSnapshot:
        with self._lock:
            return self._snapshot

    def touch(self, owner_id: str) -> None:
        if owner_id != self.owner_id:
            self.close()
            raise BrowserError("This browser belongs to a different signed-in session.")
        with self._lock:
            self._heartbeat = time.monotonic()

    def close(self) -> None:
        with self._lock:
            if self._snapshot.state in {"closed", "error"}:
                return
            self._stop.set()
            self._snapshot = replace(self._snapshot, state="closing", live_url="", upload_request=None,
                                     message="Closing the application browser...")

    def upload(self, owner_id: str, request_id: str, filename: str, data: bytes) -> None:
        if owner_id != self.owner_id or self._stop.is_set():
            raise BrowserError("This browser is no longer available to this account.")
        current = self.snapshot()
        if (current.state != "ready" or not current.upload_request or
                current.upload_request.request_id != request_id or
                time.monotonic() >= current.upload_request.expires_at):
            raise BrowserError("Select a file field in the application page first.")
        if not data or len(data) > MAX_DOCUMENT_BYTES:
            raise BrowserError("Choose a non-empty document of at most 5 MB.")
        try:
            self.commands.put_nowait((request_id, filename, bytes(data)))
        except Full:
            raise BrowserError("A document is already being attached. Wait for it to finish.") from None

    def _publish(self, **changes) -> None:
        with self._lock:
            if not self._stop.is_set():
                self._snapshot = replace(self._snapshot, **changes)

    def _file_requested(self, chooser) -> None:
        self._invalidate_upload()
        try:
            frame = chooser.element.owner_frame()
            if frame is None:
                return
            validate_destination(frame.url)
        except (BrowserError, PlaywrightError):
            self._publish(message="This file field is no longer available on a public HTTPS page.")
            return
        self._chooser = chooser
        self._request = UploadRequest(uuid4().hex, frame.url)
        self._publish(upload_request=self._request, message="An application page is requesting a document.")

    def _track_page(self, page) -> None:
        if page in self._cdp_sessions:
            return
        page.on("filechooser", self._file_requested)
        page.on("framenavigated", self._invalidate_upload)
        page.on("framedetached", self._invalidate_upload)
        page.on("close", self._invalidate_upload)
        # Playwright routes only the first request in a redirect chain. CDP pauses each hop.
        session = page.context.new_cdp_session(page)
        self._cdp_sessions[page] = session
        session.on("Fetch.requestPaused", lambda event: self._guard_navigation(session, event))
        session.send("Fetch.enable", {"patterns": [{"resourceType": "Document", "requestStage": "Request"}]})

    def _guard_navigation(self, session, event) -> None:
        try:
            validate_destination(event["request"]["url"])
        except (BrowserError, KeyError):
            method = "Fetch.failRequest"
            params = {"requestId": event["requestId"], "errorReason": "BlockedByClient"}
            self._publish(message="Blocked a destination that is not a public HTTPS website.")
        else:
            method = "Fetch.continueRequest"
            params = {"requestId": event["requestId"]}
        try:
            session.send(method, params)
        except PlaywrightError:
            self.close()

    def _invalidate_upload(self, *args) -> None:
        if self._request is not None:
            self._chooser, self._request = None, None
            self._publish(upload_request=None, message="The document request changed or expired. Select the file field again.")

    def _route_navigation(self, route) -> None:
        if route.request.is_navigation_request():
            try:
                validate_destination(route.request.url)
                self._track_page(route.request.frame.page)
            except BrowserError:
                route.abort()
                return
        route.continue_()

    def _attach_pending(self) -> None:
        if self._request and time.monotonic() >= self._request.expires_at:
            self._invalidate_upload()
        try:
            request_id, filename, data = self.commands.get_nowait()
        except Empty:
            return
        try:
            if self._stop.is_set() or self._chooser is None or self._request is None:
                return
            attach_document(self._chooser, self._request, request_id, filename, data)
            self._publish(message="Document attached. Review the application before submitting.")
        except BrowserError as exc:
            self._publish(message=str(exc))
        except Exception:
            self._publish(message="The page could not accept the document. Select its file field again or use the original page.")
        finally:
            # The file bytes and remote element are never retained after the command.
            self._chooser, self._request = None, None
            self._publish(upload_request=None)

    def _run(self) -> None:
        session_id = ""
        final_state, message = "closed", "Application browser closed."
        deadline = time.monotonic() + self.config.timeout_seconds
        try:
            if not self.config.enabled:
                raise BrowserError("The application browser is disabled.")
            if not self.owner_id or self.identity_expires_at - time.time() < 60:
                raise BrowserError("Sign in again before starting an application browser.")
            validate_destination(self.destination)
            if self._stop.is_set():
                return
            timeout = min(self.config.timeout_seconds, int(self.identity_expires_at - time.time()))
            created = self.client.create(timeout)
            session_id = created.session_id
            if self._stop.is_set():
                return
            with self.connect(created.connect_url) as browser:
                context = browser.contexts[0]
                context.route("**/*", self._route_navigation)
                context.on("page", self._track_page)
                for page in context.pages:
                    self._track_page(page)
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(self.destination, wait_until="domcontentloaded", timeout=25000)
                if self._stop.is_set():
                    return
                self._publish(state="ready", message="Application browser ready. Submission remains under your control.",
                              live_url=self.client.live_url(session_id))
                while not self._stop.is_set():
                    remaining = min(deadline - time.monotonic(), self.identity_expires_at - time.time())
                    with self._lock:
                        abandoned = time.monotonic() - self._heartbeat > HEARTBEAT_SECONDS
                    if remaining <= 0 or abandoned:
                        message = "Application browser expired. Open a new session to continue."
                        break
                    self._publish(seconds_remaining=max(0, int(remaining)))
                    self._attach_pending()
                    if not browser.is_connected() or not context.pages:
                        message = "The remote browser disconnected. Open a new session or use the original page."
                        break
                    active_page = context.pages[0]
                    try:
                        active_page.wait_for_timeout(250)
                    except PlaywrightError:
                        if not active_page.is_closed() or not browser.is_connected() or not context.pages:
                            raise
        except BrowserError as exc:
            final_state, message = "error", str(exc)
        except Exception:
            final_state, message = "error", "The application browser could not load or lost its connection. Use the original page or try again."
        finally:
            if session_id:
                try:
                    self.client.release(session_id)
                except BrowserError:
                    message += " Closure could not be confirmed; check Browserbase Sessions. The provider timeout still applies."
            self._chooser, self._request = None, None
            self._cdp_sessions.clear()
            while not self.commands.empty():
                try:
                    self.commands.get_nowait()
                except Empty:
                    break
            with self._lock:
                self._snapshot = BrowserSnapshot(final_state, message, seconds_remaining=0)
