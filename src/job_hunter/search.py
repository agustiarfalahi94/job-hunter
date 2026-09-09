"""Public web-result job search and queue ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import json
from urllib.parse import parse_qs, quote_plus, unquote, urlencode, urlparse

from bs4 import BeautifulSoup

from job_hunter.queue import JobQueue
from job_hunter.queue_types import JobInput
from job_hunter.runtime_config import SearchProviderConfig


DUCKDUCKGO_HTML_URL = "https://duckduckgo.com/html/?q={query}"
LINKEDIN_SEARCH_URL = "https://www.linkedin.com/jobs/search/?keywords={keywords}&location={location}"
SERPAPI_URL = "https://serpapi.com/search.json?{params}"
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
PLATFORM_DOMAINS = {
    "LinkedIn": ("linkedin.com",),
    "JobStreet": ("jobstreet.com", "jobstreet.com.my"),
    "Indeed": ("indeed.com", "indeed.com.my"),
    "Foundit": ("foundit.my", "foundit.com.my"),
    "Company career pages": (
        "accenture.com",
        "hcltech.com",
        "razer.com",
        "prudential.com.my",
        "accordinnovations.com",
    ),
}
NOISE_TERMS = ("course", "training", "certification", "learn ", "tutorial", "bootcamp")
CLOSED_JOB_MARKERS = (
    "no longer accepting applications",
    "applications are closed",
    "applications closed",
    "job is no longer available",
    "position has been filled",
    "this job has expired",
    "job has expired",
)


@dataclass(frozen=True)
class SearchCriteria:
    title_terms: tuple[str, ...]
    description_terms: tuple[str, ...]
    location: str
    platforms: tuple[str, ...]
    max_results: int = 50
    posted_within_days: int | None = 30


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
    closed_reason: str = ""


@dataclass(frozen=True)
class SearchRunSummary:
    checked: int
    added: int
    duplicates: int
    skipped: int
    logs: tuple[str, ...]


@dataclass(frozen=True)
class SearchProgress:
    stage: str
    checked: int
    total: int
    message: str


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
        url = DUCKDUCKGO_HTML_URL.format(query=quote_plus(query))
        date_filter = _duckduckgo_date_filter(criteria.posted_within_days)
        if date_filter:
            url = f"{url}&df={date_filter}"
        queries.append(PlatformQuery(platform=platform, query=query, url=url))
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
            url=_with_linkedin_date_filter(
                LINKEDIN_SEARCH_URL.format(
                    keywords=quote_plus(keywords.strip()),
                    location=quote_plus(criteria.location),
                ),
                criteria.posted_within_days,
            ),
            parser="linkedin",
        )
    )
    return queries


def build_serpapi_queries(criteria: SearchCriteria, api_key: str) -> list[PlatformQuery]:
    if not api_key:
        return []
    queries = []
    for platform_query in build_search_queries(criteria):
        params: dict[str, object] = {
            "engine": "google",
            "q": platform_query.query,
            "api_key": api_key,
            "num": _result_limit(criteria.max_results),
        }
        date_filter = _google_date_filter(criteria.posted_within_days)
        if date_filter:
            params["tbs"] = date_filter
        queries.append(
            PlatformQuery(
                platform=platform_query.platform,
                query=platform_query.query,
                url=SERPAPI_URL.format(params=urlencode(params)),
                parser="serpapi",
            )
        )
    return queries


def parse_serpapi_results(payload: str, platform: str, location: str, limit: int) -> list[SearchCandidate]:
    data = json.loads(payload or "{}")
    candidates: list[SearchCandidate] = []
    for item in data.get("organic_results", []):
        if len(candidates) >= limit:
            break
        title_text = str(item.get("title", "")).strip()
        href = str(item.get("link", "")).strip()
        snippet = str(item.get("snippet", "")).strip()
        title, company = _split_title_company(title_text)
        if not title or not href:
            continue
        if not _looks_like_job_result(href, title_text, platform):
            continue
        closed_reason = _closed_job_reason(" ".join((title_text, snippet)))
        candidates.append(
            SearchCandidate(
                title=title,
                company=company,
                location=location,
                description=snippet or title_text,
                source_url=href,
                platform=platform,
                closed_reason=closed_reason,
            )
        )
    return candidates


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
        card_text = card.get_text(" ", strip=True)
        description = " ".join(part for part in (title, company, card_location) if part)
        candidates.append(
            SearchCandidate(
                title=title,
                company=company,
                location=card_location or location,
                description=description,
                source_url=source_url,
                platform="LinkedIn",
                closed_reason=_closed_job_reason(card_text),
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
        closed_reason = _closed_job_reason(" ".join((title_text, snippet)))
        candidates.append(
            SearchCandidate(
                title=title,
                company=company,
                location=location,
                description=snippet or title_text,
                source_url=href,
                platform=platform,
                closed_reason=closed_reason,
            )
        )
    return candidates


def run_public_search(
    criteria: SearchCriteria,
    preferences: dict[str, object],
    queue: JobQueue,
    fetcher: Callable[[str], str] | None = None,
    provider_config: SearchProviderConfig | None = None,
    progress_callback: Callable[[SearchProgress], None] | None = None,
) -> SearchRunSummary:
    fetch = fetcher or fetch_public_html
    fetch_availability = fetcher or fetch_job_html
    checked = 0
    added = 0
    duplicates = 0
    skipped = 0
    logs: list[str] = []
    search_limit = _result_limit(criteria.max_results)
    remaining = search_limit
    provider = provider_config or SearchProviderConfig()
    if provider.has_api_search:
        platform_queries = build_serpapi_queries(criteria, provider.serpapi_key)
    else:
        platform_queries = build_direct_platform_queries(criteria)
        direct_platforms = {query.platform for query in platform_queries}
        platform_queries.extend(query for query in build_search_queries(criteria) if query.platform not in direct_platforms)
    for platform_query in platform_queries:
        if remaining <= 0:
            break
        prefix = "API search" if platform_query.parser == "serpapi" else "Searching"
        _report_progress(
            logs,
            progress_callback,
            stage="searching",
            checked=checked,
            total=search_limit,
            message=f"{prefix} {platform_query.platform}: {platform_query.query}",
        )
        try:
            html = fetch(platform_query.url)
        except Exception:
            skipped += 1
            _report_progress(
                logs,
                progress_callback,
                stage="skipped",
                checked=checked,
                total=search_limit,
                message=f"Skipped {platform_query.platform}: request failed",
            )
            continue
        if _is_blocked_search_page(html):
            skipped += 1
            _report_progress(
                logs,
                progress_callback,
                stage="skipped",
                checked=checked,
                total=search_limit,
                message=f"Skipped {platform_query.platform}: search provider returned a challenge page.",
            )
            continue
        if platform_query.parser == "linkedin":
            candidates = parse_linkedin_jobs(html, criteria.location, remaining)
        elif platform_query.parser == "serpapi":
            candidates = parse_serpapi_results(html, platform_query.platform, criteria.location, remaining)
        else:
            candidates = parse_duckduckgo_results(html, platform_query.platform, criteria.location, remaining)
        if not candidates:
            _report_progress(
                logs,
                progress_callback,
                stage="empty",
                checked=checked,
                total=search_limit,
                message=f"No public results found for {platform_query.platform}.",
            )
        for candidate in candidates:
            if checked >= search_limit:
                break
            checked += 1
            remaining -= 1
            if candidate.closed_reason:
                skipped += 1
                _report_progress(
                    logs,
                    progress_callback,
                    stage="skipped",
                    checked=checked,
                    total=search_limit,
                    message=(
                        f"Skipped {candidate.title} at {candidate.company or 'unknown company'}: "
                        f"{candidate.closed_reason}"
                    ),
                )
                continue
            _report_progress(
                logs,
                progress_callback,
                stage="checking",
                checked=checked,
                total=search_limit,
                message=f"Checking availability: {candidate.title} at {candidate.company or 'unknown company'}",
            )
            try:
                job_page = fetch_availability(candidate.source_url)
            except Exception:
                _report_progress(
                    logs,
                    progress_callback,
                    stage="availability_unknown",
                    checked=checked,
                    total=search_limit,
                    message=_availability_unknown_message(candidate),
                )
            else:
                if _is_blocked_search_page(job_page):
                    _report_progress(
                        logs,
                        progress_callback,
                        stage="availability_unknown",
                        checked=checked,
                        total=search_limit,
                        message=_availability_unknown_message(candidate),
                    )
                else:
                    job_page_text = BeautifulSoup(job_page, "html.parser").get_text(" ", strip=True)
                    closed_reason = _closed_job_reason(job_page_text)
                    if closed_reason:
                        skipped += 1
                        _report_progress(
                            logs,
                            progress_callback,
                            stage="skipped",
                            checked=checked,
                            total=search_limit,
                            message=(
                                f"Skipped {candidate.title} at {candidate.company or 'unknown company'}: "
                                f"{closed_reason}"
                            ),
                        )
                        continue
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
                message = f"Added {candidate.title} at {candidate.company or 'unknown company'} ({result.score}/100)"
                stage = "added"
            else:
                duplicates += 1
                message = f"Duplicate skipped: {candidate.title} at {candidate.company or 'unknown company'}"
                stage = "duplicate"
            _report_progress(
                logs,
                progress_callback,
                stage=stage,
                checked=checked,
                total=search_limit,
                message=message,
            )
    _report_progress(
        logs,
        progress_callback,
        stage="complete",
        checked=checked,
        total=search_limit,
        message=f"Search complete: checked {checked} of {search_limit} possible jobs.",
    )
    return SearchRunSummary(
        checked=checked,
        added=added,
        duplicates=duplicates,
        skipped=skipped,
        logs=tuple(logs),
    )


def _report_progress(
    logs: list[str],
    callback: Callable[[SearchProgress], None] | None,
    *,
    stage: str,
    checked: int,
    total: int,
    message: str,
) -> None:
    logs.append(message)
    if callback is not None:
        callback(SearchProgress(stage=stage, checked=checked, total=total, message=message))


def fetch_public_html(url: str) -> str:
    import requests

    response = requests.get(
        url,
        headers={"User-Agent": "JobHunter/1.10 (+https://github.com/agustiarfalahi94/job-hunter)"},
        timeout=(5, 20),
    )
    response.raise_for_status()
    return response.text


def fetch_job_html(url: str) -> str:
    import requests

    response = requests.get(
        url,
        headers={"User-Agent": "JobHunter/1.10 (+https://github.com/agustiarfalahi94/job-hunter)"},
        timeout=(3, 8),
        allow_redirects=False,
    )
    if response.is_redirect:
        raise RuntimeError("Job page redirected")
    response.raise_for_status()
    return response.text


def _quoted_or(values: tuple[str, ...]) -> str:
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    if not cleaned:
        return ""
    return " OR ".join(f'"{value}"' for value in cleaned)


def _with_linkedin_date_filter(url: str, days: int | None) -> str:
    if days is None:
        return url
    return f"{url}&f_TPR=r{max(1, days) * 86400}"


def _result_limit(requested: int) -> int:
    return max(0, min(50, requested))


def _google_date_filter(days: int | None) -> str:
    return {1: "qdr:d", 7: "qdr:w", 30: "qdr:m"}.get(days, "")


def _duckduckgo_date_filter(days: int | None) -> str:
    return {1: "d", 7: "w", 30: "m"}.get(days, "")


def _closed_job_reason(text: str) -> str:
    normalized = text.casefold()
    for marker in CLOSED_JOB_MARKERS:
        if marker in normalized:
            return marker.capitalize()
    return ""


def _availability_unknown_message(candidate: SearchCandidate) -> str:
    return (
        f"Availability could not be confirmed: {candidate.title} at "
        f"{candidate.company or 'unknown company'}"
    )


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
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").casefold()
    allowed_domains = PLATFORM_DOMAINS.get(platform, ())
    if parsed.scheme != "https" or not hostname:
        return False
    trusted_domain = any(
        hostname == domain or hostname.endswith(f".{domain}") for domain in allowed_domains
    )
    if allowed_domains and not trusted_domain:
        return False
    normalized_url = url.casefold()
    normalized_title = title.casefold()
    if any(term in normalized_title or term in normalized_url for term in NOISE_TERMS):
        return False
    hints = PLATFORM_JOB_PATH_HINTS.get(platform, ())
    if not hints:
        return True
    return any(hint in normalized_url for hint in hints)
