"""Daily workflow reporting."""

from __future__ import annotations

from dataclasses import dataclass

from job_hunter.queue import JobQueue


@dataclass(frozen=True)
class DailySummary:
    daily_target: int
    submitted_today: int
    remaining_today: int
    total_queued: int
    by_status: dict[str, int]
    next_action: str


def daily_summary(queue: JobQueue, daily_target: int) -> DailySummary:
    jobs = queue.list_jobs()
    by_status: dict[str, int] = {}
    for job in jobs:
        by_status[job.status] = by_status.get(job.status, 0) + 1

    submitted_today = by_status.get("submitted", 0)
    remaining_today = max(0, daily_target - submitted_today)
    shortlist_count = sum(1 for job in jobs if job.status == "new" and job.decision == "shortlist")
    review_count = sum(1 for job in jobs if job.status == "new" and job.decision == "review")

    return DailySummary(
        daily_target=daily_target,
        submitted_today=submitted_today,
        remaining_today=remaining_today,
        total_queued=len(jobs),
        by_status=by_status,
        next_action=_next_action(shortlist_count, review_count, remaining_today),
    )


def summary_to_text(summary: DailySummary) -> str:
    status_lines = "\n".join(
        f"- {status}: {count}" for status, count in sorted(summary.by_status.items())
    )
    if not status_lines:
        status_lines = "- none: 0"
    return (
        f"Daily target: {summary.daily_target}\n"
        f"Submitted today: {summary.submitted_today}\n"
        f"Remaining today: {summary.remaining_today}\n"
        f"Total queued: {summary.total_queued}\n"
        "By status:\n"
        f"{status_lines}\n"
        f"Next action: {summary.next_action}\n"
    )


def _next_action(shortlist_count: int, review_count: int, remaining_today: int) -> str:
    if remaining_today == 0:
        return "Daily target reached. Review quality before adding more volume."
    if shortlist_count:
        noun = "job" if shortlist_count == 1 else "jobs"
        return f"Review {shortlist_count} shortlisted {noun} and export application packets."
    if review_count:
        noun = "job" if review_count == 1 else "jobs"
        return f"Review {review_count} borderline {noun} before drafting."
    return "Import or add more jobs, then score the queue."
