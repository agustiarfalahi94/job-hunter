"""Public web-result job search and queue ingestion."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import Callable
import ipaddress
import json
import re
import socket
from urllib.parse import parse_qs, quote_plus, unquote, urlencode, urljoin, urlparse

from bs4 import BeautifulSoup

from job_hunter.application_links import KNOWN_ATS_DOMAINS, is_safe_application_url
from job_hunter.descriptions import JobDescription, extract_job_description
from job_hunter.eligibility import hard_skip_matches
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
MAX_SEARCH_REQUESTS = 12


@dataclass(frozen=True)
class SearchCriteria:
    title_terms: tuple[str, ...]
    description_terms: tuple[str, ...]
    location: str
    platforms: tuple[str, ...]
    max_results: int = 50
    posted_within_days: int | None = 30
    custom_domains: tuple[str, ...] = ()
    custom_site_filters: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlatformQuery:
    platform: str
    query: str
    url: str
    parser: str = "duckduckgo"
    signal: str = "combined"


@dataclass(frozen=True)
class SearchCandidate:
    title: str
    company: str
    location: str
    description: str
    source_url: str
    platform: str
    closed_reason: str = ""
    posted_date: str = ""
    apply_url: str = ""


@dataclass(frozen=True)
class JobPageMetadata:
    posted_date: str = ""
    apply_url: str = ""
    posted_date_verified: bool = False
    posted_date_source: str = ""
    posted_date_reason: str = ""
    description: JobDescription = JobDescription(
        text="",
        kind="unavailable",
        source="",
        limitation="No readable job description was available.",
    )


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
    location_part = f'"{criteria.location}"' if criteria.location else ""
    sources: list[tuple[str, str]] = []
    for platform in criteria.platforms:
        site_filter = PLATFORM_SITE_FILTERS.get(platform)
        if not site_filter:
            continue
        sources.append((platform, site_filter))
    sources.extend(
        (domain, criteria.custom_site_filters[index] if index < len(criteria.custom_site_filters) else f"site:{domain}")
        for index, domain in enumerate(criteria.custom_domains)
    )
    return _bounded_signal_queries(
        criteria,
        sources,
        location_part,
        parser="duckduckgo",
    )


def _bounded_signal_queries(
    criteria: SearchCriteria,
    sources: list[tuple[str, str]],
    location_part: str,
    *,
    parser: str,
) -> list[PlatformQuery]:
    first_pass: list[PlatformQuery] = []
    second_pass: list[PlatformQuery] = []
    signals = (
        ("title", _quoted_or(criteria.title_terms)),
        ("description", _quoted_or(criteria.description_terms)),
    )
    for signal_index, (signal, terms) in enumerate(signals):
        if not terms:
            continue
        destination = first_pass if signal_index == 0 else second_pass
        for platform, site_filter in sources:
            query = " ".join(
                part for part in (site_filter, terms, location_part) if part
            )
            url = DUCKDUCKGO_HTML_URL.format(query=quote_plus(query))
            date_filter = _duckduckgo_date_filter(criteria.posted_within_days)
            if date_filter:
                url = f"{url}&df={date_filter}"
            destination.append(
                PlatformQuery(
                    platform=platform,
                    query=query,
                    url=url,
                    parser=parser,
                    signal=signal,
                )
            )
    return (first_pass + second_pass)[:MAX_SEARCH_REQUESTS]


def build_direct_platform_queries(criteria: SearchCriteria) -> list[PlatformQuery]:
    queries = []
    if "LinkedIn" not in criteria.platforms:
        return queries
    for signal, terms in (
        ("title", criteria.title_terms),
        ("description", criteria.description_terms),
    ):
        keywords = " ".join(terms).strip()
        if not keywords:
            continue
        query = f"{keywords} {criteria.location}".strip()
        queries.append(
            PlatformQuery(
                platform="LinkedIn",
                query=query,
                url=_with_linkedin_date_filter(
                    LINKEDIN_SEARCH_URL.format(
                        keywords=quote_plus(keywords),
                        location=quote_plus(criteria.location),
                    ),
                    criteria.posted_within_days,
                ),
                parser="linkedin",
                signal=signal,
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
                signal=platform_query.signal,
            )
        )
    return queries[:MAX_SEARCH_REQUESTS]


def parse_serpapi_results(payload: str, platform: str, location: str, limit: int) -> list[SearchCandidate]:
    data = json.loads(payload or "{}")
    candidates: list[SearchCandidate] = []
    for item in data.get("organic_results", []):
        if len(candidates) >= limit:
            break
        title_text = str(item.get("title", "")).strip()
        href = str(item.get("link", "")).strip()
        snippet = str(item.get("snippet", "")).strip()
        posted_date = normalize_posted_date(_find_provider_posted_value(item))
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
                posted_date=posted_date,
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
        date_node = card.select_one("time.job-search-card__listdate, time")
        if link is None or title_node is None:
            continue
        source_url = str(link.get("href", "")).strip()
        title = title_node.get_text(" ", strip=True)
        company = company_node.get_text(" ", strip=True) if company_node else ""
        card_location = location_node.get_text(" ", strip=True) if location_node else location
        posted_value = ""
        if date_node is not None:
            posted_value = str(date_node.get("datetime", "")).strip() or date_node.get_text(
                " ", strip=True
            )
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
                posted_date=normalize_posted_date(posted_value),
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
                posted_date=_date_from_text(" ".join((title_text, snippet))),
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
            eligibility_reason = _eligibility_skip_reason(
                candidate, preferences.get("hard_skip_keywords", ())
            )
            if eligibility_reason:
                skipped += 1
                _report_progress(
                    logs,
                    progress_callback,
                    stage="skipped",
                    checked=checked,
                    total=search_limit,
                    message=(
                        f"Skipped {candidate.title} at {candidate.company or 'unknown company'}: "
                        f"{eligibility_reason}"
                    ),
                )
                continue
            if _posting_is_too_old(candidate.posted_date, criteria.posted_within_days):
                skipped += 1
                _report_progress(
                    logs,
                    progress_callback,
                    stage="skipped",
                    checked=checked,
                    total=search_limit,
                    message=(
                        f"Skipped {candidate.title} at {candidate.company or 'unknown company'}: "
                        f"posted {candidate.posted_date}, older than "
                        f"{criteria.posted_within_days} days"
                    ),
                )
                continue
            description = JobDescription(
                text=candidate.description,
                kind="snippet" if candidate.description else "unavailable",
                source="search result" if candidate.description else "",
                limitation=(
                    "Full job description was unavailable; score uses a search snippet."
                    if candidate.description
                    else "No readable job description was available."
                ),
            )
            posted_date_verified = bool(candidate.posted_date)
            posted_date_source = "search provider" if candidate.posted_date else ""
            posted_date_reason = "" if candidate.posted_date else "Job page was not checked"
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
                posted_date_reason = (
                    "" if candidate.posted_date else "Job page could not be loaded"
                )
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
                    posted_date_reason = (
                        "" if candidate.posted_date else "Job page was blocked"
                    )
                    _report_progress(
                        logs,
                        progress_callback,
                        stage="availability_unknown",
                        checked=checked,
                        total=search_limit,
                        message=_availability_unknown_message(candidate),
                    )
                else:
                    metadata = extract_job_metadata(
                        job_page,
                        candidate.source_url,
                        snippet=candidate.description,
                    )
                    candidate = replace(
                        candidate,
                        posted_date=metadata.posted_date or candidate.posted_date,
                        apply_url=metadata.apply_url or candidate.apply_url,
                        description=metadata.description.text or candidate.description,
                    )
                    description = metadata.description
                    if metadata.posted_date:
                        posted_date_verified = metadata.posted_date_verified
                        posted_date_source = metadata.posted_date_source
                        posted_date_reason = metadata.posted_date_reason
                    elif not candidate.posted_date:
                        posted_date_verified = False
                        posted_date_source = ""
                        posted_date_reason = metadata.posted_date_reason
                    job_page_text = BeautifulSoup(job_page, "html.parser").get_text(" ", strip=True)
                    eligibility_reason = _eligibility_skip_reason(
                        candidate,
                        preferences.get("hard_skip_keywords", ()),
                        page_text=job_page_text,
                    )
                    if eligibility_reason:
                        skipped += 1
                        _report_progress(
                            logs,
                            progress_callback,
                            stage="skipped",
                            checked=checked,
                            total=search_limit,
                            message=(
                                f"Skipped {candidate.title} at "
                                f"{candidate.company or 'unknown company'}: "
                                f"{eligibility_reason}"
                            ),
                        )
                        continue
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
                    if not candidate.posted_date:
                        _report_progress(
                            logs,
                            progress_callback,
                            stage="date_unknown",
                            checked=checked,
                            total=search_limit,
                            message=(
                                f"Posting date unavailable: {candidate.title} at "
                                f"{candidate.company or 'unknown company'} did not expose "
                                "a readable date."
                            ),
                        )
                    if _posting_is_too_old(
                        candidate.posted_date, criteria.posted_within_days
                    ):
                        skipped += 1
                        _report_progress(
                            logs,
                            progress_callback,
                            stage="skipped",
                            checked=checked,
                            total=search_limit,
                            message=(
                                f"Skipped {candidate.title} at "
                                f"{candidate.company or 'unknown company'}: "
                                f"posted {candidate.posted_date}, older than "
                                f"{criteria.posted_within_days} days"
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
                    posted_date=candidate.posted_date,
                    apply_url=candidate.apply_url,
                    description_kind=description.kind,
                    description_source=description.source,
                    description_limitation=description.limitation,
                    posted_date_verified=posted_date_verified,
                    posted_date_source=posted_date_source,
                    posted_date_reason=posted_date_reason,
                    platform=candidate.platform,
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
        headers={"User-Agent": "JobHunter/1.14 (+https://github.com/agustiarfalahi94/job-hunter)"},
        timeout=(5, 20),
    )
    response.raise_for_status()
    return response.text


def fetch_job_html(url: str, allowed_domains: tuple[str, ...] = ()) -> str:
    import requests

    if not _is_trusted_job_url(url, allowed_domains):
        raise RuntimeError("Job page URL is not trusted")
    current_url = url
    for redirect_count in range(4):
        response = requests.get(
            current_url,
            headers={"User-Agent": "JobHunter/1.14 (+https://github.com/agustiarfalahi94/job-hunter)"},
            timeout=(3, 8),
            allow_redirects=False,
        )
        if not response.is_redirect:
            response.raise_for_status()
            return response.text
        if redirect_count == 3:
            raise RuntimeError("Job page redirected too many times")
        next_url = urljoin(current_url, response.headers.get("Location", ""))
        if not _is_trusted_job_url(next_url, allowed_domains):
            raise RuntimeError("Job page redirected to an untrusted destination")
        current_url = next_url
    raise RuntimeError("Job page could not be loaded")


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


def normalize_posted_date(value: str, today: date | None = None) -> str:
    normalized = " ".join(str(value).strip().split())
    if not normalized:
        return ""
    reference_date = today or date.today()
    iso_candidate = normalized[:10]
    try:
        return date.fromisoformat(iso_candidate).isoformat()
    except ValueError:
        pass

    for date_format in ("%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(normalized, date_format).date().isoformat()
        except ValueError:
            continue

    lowered = normalized.casefold()
    if lowered == "today":
        return reference_date.isoformat()
    if lowered == "yesterday":
        return (reference_date - timedelta(days=1)).isoformat()

    relative = re.fullmatch(
        r"(?:about\s+)?(\d+)\+?\s+(hour|day|week|month|year)s?\s+ago", lowered
    )
    if relative is None:
        return ""
    amount = int(relative.group(1))
    unit = relative.group(2)
    days = {
        "hour": 0,
        "day": amount,
        "week": amount * 7,
        "month": amount * 30,
        "year": amount * 365,
    }[unit]
    return (reference_date - timedelta(days=days)).isoformat()


def extract_job_metadata(
    html: str,
    source_url: str,
    today: date | None = None,
    snippet: str = "",
) -> JobPageMetadata:
    soup = BeautifulSoup(html, "html.parser")
    posted_date = ""
    posted_date_source = ""
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or script.get_text() or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        date_posted = _find_date_posted(payload)
        if date_posted:
            posted_date = normalize_posted_date(date_posted, today=today)
            if posted_date:
                posted_date_source = "JobPosting.datePosted"
                break

    if not posted_date:
        posted_date = _date_from_meta(soup, today=today)
        if posted_date:
            posted_date_source = "datePosted metadata"

    if not posted_date:
        posted_date = _date_from_job_page_nodes(soup, today=today)
        if posted_date:
            posted_date_source = "job page element"

    if not posted_date:
        posted_date = normalize_posted_date(
            _find_embedded_posted_value(soup), today=today
        )
        if posted_date:
            posted_date_source = "embedded job posting data"

    if not posted_date:
        posted_date = _labeled_date_from_text(
            soup.get_text(" ", strip=True), today=today
        )
        if posted_date:
            posted_date_source = "labelled job page text"

    apply_url = ""
    for link in soup.find_all("a", href=True):
        label = " ".join(
            (
                link.get_text(" ", strip=True),
                str(link.get("aria-label", "")),
                str(link.get("title", "")),
            )
        ).casefold()
        if "apply" not in label:
            continue
        candidate_url = urljoin(source_url, str(link.get("href", "")).strip())
        if is_safe_application_url(candidate_url, source_url):
            apply_url = candidate_url
            break
    return JobPageMetadata(
        posted_date=posted_date,
        apply_url=apply_url,
        posted_date_verified=bool(posted_date),
        posted_date_source=posted_date_source,
        posted_date_reason="" if posted_date else "No job-specific posting date found",
        description=extract_job_description(html, snippet=snippet),
    )


def _find_date_posted(value: object) -> str:
    if isinstance(value, dict):
        item_type = value.get("@type")
        item_types = item_type if isinstance(item_type, list) else [item_type]
        if any(str(candidate).casefold() == "jobposting" for candidate in item_types):
            raw_date = value.get("datePosted")
            if isinstance(raw_date, str) and raw_date.strip():
                return raw_date.strip()
        for child in value.values():
            found = _find_date_posted(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_date_posted(child)
            if found:
                return found
    return ""


def _find_provider_posted_value(value: object, allow_generic_date: bool = True) -> str:
    known_keys = ("datePosted", "date_posted", "posted_at")
    if isinstance(value, dict):
        keys = ("date",) + known_keys if allow_generic_date else known_keys
        for key in keys:
            raw_value = value.get(key)
            if isinstance(raw_value, str) and raw_value.strip():
                return raw_value.strip()
        for child in value.values():
            found = _find_provider_posted_value(child, allow_generic_date=False)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_provider_posted_value(child, allow_generic_date=False)
            if found:
                return found
    return ""


def _date_from_meta(soup: BeautifulSoup, today: date | None = None) -> str:
    for node in soup.find_all("meta"):
        labels = " ".join(
            str(node.get(attribute, ""))
            for attribute in ("itemprop", "property", "name")
        )
        normalized_labels = re.sub(r"[^a-z0-9]+", "", labels.casefold())
        if "dateposted" not in normalized_labels:
            continue
        value = str(node.get("content", "")).strip()
        posted_date = normalize_posted_date(value, today=today)
        if posted_date:
            return posted_date
    return ""


def _date_from_job_page_nodes(soup: BeautifulSoup, today: date | None = None) -> str:
    for node in soup.find_all(True):
        attributes = " ".join(
            (
                " ".join(str(item) for item in node.get("class", ())),
                str(node.get("id", "")),
                str(node.get("data-test", "")),
                str(node.get("data-testid", "")),
                str(node.get("itemprop", "")),
            )
        ).casefold()
        if node.name != "time" and not any(
            marker in attributes
            for marker in (
                "posted-time",
                "posted-date",
                "posting-date",
                "date-posted",
                "dateposted",
            )
        ):
            continue
        value = (
            str(node.get("datetime", "")).strip()
            or str(node.get("content", "")).strip()
            or node.get_text(" ", strip=True)
        )
        posted_date = _date_from_text(value, today=today)
        if posted_date:
            return posted_date
    return ""


def _find_embedded_posted_value(soup: BeautifulSoup) -> str:
    pattern = re.compile(
        r'["\'](?:datePosted|date_posted|postedAt|posted_at)["\']\s*:\s*["\']([^"\']+)["\']',
        flags=re.IGNORECASE,
    )
    for script in soup.find_all("script"):
        match = pattern.search(script.string or script.get_text() or "")
        if match:
            return match.group(1).strip()
    return ""


def _labeled_date_from_text(text: str, today: date | None = None) -> str:
    label = re.compile(
        r"\b(?:date\s+posted|posted|listed|published)\s*(?:on\s+|:\s*|-\s*)?",
        flags=re.IGNORECASE,
    )
    for match in label.finditer(text):
        posted_date = _date_from_text(text[match.end() : match.end() + 80], today=today)
        if posted_date:
            return posted_date
    return ""


def _date_from_text(text: str, today: date | None = None) -> str:
    relative = re.search(
        r"\b(?:today|yesterday|(?:about\s+)?\d+\+?\s+(?:hour|day|week|month|year)s?\s+ago)\b",
        text,
        flags=re.IGNORECASE,
    )
    if relative:
        return normalize_posted_date(relative.group(0), today=today)
    iso_date = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
    return normalize_posted_date(iso_date.group(0), today=today) if iso_date else ""


def _posting_is_too_old(posted_date: str, days: int | None) -> bool:
    if not posted_date or days is None:
        return False
    try:
        parsed_date = date.fromisoformat(posted_date)
    except ValueError:
        return False
    return parsed_date < date.today() - timedelta(days=max(1, days))


def _availability_unknown_message(candidate: SearchCandidate) -> str:
    return (
        f"Availability could not be confirmed: {candidate.title} at "
        f"{candidate.company or 'unknown company'}"
    )


def _eligibility_skip_reason(
    candidate: SearchCandidate, keywords: object, page_text: str = ""
) -> str:
    text = " ".join(
        (candidate.title, candidate.description, candidate.location, page_text)
    )
    matches = hard_skip_matches(text, keywords)
    if not matches:
        return ""
    return f"Hard skip keyword found: {', '.join(matches)}"


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
    if not allowed_domains and "." in platform and " " not in platform:
        allowed_domains = (platform.casefold(),)
    if parsed.scheme != "https" or not hostname:
        return False
    try:
        if parsed.port not in {None, 443}:
            return False
    except ValueError:
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


def _is_trusted_job_url(url: str, allowed_domains: tuple[str, ...] = ()) -> bool:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or not hostname:
        return False
    try:
        if parsed.port not in {None, 443}:
            return False
    except ValueError:
        return False
    trusted_domains = {
        domain
        for domains in PLATFORM_DOMAINS.values()
        for domain in domains
    }
    trusted_domains.update(KNOWN_ATS_DOMAINS)
    if any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in trusted_domains
    ):
        return True
    custom_domains = tuple(domain.casefold().strip() for domain in allowed_domains)
    custom_match = any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in custom_domains
    )
    return custom_match and _hostname_resolves_public(hostname)


def _hostname_resolves_public(hostname: str) -> bool:
    try:
        addresses = {
            result[4][0]
            for result in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
        }
        return bool(addresses) and all(
            ipaddress.ip_address(address).is_global for address in addresses
        )
    except (OSError, ValueError):
        return False
