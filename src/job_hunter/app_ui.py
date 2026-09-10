"""Helpers for the Streamlit dashboard."""

from __future__ import annotations

from collections import Counter
from typing import Iterable
from urllib.parse import urlparse

from job_hunter.queue import JobRecord
from job_hunter.search import SearchRunSummary


STATUSES = ("new", "reviewing", "drafted", "submitted", "rejected")
DEFAULT_STRONG_TARGET = 20
DEFAULT_SESSION_CAP = 50


def jobs_to_rows(jobs: Iterable[JobRecord]) -> list[dict[str, object]]:
    return [
        {
            "ID": job.id,
            "Score": job.score,
            "Decision": job.decision,
            "Posted": job.posted_date or "Unknown",
            "Title": job.title,
            "Company": job.company,
            "Location": job.location,
            "Description": job.description,
            "Source URL": job.source_url,
            "Reasons": job.reasons,
            "Remarks": job.remarks,
        }
        for job in jobs
    ]


def filter_jobs(
    jobs: Iterable[JobRecord], decision: str, status: str = "all"
) -> list[JobRecord]:
    filtered = list(jobs)
    if decision != "all":
        filtered = [job for job in filtered if job.decision == decision]
    if status != "all":
        filtered = [job for job in filtered if job.status == status]
    return filtered


def application_destination(job: JobRecord) -> str:
    for url in (job.apply_url, job.source_url):
        parsed = urlparse(url)
        if parsed.scheme == "https" and parsed.hostname:
            return url
    return ""


def status_counts(jobs: Iterable[JobRecord]) -> dict[str, int]:
    counts = Counter(job.status for job in jobs)
    return {status: counts.get(status, 0) for status in STATUSES}


def search_summary_to_rows(summary: SearchRunSummary) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {"Metric": "Checked", "Value": summary.checked, "Detail": "Search results scored"},
        {"Metric": "Added", "Value": summary.added, "Detail": "New jobs inserted into the queue"},
        {"Metric": "Duplicates", "Value": summary.duplicates, "Detail": "Exact duplicate jobs skipped"},
        {
            "Metric": "Skipped",
            "Value": summary.skipped,
            "Detail": "Closed jobs or unreadable search results skipped",
        },
    ]
    rows.extend({"Metric": "Log", "Value": None, "Detail": log} for log in summary.logs)
    return rows


def provider_status_label(has_api_search: bool) -> str:
    return "API search enabled" if has_api_search else "Free public search fallback"


def editable_criteria_defaults(preferences: dict[str, object]) -> dict[str, object]:
    daily_targets = preferences.get("daily_targets", {})
    if not isinstance(daily_targets, dict):
        daily_targets = {}
    return {
        "target_roles": _string_list(preferences.get("target_roles")),
        "primary_keywords": _string_list(preferences.get("primary_keywords")),
        "bonus_keywords": _string_list(preferences.get("bonus_keywords")),
        "hard_skip_keywords": _string_list(preferences.get("hard_skip_keywords")),
        "strong_target": int(daily_targets.get("strong_matches", DEFAULT_STRONG_TARGET)),
        "session_cap": int(daily_targets.get("suitable_matches", DEFAULT_SESSION_CAP)),
    }


def queue_column_widths() -> dict[str, str]:
    return {
        "Title": "large",
        "Company": "medium",
        "Location": "medium",
        "Posted": "medium",
        "Reasons": "large",
        "Remarks": "large",
        "Description": "large",
        "Source URL": "medium",
    }


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]
