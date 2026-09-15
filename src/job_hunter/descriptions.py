"""Extract job descriptions without overstating incomplete source text."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Literal

from bs4 import BeautifulSoup


DescriptionKind = Literal["full", "snippet", "unavailable"]
DESCRIPTION_SELECTORS = (
    '[itemprop="description"]',
    '[data-automation="jobAdDetails"]',
    '[data-testid="jobDescription"]',
    "#jobDescriptionText",
    ".description__text",
    ".job-description",
    '[class*="job-description"]',
)


@dataclass(frozen=True)
class JobDescription:
    text: str
    kind: DescriptionKind
    source: str
    limitation: str = ""


def extract_job_description(html: str, snippet: str = "") -> JobDescription:
    snippet_text = _normalize(snippet)
    if html.strip():
        soup = BeautifulSoup(html, "html.parser")
        structured = _structured_description(soup)
        if _is_full_description(structured):
            return JobDescription(
                text=structured,
                kind="full",
                source="JobPosting.description",
            )
        for selector in DESCRIPTION_SELECTORS:
            node = soup.select_one(selector)
            if node is None:
                continue
            _remove_noise(node)
            description = _normalize(node.get_text(" ", strip=True))
            if _is_full_description(description):
                return JobDescription(
                    text=description,
                    kind="full",
                    source="job description container",
                )
    if snippet_text:
        return JobDescription(
            text=snippet_text,
            kind="snippet",
            source="search result",
            limitation="Full job description was unavailable; score uses a search snippet.",
        )
    return JobDescription(
        text="",
        kind="unavailable",
        source="",
        limitation="No readable job description was available.",
    )


def _structured_description(soup: BeautifulSoup) -> str:
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or script.get_text() or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        raw = _job_posting_description(payload)
        if raw:
            fragment = BeautifulSoup(raw, "html.parser")
            _remove_noise(fragment)
            return _normalize(fragment.get_text(" ", strip=True))
    return ""


def _job_posting_description(value: object) -> str:
    if isinstance(value, dict):
        item_type = value.get("@type")
        types = item_type if isinstance(item_type, list) else [item_type]
        if any(str(candidate).casefold() == "jobposting" for candidate in types):
            description = value.get("description")
            if isinstance(description, str):
                return description
        for child in value.values():
            found = _job_posting_description(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _job_posting_description(child)
            if found:
                return found
    return ""


def _remove_noise(node: BeautifulSoup) -> None:
    for noise in node.select("script, style, nav, footer, form, noscript, dialog"):
        noise.decompose()


def _is_full_description(text: str) -> bool:
    return len(text) >= 80 and len(text.split()) >= 12


def _normalize(value: str) -> str:
    return " ".join(value.split())
