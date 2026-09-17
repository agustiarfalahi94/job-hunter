"""Validated personal-account configuration and native OIDC identity claims."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import math
import re
import time
from typing import Mapping
from urllib.parse import urlsplit

from cryptography.fernet import Fernet


GOOGLE_ISSUER = "https://accounts.google.com"
GOOGLE_METADATA = f"{GOOGLE_ISSUER}/.well-known/openid-configuration"


class AccountConfigError(ValueError):
    pass


class AccountAccessError(ValueError):
    pass


@dataclass(frozen=True)
class AccountConfig:
    enabled: bool = False
    allowed_emails: tuple[str, ...] = field(default=(), repr=False)
    supabase_url: str = ""
    supabase_secret_key: str = field(default="", repr=False)
    encryption_key: str = field(default="", repr=False)
    client_id: str = field(default="", repr=False)


@dataclass(frozen=True)
class AccountIdentity:
    subject: str = field(repr=False)
    email: str = field(repr=False)
    expires_at: float

    @property
    def owner_id(self) -> str:
        return hashlib.sha256(f"{GOOGLE_ISSUER}\0{self.subject}".encode()).hexdigest()


def load_account_config(secrets: Mapping[str, object]) -> AccountConfig:
    try:
        section = secrets.get("accounts", {})
    except FileNotFoundError:
        return AccountConfig()
    if not isinstance(section, Mapping) or type(section.get("enabled", False)) is not bool:
        raise AccountConfigError("Account configuration must use enabled = true or false.")
    if not section.get("enabled", False):
        return AccountConfig()

    emails = section.get("allowed_emails")
    if (not isinstance(emails, list) or not 1 <= len(emails) <= 10
            or any(not isinstance(value, str) or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value.strip()) for value in emails)):
        raise AccountConfigError("Configure accounts.allowed_emails with the permitted Google account.")
    url = _required(section, "supabase_url")
    if not re.fullmatch(r"https://[a-z0-9-]+\.supabase\.co/?", url):
        raise AccountConfigError("Use the official HTTPS Supabase project URL without a path or credentials.")
    parsed = urlsplit(url)
    key = _required(section, "supabase_secret_key")
    if not re.fullmatch(r"sb_secret_[A-Za-z0-9_-]+", key):
        raise AccountConfigError("Use a server-only Supabase secret key, not a publishable key.")
    encryption_key = _required(section, "encryption_key")
    try:
        Fernet(encryption_key.encode("ascii"))
    except (ValueError, UnicodeError):
        raise AccountConfigError("Configure a valid accounts.encryption_key and keep it backed up privately.") from None

    auth = secrets.get("auth", {})
    if not isinstance(auth, Mapping):
        raise AccountConfigError("Configure the native Google auth secrets before enabling accounts.")
    callback = _required(auth, "redirect_uri")
    try:
        redirect = urlsplit(callback)
        secure = redirect.scheme == "https" or (
            redirect.scheme == "http" and redirect.hostname in {"localhost", "127.0.0.1"}
        )
        valid = (secure and redirect.hostname and redirect.path == "/oauth2callback"
                 and not redirect.query and not redirect.fragment and not redirect.username
                 and not redirect.password)
    except ValueError:
        valid = False
    if not valid:
        raise AccountConfigError("Use an HTTPS auth.redirect_uri ending in /oauth2callback (HTTP only on localhost).")
    if len(_required(auth, "cookie_secret")) < 32:
        raise AccountConfigError("Use a strong auth.cookie_secret of at least 32 characters.")
    google = auth.get("google", {})
    if not isinstance(google, Mapping):
        raise AccountConfigError("Configure auth.google for native Google sign-in.")
    client_id = _required(google, "client_id")
    _required(google, "client_secret")
    if google.get("server_metadata_url") != GOOGLE_METADATA:
        raise AccountConfigError("Use Google's official OIDC metadata URL in auth.google.")
    return AccountConfig(True, tuple(value.strip().casefold() for value in emails),
                         f"https://{parsed.hostname}", key, encryption_key, client_id)


def identity_from_claims(
    claims: Mapping[str, object], config: AccountConfig, *, now: float | None = None,
) -> AccountIdentity:
    # Claims must come from st.user after native OIDC validation, never client input.
    email = claims.get("email")
    subject = claims.get("sub")
    expiry = claims.get("exp")
    if (not config.enabled or claims.get("iss") not in (GOOGLE_ISSUER, "accounts.google.com")
            or not isinstance(subject, str) or not subject.strip() or len(subject) > 255
            or not isinstance(email, str) or email.strip().casefold() not in config.allowed_emails
            or claims.get("email_verified") is not True or claims.get("aud") != config.client_id):
        raise AccountAccessError("This Google account is not authorized for this private workspace.")
    if (type(expiry) not in {int, float} or not math.isfinite(expiry)
            or expiry <= (time.time() if now is None else now)):
        raise AccountAccessError("Your Google sign-in expired. Sign out and sign in again.")
    return AccountIdentity(subject, email.strip().casefold(), float(expiry))


def _required(section: Mapping[str, object], name: str) -> str:
    value = section.get(name)
    if not isinstance(value, str) or not value.strip():
        raise AccountConfigError(f"Account setup is incomplete: configure {name} in Streamlit Secrets.")
    return value.strip()
