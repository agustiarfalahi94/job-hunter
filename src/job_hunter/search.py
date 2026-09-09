"""Public web-result job search and queue ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from bs4 import BeautifulSoup

from job_hunter.queue import JobQueue
from job_hunter.queue_types import JobInput


DUCKDUCKGO_HTML_URL = "https://duckduckgo.com/html/?q={query}"
LINKEDIN_SEARCH_URL = "https://www.linkedin.com/jobs/search/?keywords={keywords}&location={location}"
PLATFORM_SITE_FILTERS = {
    "LinkedIn": "site:linkedin.com/jobs",
    "JobStreet": "site:my.jobstreet.com",
    "Indeed": "site:my.indeed.com OR site:indeed.com",
    "Foundit": "site:foundit.my OR site:foundit.com.my",
    "Company career pages": (
        "site:careers.accenture.com OR site:hcltech.com/careers OR "
        "site:razer.com/careers OR site:prudential.com.my/careers OR site:accordinnovations.com"
    ),
}
PLATFORM_JOB_PATH_HINTS = {
    "LinkedIn": ("/jobs/", "/jobs/view/"),
    "JobStreet": ("/job/", "/jobs/"),
    "Indeed": ("/viewjob", "/jobs/", "/rc/clk"),
    "Foundit": ("/job/", "/jobs/"),
    "Company career pages": ("job", "career", "position", "opening"),
}
NOISE_TERMS = ("course", "training", "certification", "learn ", "tutorial", "bootcamp")


@dataclass(frozen=True)
class SearchCriteria:
    title_terms: tuple[str, ...]
    description_terms: tuple[str, ...]
    location: str
    platforms: tuple[str, ...]
    max_results: int = 50


@dataclass(frozen=True)
class PlatformQuery:
    platform: str
    query: str
    url: str
    parser: str = "duckduckgo"


@dataclass(frozen=True)
class SearchCandidate:
    title: str
    company: str
    location: str
    description: str
    source_url: str
    platform: str


@dataclass(frozen=True)
class SearchRunSummary:
    checked: int
    added: int
    duplicates: int
    skipped: int
    logs: tuple[str, ...]


def build_search_queries(criteria: SearchCriteria) -> list[PlatformQuery]:
    title_part = _quoted_or(criteria.title_terms)
    description_part = _quoted_or(criteria.description_terms)
    location_part = f'"{criteria.location}"' if criteria.location else ""
    queries = []
    for platform in criteria.platforms:
        site_filter = PLATFORM_SITE_FILTERS.get(platform)
        if not site_filter:
            continue
        query = " ".join(part for part in (site_filter, title_part, description_part, location_part) if part)
        queries.append(PlatformQuery(platform=platform, query=query, url=DUCKDUCKGO_HTML_URL.format(query=quote_plus(query))))
    return queries


def build_direct_platform_queries(criteria: SearchCriteria) -> list[PlatformQuery]:
    queries = []
    if "LinkedIn" not in criteria.platforms:
        return queries
    keywords = " ".join(tuple(criteria.title_terms) + tuple(criteria.description_terms))
    if not keywords.strip():
        return queries
    query = f"{keywords.strip()} {criteria.location}".strip()
    queries.append(
        PlatformQuery(
            platform="LinkedIn",
            query=query,
            url=LINKEDIN_SEARCH_URL.format(
                keywords=quote_plus(keywords.strip()),
                location=quote_plus(criteria.location),
            ),
            parser="linkedin",
        )
    )
    return queries


def parse_linkedin_jobs(html: str, location: str, limit: int) -> list[SearchCandidate]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[SearchCandidate] = []
    cards = soup.select(".base-search-card")
    for card in cards:
        if len(candidates) >= limit:
            break
        link = card.select_one("a.base-card__full-link")
        title_node = card.select_one(".base-search-card__title")
        company_node = card.select_one(".base-search-card__subtitle")
        location_node = card.select_one(".job-search-card__location")
        if link is None or title_node is None:
            continue
        source_url = str(link.get("href", "")).strip()
        title = title_node.get_text(" ", strip=True)
        company = company_node.get_text(" ", strip=True) if company_node else ""
        card_location = location_node.get_text(" ", strip=True) if location_node else location
        if not source_url or not title:
            continue
        if not _looks_like_job_result(source_url, title, "LinkedIn"):
            continue
        description = " ".join(part for part in (title, company, card_location) if part)
        candidates.append(
            SearchCandidate(
                title=title,
                company=company,
                location=card_location or location,
                description=description,
                source_url=source_url,
                platform="LinkedIn",
            )
        )
    return candidates


def parse_duckduckgo_results(html: str, platform: str, location: str, limit: int) -> list[SearchCandidate]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[SearchCandidate] = []
    anchors = soup.find_all("a", class_="result__a")
    for anchor in anchors:
        if len(candidates) >= limit:
            break
        href = _clean_duckduckgo_url(str(anchor.get("href", "")))
        title_text = anchor.get_text(" ", strip=True)
        snippet_node = anchor.find_next("a", class_="result__snippet") or anchor.find_next(class_="result__snippet")
        snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
        title, company = _split_title_company(title_text)
        if not title or not href:
            continue
        if not _looks_like_job_result(href, title_text, platform):
            continue
        candidates.append(
            SearchCandidate(
                title=title,
                company=company,
                location=location,
                description=snippet or title_text,
                source_url=href,
                platform=platform,
            )
        )
    return candidates


def run_public_search(
    criteria: SearchCriteria,
    preferences: dict[str, object],
    queue: JobQueue,
    fetcher: Callable[[str], str] | None = None,
) -> SearchRunSummary:
    fetch = fetcher or fetch_public_html
    checked = 0
    added = 0
    duplicates = 0
    skipped = 0
    logs: list[str] = []
    remaining = max(0, min(50, criteria.max_results))
    platform_queries = build_direct_platform_queries(criteria)
    direct_platforms = {query.platform for query in platform_queries}
    platform_queries.extend(query for query in build_search_queries(criteria) if query.platform not in direct_platforms)
    for platform_query in platform_queries:
        if remaining <= 0:
            break
        logs.append(f"Searching {platform_query.platform}: {platform_query.query}")
        try:
            html = fetch(platform_query.url)
        except Exception as exc:
            skipped += 1
            logs.append(f"Skipped {platform_query.platform}: {exc}")
            continue
        if _is_blocked_search_page(html):
            skipped += 1
            logs.append(f"Skipped {platform_query.platform}: search provider returned a challenge page.")
            continue
        if platform_query.parser == "linkedin":
            candidates = parse_linkedin_jobs(html, criteria.location, remaining)
        else:
            candidates = parse_duckduckgo_results(html, platform_query.platform, criteria.location, remaining)
        if not candidates:
            logs.append(f"No public results found for {platform_query.platform}.")
        for candidate in candidates:
            if checked >= criteria.max_results:
                break
            checked += 1
            remaining -= 1
            result = queue.add_job(
                JobInput(
                    title=candidate.title,
                    company=candidate.company,
                    location=candidate.location,
                    description=candidate.description,
                    source_url=candidate.source_url,
                ),
                preferences,
            )
            if result.created:
                added += 1
                logs.append(f"Added {candidate.title} at {candidate.company or 'unknown company'} ({result.score}/100)")
            else:
                duplicates += 1
                logs.append(f"Duplicate skipped: {candidate.title} at {candidate.company or 'unknown company'}")
    return SearchRunSummary(checked=checked, added=added, duplicates=duplicates, skipped=skipped, logs=tuple(logs))


def fetch_public_html(url: str) -> str:
    import requests

    response = requests.get(
        url,
        headers={"User-Agent": "JobHunter/1.4 (+https://github.com/agustiarfalahi94/job-hunter)"},
        timeout=(5, 20),
    )
    response.raise_for_status()
    return response.text


def _quoted_or(values: tuple[str, ...]) -> str:
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    if not cleaned:
        return ""
    return " OR ".join(f'"{value}"' for value in cleaned)


def _clean_duckduckgo_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(target)
    return url


def _split_title_company(text: str) -> tuple[str, str]:
    separators = (" - ", " | ", " at ")
    for separator in separators:
        if separator in text:
            left, right = text.split(separator, 1)
            return left.strip(), right.strip()
    return text.strip(), ""


def _is_blocked_search_page(html: str) -> bool:
    normalized = html.casefold()
    return "anomaly-modal" in normalized or "challenge-form" in normalized or "access denied" in normalized


def _looks_like_job_result(url: str, title: str, platform: str) -> bool:
    normalized_url = url.casefold()
    normalized_title = title.casefold()
    if any(term in normalized_title or term in normalized_url for term in NOISE_TERMS):
        return False
    hints = PLATFORM_JOB_PATH_HINTS.get(platform, ())
    if not hints:
        return True
    return any(hint in normalized_url for hint in hints)
