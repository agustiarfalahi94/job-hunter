"""Truthful application draft generation."""

from __future__ import annotations

from dataclasses import dataclass

from job_hunter.profile import CANDIDATE_PROFILE
from job_hunter.queue_types import JobInput


UNSUPPORTED_REQUIREMENTS: tuple[tuple[str, str], ...] = (
    ("kubernetes", "Job mentions Kubernetes, which is not supported by the public profile."),
    (
        "dedicated linux",
        "Job mentions dedicated Linux administration, which is not supported by the public profile.",
    ),
    (
        "linux system administration",
        "Job mentions dedicated Linux administration, which is not supported by the public profile.",
    ),
    ("terraform", "Job mentions Terraform, which is not supported by the public profile."),
    ("aws", "Job mentions AWS, which is not supported by the public profile."),
)


@dataclass(frozen=True)
class ApplicationDraft:
    cover_letter: str
    short_answer: str
    warnings: tuple[str, ...]


def build_application_draft(job: JobInput) -> ApplicationDraft:
    warnings = unsupported_claim_warnings(job.description)
    company = job.company or "your team"
    title = job.title or "this role"
    evidence = _select_evidence(job.description)

    cover_letter = (
        f"# Application Draft - {title}\n\n"
        f"Hi {company} team,\n\n"
        f"I am interested in the {title} role because it lines up with my data engineering "
        "and BI reporting background. My strongest fit is in SQL-heavy data work, migration "
        "projects, reporting reliability, and stakeholder-facing delivery.\n\n"
        f"Relevant evidence from my experience includes {evidence[0]}, {evidence[1]}, and "
        f"{evidence[2]}. I would bring a careful validation mindset to this role, especially "
        "where data correctness, refresh reliability, and clear reporting matter.\n\n"
        "Best,\n"
        "Agustiar\n"
    )
    short_answer = (
        f"My background fits the {title} role through hands-on SQL, Python, reporting, "
        f"and migration work. Examples I can discuss include {evidence[0]} and {evidence[1]}."
    )
    return ApplicationDraft(cover_letter=cover_letter, short_answer=short_answer, warnings=warnings)


def unsupported_claim_warnings(text: str) -> tuple[str, ...]:
    normalized = text.casefold()
    warnings: list[str] = []
    for keyword, warning in UNSUPPORTED_REQUIREMENTS:
        if keyword in normalized and warning not in warnings:
            warnings.append(warning)
    return tuple(warnings)


def draft_to_markdown(draft: ApplicationDraft) -> str:
    warning_block = "None"
    if draft.warnings:
        warning_block = "\n".join(f"- {warning}" for warning in draft.warnings)
    return (
        f"{draft.cover_letter}\n"
        "## Short Form Answer\n\n"
        f"{draft.short_answer}\n\n"
        "## Warnings\n\n"
        f"{warning_block}\n"
    )


def _select_evidence(description: str) -> tuple[str, str, str]:
    normalized = description.casefold()
    strengths = CANDIDATE_PROFILE.strengths
    ranked = sorted(
        strengths,
        key=lambda strength: _overlap_score(normalized, strength),
        reverse=True,
    )
    return tuple(ranked[:3])  # type: ignore[return-value]


def _overlap_score(description: str, strength: str) -> int:
    return sum(1 for word in strength.casefold().replace("/", " ").split() if word in description)
