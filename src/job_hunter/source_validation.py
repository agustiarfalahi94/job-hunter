"""Validate user-provided job source domains for SerpAPI site search."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import re
from typing import Iterable
from urllib.parse import urlparse


MAX_CUSTOM_SOURCES = 5
HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
COMPANY_SOURCE_DOMAINS = {
    "Accenture": "careers.accenture.com",
    "HCLTech": "hcltech.com",
    "Razer": "razer.com",
    "Prudential Malaysia": "prudential.com.my",
    "Accord Innovations": "accordinnovations.com",
}
COMPANY_SOURCE_OPTIONS = tuple(COMPANY_SOURCE_DOMAINS)


@dataclass(frozen=True)
class CustomSource:
    hostname: str
    site_filter: str


def resolve_company_sources(
    values: Iterable[str], *, has_api_search: bool
) -> tuple[tuple[CustomSource, ...], tuple[str, ...]]:
    """Resolve friendly company names or user-entered public career domains."""
    resolved = [
        _resolve_company_value(str(value))
        for value in values
        if str(value).strip()
    ]
    return validate_custom_sources(resolved, has_api_search=has_api_search)


def validate_custom_sources(
    values: Iterable[str], *, has_api_search: bool
) -> tuple[tuple[CustomSource, ...], tuple[str, ...]]:
    raw_values = [str(value).strip() for value in values if str(value).strip()]
    if not raw_values:
        return (), ()
    if not has_api_search:
        return (), ("Additional platform domains require SerpAPI search.",)

    sources: list[CustomSource] = []
    errors: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        try:
            hostname = _validated_hostname(value)
        except ValueError as exc:
            errors.append(f"{value}: {exc}")
            continue
        if hostname in seen:
            continue
        if len(sources) >= MAX_CUSTOM_SOURCES:
            if "Only the first 5 additional domains are used." not in errors:
                errors.append("Only the first 5 additional domains are used.")
            continue
        seen.add(hostname)
        sources.append(CustomSource(hostname=hostname, site_filter=f"site:{hostname}"))
    return tuple(sources), tuple(errors)


def _validated_hostname(value: str) -> str:
    explicit_scheme = "://" in value
    parsed = urlparse(value if explicit_scheme else f"https://{value}")
    if parsed.scheme.casefold() != "https":
        raise ValueError("use an HTTPS URL or domain")
    if parsed.username or parsed.password:
        raise ValueError("credentials are not allowed in source URLs")
    if parsed.port not in {None, 443}:
        raise ValueError("custom ports are not supported")
    hostname = (parsed.hostname or "").rstrip(".").casefold()
    if not hostname or " " in hostname:
        raise ValueError("enter a valid domain")
    try:
        hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("enter a valid domain") from exc
    if hostname.startswith("www."):
        hostname = hostname[4:]
    if hostname == "localhost" or hostname.endswith(".local"):
        raise ValueError("local addresses are not supported")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        labels = hostname.split(".")
        if len(labels) < 2 or any(not HOST_LABEL.fullmatch(label) for label in labels):
            raise ValueError("enter a valid public domain")
    else:
        if not address.is_global:
            raise ValueError("private or local addresses are not supported")
    return hostname


def _normalize_company_name(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def _resolve_company_value(value: str) -> str:
    if any(marker in value for marker in (".", "/", ":")):
        return value.strip()
    normalized = _normalize_company_name(value)
    compact = normalized.replace(" ", "")
    matches = []
    for name, domain in COMPANY_SOURCE_DOMAINS.items():
        known = _normalize_company_name(name)
        known_compact = known.replace(" ", "")
        if (
            known == normalized
            or known in normalized
            or (len(compact) >= 4 and compact in known_compact)
            or (len(known_compact) >= 4 and known_compact in compact)
        ):
            matches.append(domain)
    return matches[0] if len(set(matches)) == 1 else value.strip()
