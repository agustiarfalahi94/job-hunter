"""Conservative job identity and source-link normalization."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


TRACKING_KEYS = {
    "ref",
    "refid",
    "source",
    "trackingid",
    "trk",
    "trkemail",
}
GENERIC_VALUES = {"", "unknown", "not specified", "n/a", "na", "job", "role"}


@dataclass(frozen=True)
class JobSource:
    platform: str
    original_url: str
    canonical_url: str
    stable_id: str = ""


def job_source(platform: str, url: str) -> JobSource:
    return JobSource(
        platform=platform.strip(),
        original_url=url.strip(),
        canonical_url=canonicalize_job_url(url),
        stable_id=stable_job_id(platform, url),
    )


def canonicalize_job_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        return ""
    hostname = parsed.hostname.casefold()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    netloc = hostname
    if parsed.port and parsed.port not in {80, 443}:
        netloc = f"{hostname}:{parsed.port}"
    filtered_query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=False):
        normalized_key = key.casefold()
        if normalized_key.startswith("utm_") or normalized_key in TRACKING_KEYS:
            continue
        filtered_query.append((key, value))
    path = re.sub(r"/+", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urlunparse(
        (
            "https",
            netloc,
            path,
            "",
            urlencode(sorted(filtered_query)),
            "",
        )
    )


def stable_job_id(platform: str, url: str) -> str:
    parsed = urlparse(url)
    normalized_platform = platform.casefold()
    query = dict(parse_qsl(parsed.query))
    if "linkedin" in normalized_platform:
        match = re.search(r"/jobs/(?:view/)?(?:[^/?#]*-)?(\d+)(?:/|$)", parsed.path)
        return (match.group(1) if match else query.get("currentJobId", "")).strip()
    if "indeed" in normalized_platform:
        return query.get("jk", "").strip()
    if "jobstreet" in normalized_platform:
        match = re.search(r"/jobs?/(?:[^/?#]*-)?(\d+)(?:/|$)", parsed.path)
        return match.group(1) if match else ""
    if "foundit" in normalized_platform:
        match = re.search(r"(?:-|/)(\d+)(?:/|$)", parsed.path.rstrip("/"))
        return match.group(1) if match else ""
    return ""


def vacancy_fingerprint(title: str, company: str, location: str) -> str:
    parts = tuple(_normalize(value) for value in (title, company, location))
    if any(part in GENERIC_VALUES for part in parts):
        return ""
    if len(parts[0]) < 5 or len(parts[1]) < 3 or len(parts[2]) < 3:
        return ""
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _normalize(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())
