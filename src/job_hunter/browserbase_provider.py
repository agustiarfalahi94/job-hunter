"""Server-only Browserbase configuration and bounded session requests."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from urllib.parse import urlsplit
from uuid import UUID

import requests

from job_hunter.runtime_config import _secret_value


class BrowserError(ValueError):
    """A message safe to show without provider responses or credentials."""


@dataclass(frozen=True)
class BrowserConfig:
    enabled: bool = False
    api_key: str = field(default="", repr=False)
    project_id: str = field(default="", repr=False)
    timeout_seconds: int = 900


@dataclass(frozen=True)
class CreatedSession:
    session_id: str = field(repr=False)
    connect_url: str = field(repr=False)


def load_browser_config(secrets=None, environ=None) -> BrowserConfig:
    env = os.environ if environ is None else environ
    try:
        value = secrets.get("BROWSERBASE_ENABLED") if secrets is not None else None
    except FileNotFoundError:
        value = None
    if value is None:
        value = env.get("BROWSERBASE_ENABLED", "false")
    if str(value).casefold() not in {"true", "false"}:
        raise BrowserError("BROWSERBASE_ENABLED must be true or false.")
    if str(value).casefold() == "false":
        return BrowserConfig()
    key = _secret_value(secrets, "BROWSERBASE_API_KEY") or env.get("BROWSERBASE_API_KEY", "")
    project = _secret_value(secrets, "BROWSERBASE_PROJECT_ID") or env.get("BROWSERBASE_PROJECT_ID", "")
    if not key or not project:
        raise BrowserError("Configure BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID in Streamlit secrets.")
    try:
        UUID(project)
    except (ValueError, TypeError):
        raise BrowserError("BROWSERBASE_PROJECT_ID must be the project ID from Browserbase Settings.") from None
    return BrowserConfig(True, key, project)


def provider_url(value: object, scheme: str) -> str:
    try:
        parsed = urlsplit(value if isinstance(value, str) else "")
        host = parsed.hostname or ""
        valid = (isinstance(value, str) and value.startswith(f"{scheme}://") and parsed.scheme == scheme and
                 (host == "browserbase.com" or host.endswith(".browserbase.com")) and
                 parsed.port in (None, 443) and not parsed.username and not parsed.password and
                 not any(char.isspace() for char in value) and "\\" not in value)
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise BrowserError("Browserbase returned an invalid browser address.")
    return value


class BrowserbaseClient:
    def __init__(self, config: BrowserConfig, *, request=None):
        self.config = config
        self._request = request or requests.request

    def _call(self, method: str, path: str, payload=None) -> dict:
        try:
            reply = self._request(
                method, f"https://api.browserbase.com/v1/sessions{path}",
                headers={"X-BB-API-Key": self.config.api_key},
                json=payload, timeout=(5, 15), allow_redirects=False,
            )
            if reply.status_code in (401, 403):
                raise BrowserError("Browserbase denied access. Check the API key and project permissions.")
            if reply.status_code in (402, 429):
                raise BrowserError("Browserbase usage or concurrent-session limit reached. Close other sessions or check your plan.")
            if not 200 <= reply.status_code < 300:
                raise BrowserError("Browserbase could not complete the request. Try again later or open the original page.")
            result = reply.json()
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except requests.RequestException:
            raise BrowserError("Browserbase did not respond. A requested session may remain until its 15-minute timeout; check the Browserbase dashboard before retrying.") from None
        except (TypeError, ValueError) as exc:
            if isinstance(exc, BrowserError):
                raise
            raise BrowserError("Browserbase returned an unreadable response.") from None

    def create(self, timeout: int) -> CreatedSession:
        result = self._call("POST", "", {
            "projectId": self.config.project_id,
            "timeout": max(60, min(timeout, 900)),
            "keepAlive": False,
            "proxies": False,
            "browserSettings": {"recordSession": False, "logSession": False,
                                "solveCaptchas": False, "advancedStealth": False,
                                "viewport": {"width": 1280, "height": 900}},
        })
        session_id = result.get("id", "")
        try:
            UUID(session_id)
        except (ValueError, TypeError, AttributeError):
            raise BrowserError("Browserbase returned an invalid session ID. Check its dashboard before retrying.") from None
        try:
            connect_url = provider_url(result.get("connectUrl"), "wss")
        except BrowserError:
            try:
                self.release(session_id)
            except BrowserError:
                pass
            raise
        return CreatedSession(session_id, connect_url)

    def live_url(self, session_id: str) -> str:
        UUID(session_id)
        return provider_url(self._call("GET", f"/{session_id}/debug").get("debuggerUrl"), "https")

    def release(self, session_id: str) -> None:
        UUID(session_id)
        self._call("POST", f"/{session_id}", {"status": "REQUEST_RELEASE"})
