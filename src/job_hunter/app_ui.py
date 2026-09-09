"""Helpers for the Streamlit dashboard."""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from job_hunter.queue import JobRecord
from job_hunter.search import SearchRunSummary


STATUSES = ("new", "reviewing", "drafted", "submitted", "rejected")


def jobs_to_rows(jobs: Iterable[JobRecord]) -> list[dict[str, object]]:
    return [
        {
            "ID": job.id,
            "Score": job.score,
            "Decision": job.decision,
            "Status": job.status,
            "Title": job.title,
            "Company": job.company,
            "Location": job.location,
            "Source URL": job.source_url,
            "Reasons": job.reasons,
            "Remarks": job.remarks,
        }
        for job in jobs
    ]


def filter_jobs(jobs: Iterable[JobRecord], decision: str, status: str) -> list[JobRecord]:
    filtered = list(jobs)
    if decision != "all":
        filtered = [job for job in filtered if job.decision == decision]
    if status != "all":
        filtered = [job for job in filtered if job.status == status]
    return filtered


def status_counts(jobs: Iterable[JobRecord]) -> dict[str, int]:
    counts = Counter(job.status for job in jobs)
    return {status: counts.get(status, 0) for status in STATUSES}


def search_summary_to_rows(summary: SearchRunSummary) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {"Metric": "Checked", "Value": summary.checked, "Detail": "Search results scored"},
        {"Metric": "Added", "Value": summary.added, "Detail": "New jobs inserted into the queue"},
        {"Metric": "Duplicates", "Value": summary.duplicates, "Detail": "Exact duplicate jobs skipped"},
        {"Metric": "Skipped", "Value": summary.skipped, "Detail": "Platform queries that could not be read"},
    ]
    rows.extend({"Metric": "Log", "Value": "", "Detail": log} for log in summary.logs)
    return rows
