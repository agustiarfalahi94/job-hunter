"""Validate and select safe job-application destinations."""

from __future__ import annotations

from urllib.parse import urlparse


KNOWN_ATS_DOMAINS = (
    "ashbyhq.com",
    "greenhouse.io",
    "icims.com",
    "lever.co",
    "myworkdayjobs.com",
    "smartrecruiters.com",
    "successfactors.com",
    "taleo.net",
    "workable.com",
)


def is_safe_application_url(url: str, source_url: str) -> bool:
    parsed = urlparse(url)
    source = urlparse(source_url)
    hostname = (parsed.hostname or "").casefold()
    source_hostname = (source.hostname or "").casefold()
    if parsed.scheme != "https" or source.scheme != "https":
        return False
    if not hostname or not source_hostname:
        return False
    same_site = (
        hostname == source_hostname
        or hostname.endswith(f".{source_hostname}")
        or source_hostname.endswith(f".{hostname}")
    )
    known_ats = any(
        hostname == domain or hostname.endswith(f".{domain}") for domain in KNOWN_ATS_DOMAINS
    )
    return same_site or known_ats


def application_destination_url(apply_url: str, source_url: str) -> str:
    if is_safe_application_url(apply_url, source_url):
        return apply_url
    parsed = urlparse(source_url)
    if parsed.scheme == "https" and parsed.hostname:
        return source_url
    return ""


def application_destination_hostname(apply_url: str, source_url: str) -> str:
    destination = application_destination_url(apply_url, source_url)
    return (urlparse(destination).hostname or "").casefold()
