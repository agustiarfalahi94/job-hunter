"""Dry-run application packets for human-reviewed submissions."""

from __future__ import annotations

from dataclasses import dataclass

from job_hunter.drafts import build_application_draft, draft_to_markdown
from job_hunter.queue_types import JobInput


@dataclass(frozen=True)
class ApplicationPacket:
    mode: str
    submit_allowed: bool
    review_notes: tuple[str, ...]
    warnings: tuple[str, ...]
    markdown: str


def build_application_packet(job: JobInput, require_human_review: bool = True) -> ApplicationPacket:
    draft = build_application_draft(job)
    review_notes = ["Human review required before submission."] if require_human_review else []
    if draft.warnings:
        review_notes.append("Resolve unsupported-claim warnings before using this draft.")

    submit_allowed = not require_human_review and not draft.warnings
    markdown = _packet_markdown(job, draft_to_markdown(draft), review_notes, draft.warnings, submit_allowed)
    return ApplicationPacket(
        mode="dry-run",
        submit_allowed=submit_allowed,
        review_notes=tuple(review_notes),
        warnings=draft.warnings,
        markdown=markdown,
    )


def _packet_markdown(
    job: JobInput,
    draft_markdown: str,
    review_notes: list[str],
    warnings: tuple[str, ...],
    submit_allowed: bool,
) -> str:
    notes = "\n".join(f"- {note}" for note in review_notes) or "None"
    warning_text = "\n".join(f"- {warning}" for warning in warnings) or "None"
    submit_text = "yes" if submit_allowed else "no"
    return (
        f"# Application Packet - {job.title}\n\n"
        "## Job\n\n"
        f"- Company: {job.company or 'Unknown'}\n"
        f"- Location: {job.location or 'Unknown'}\n"
        f"- Source URL: {job.source_url or 'Not provided'}\n"
        f"- Submit allowed: {submit_text}\n"
        "- Mode: dry-run\n\n"
        "## Review Notes\n\n"
        f"{notes}\n\n"
        "## Warnings\n\n"
        f"{warning_text}\n\n"
        "## Draft\n\n"
        f"{draft_markdown}"
    )
