"""Session-isolated private state for the hosted Streamlit app."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, MutableMapping

from job_hunter.job_identity import JobSource, job_source, vacancy_fingerprint
from job_hunter.matching import MatchResult
from job_hunter.queue import AddResult, JobRecord
from job_hunter.queue_types import JobInput
from job_hunter.scoring import ScoreResult, score_job


WORKSPACE_KEY = "job_hunter_workspace"


@dataclass(frozen=True)
class SessionCV:
    filename: str
    content: bytes
    text: str

    @property
    def size_bytes(self) -> int:
        return len(self.content)


class SessionWorkspace:
    """Owns data that must not be shared between public app sessions."""

    def __init__(self) -> None:
        self.cv: SessionCV | None = None
        self.score_cache: dict[str, object] = {}
        self._jobs: list[JobRecord] = []
        self._next_job_id = 1

    @property
    def cv_text(self) -> str:
        return self.cv.text if self.cv is not None else ""

    def save_cv(self, filename: str, content: bytes, text: str) -> None:
        cleaned_text = text.strip()
        if not content:
            raise ValueError("CV file is empty.")
        if not cleaned_text:
            raise ValueError("No readable CV text was found.")
        self.cv = SessionCV(filename=filename, content=bytes(content), text=cleaned_text)
        self._clear_cv_cache()

    def remove_cv(self) -> None:
        self.cv = None
        self._clear_cv_cache()

    def add_job(self, job: JobInput, preferences: dict[str, Any]) -> AddResult:
        return self.add_scored_job(
            job,
            score_job(
                {
                    "title": job.title,
                    "description": job.description,
                    "location": job.location,
                },
                preferences,
            ),
        )

    def add_scored_job(
        self, job: JobInput, score: ScoreResult | MatchResult
    ) -> AddResult:
        existing = self._find_duplicate(job)
        if existing is not None:
            self._merge_duplicate(existing.id, job)
            return AddResult(
                job_id=existing.id,
                created=False,
                score=existing.score,
                decision=existing.decision,
            )
        source = job_source(job.platform, job.source_url)
        record = JobRecord(
            id=self._next_job_id,
            title=job.title.strip(),
            company=job.company.strip(),
            location=job.location.strip(),
            description=job.description.strip(),
            source_url=job.source_url.strip(),
            score=score.score,
            decision=score.decision,
            status="new",
            reasons="\n".join(score.reasons),
            remarks="\n".join(score.remarks),
            posted_date=job.posted_date.strip(),
            apply_url=job.apply_url.strip(),
            sources=(source,) if source.original_url else (),
            description_kind=job.description_kind,
            description_source=job.description_source,
            description_limitation=job.description_limitation,
            posted_date_verified=job.posted_date_verified,
            posted_date_source=job.posted_date_source,
            posted_date_reason=job.posted_date_reason,
            scoring_engine=getattr(score, "engine", "Deterministic"),
            scoring_model=getattr(score, "model", ""),
            score_limited=bool(getattr(score, "limited", False)),
            cache_hit=bool(getattr(score, "cache_hit", False)),
        )
        self._jobs.append(record)
        self._next_job_id += 1
        return AddResult(record.id, created=True, score=record.score, decision=record.decision)

    def list_jobs(self, status: str | None = None) -> list[JobRecord]:
        jobs = self._jobs
        if status is not None:
            jobs = [job for job in jobs if job.status == status]
        return sorted(jobs, key=lambda job: (job.score, job.id), reverse=True)

    def update_application_status(self, job_id: int, application_status: str | bool) -> None:
        normalized = (
            "applied" if application_status is True else "not_applied"
            if application_status is False
            else str(application_status)
        )
        if normalized not in {"applied", "not_applied"}:
            raise ValueError(f"Unsupported application status: {normalized}")
        for index, job in enumerate(self._jobs):
            if job.id == job_id:
                if normalized == "applied":
                    recorded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    evidence = (
                        "Marked manually by the user; not verified with the job platform."
                    )
                else:
                    recorded_at = ""
                    evidence = ""
                self._jobs[index] = replace(
                    job,
                    application_status=normalized,
                    application_recorded_at=recorded_at,
                    application_evidence=evidence,
                )
                return
        raise ValueError(f"Job not found: {job_id}")

    def _find_duplicate(self, job: JobInput) -> JobRecord | None:
        candidate_source = job_source(job.platform, job.source_url)
        fingerprint = vacancy_fingerprint(job.title, job.company, job.location)
        for existing in self._jobs:
            existing_sources = existing.sources or _legacy_sources(existing)
            if candidate_source.stable_id and any(
                source.platform.casefold() == candidate_source.platform.casefold()
                and source.stable_id == candidate_source.stable_id
                for source in existing_sources
            ):
                return existing
            if candidate_source.canonical_url and any(
                source.canonical_url == candidate_source.canonical_url
                for source in existing_sources
            ):
                return existing
            if fingerprint and fingerprint == vacancy_fingerprint(
                existing.title, existing.company, existing.location
            ):
                return existing
        return None

    def _merge_duplicate(self, job_id: int, incoming: JobInput) -> None:
        incoming_source = job_source(incoming.platform, incoming.source_url)
        for index, existing in enumerate(self._jobs):
            if existing.id != job_id:
                continue
            sources = list(existing.sources or _legacy_sources(existing))
            if incoming_source.original_url and not any(
                source.canonical_url == incoming_source.canonical_url
                and source.platform.casefold() == incoming_source.platform.casefold()
                for source in sources
            ):
                sources.append(incoming_source)
            use_incoming_description = (
                incoming.description_kind == "full"
                and existing.description_kind != "full"
            )
            self._jobs[index] = replace(
                existing,
                sources=tuple(sources),
                description=(
                    incoming.description if use_incoming_description else existing.description
                ),
                description_kind=(
                    incoming.description_kind
                    if use_incoming_description
                    else existing.description_kind
                ),
                description_source=(
                    incoming.description_source
                    if use_incoming_description
                    else existing.description_source
                ),
                description_limitation=(
                    incoming.description_limitation
                    if use_incoming_description
                    else existing.description_limitation
                ),
                posted_date=existing.posted_date or incoming.posted_date,
                posted_date_verified=(
                    existing.posted_date_verified or incoming.posted_date_verified
                ),
                posted_date_source=(
                    existing.posted_date_source or incoming.posted_date_source
                ),
                posted_date_reason=(
                    ""
                    if existing.posted_date or incoming.posted_date
                    else existing.posted_date_reason or incoming.posted_date_reason
                ),
                apply_url=existing.apply_url or incoming.apply_url,
            )
            return

    def _clear_cv_cache(self) -> None:
        self.score_cache = {
            key: value for key, value in self.score_cache.items() if not key.startswith("cv:")
        }


def get_session_workspace(state: MutableMapping[str, object]) -> SessionWorkspace:
    workspace = state.get(WORKSPACE_KEY)
    if not isinstance(workspace, SessionWorkspace):
        workspace = SessionWorkspace()
        state[WORKSPACE_KEY] = workspace
    return workspace


def _normalize(value: str) -> str:
    return " ".join(value.casefold().strip().split())


def _legacy_sources(job: JobRecord) -> tuple[JobSource, ...]:
    source = job_source("", job.source_url)
    return (source,) if source.original_url else ()
