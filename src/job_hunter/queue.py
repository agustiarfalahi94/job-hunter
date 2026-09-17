"""SQLite-backed local job queue."""

from __future__ import annotations

import csv
import sqlite3
from datetime import datetime, timezone
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from job_hunter.application_packet import build_application_packet
from job_hunter.drafts import build_application_draft, draft_to_markdown
from job_hunter.queue_types import JobInput
from job_hunter.scoring import score_job


@dataclass(frozen=True)
class JobRecord:
    id: int
    title: str
    company: str
    location: str
    description: str
    source_url: str
    score: int
    decision: str
    status: str
    reasons: str = ""
    remarks: str = ""
    posted_date: str = ""
    apply_url: str = ""
    application_status: str = "not_applied"
    description_kind: str = "snippet"
    description_source: str = "search result"
    description_limitation: str = ""
    posted_date_verified: bool = False
    posted_date_source: str = ""
    posted_date_reason: str = ""
    scoring_engine: str = "Deterministic"
    scoring_model: str = ""
    score_limited: bool = False
    cache_hit: bool = False
    application_recorded_at: str = ""
    application_evidence: str = ""
    quick_apply: str = ""
    availability: str = "unknown"
    availability_evidence: str = ""
    platform: str = ""


@dataclass(frozen=True)
class AddResult:
    job_id: int
    created: bool
    score: int
    decision: str


@dataclass(frozen=True)
class ImportSummary:
    created: int
    duplicates: int


class JobQueue:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def add_job(self, job: JobInput, preferences: dict[str, Any]) -> AddResult:
        existing_id = self._find_duplicate(job)
        if existing_id is not None:
            self._backfill_metadata(existing_id, job)
            existing = self._get_job(existing_id)
            return AddResult(existing_id, created=False, score=existing.score, decision=existing.decision)

        scoring = score_job(
            {
                "title": job.title,
                "description": job.description,
                "location": job.location,
            },
            preferences,
        )
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO jobs (
                    title, company, location, description, source_url,
                    dedupe_key, score, decision, status, reasons, remarks,
                    posted_date, apply_url
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?, ?, ?)
                """,
                (
                    job.title.strip(),
                    job.company.strip(),
                    job.location.strip(),
                    job.description.strip(),
                    job.source_url.strip(),
                    _dedupe_key(job),
                    scoring.score,
                    scoring.decision,
                    "\n".join(scoring.reasons),
                    "\n".join(scoring.remarks),
                    job.posted_date.strip(),
                    job.apply_url.strip(),
                ),
            )
        return AddResult(int(cursor.lastrowid), created=True, score=scoring.score, decision=scoring.decision)

    def import_csv(self, csv_path: Path | str, preferences: dict[str, Any]) -> ImportSummary:
        created = 0
        duplicates = 0
        with Path(csv_path).open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                result = self.add_job(
                    JobInput(
                        title=row.get("title", ""),
                        company=row.get("company", ""),
                        location=row.get("location", ""),
                        description=row.get("description", ""),
                        source_url=row.get("source_url", ""),
                    ),
                    preferences,
                )
                if result.created:
                    created += 1
                else:
                    duplicates += 1
        return ImportSummary(created=created, duplicates=duplicates)

    def list_jobs(self, status: str | None = None) -> list[JobRecord]:
        query = """
            SELECT id, title, company, location, description, source_url,
                   score, decision, status, reasons, remarks, posted_date, apply_url,
                   application_status, application_recorded_at, application_evidence
            FROM jobs
        """
        params: tuple[str, ...] = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY score DESC, id DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_record_from_row(row) for row in rows]

    def export_draft(self, job_id: int, output_dir: Path | str) -> Path:
        job = self._get_job(job_id)
        draft = build_application_draft(
            JobInput(
                title=job.title,
                company=job.company,
                location=job.location,
                description=job.description,
                source_url=job.source_url,
            )
        )
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        draft_path = output_path / f"job-{job.id}-{_slug(job.title)}.md"
        draft_path.write_text(draft_to_markdown(draft), encoding="utf-8")
        return draft_path

    def export_application_packet(self, job_id: int, output_dir: Path | str) -> Path:
        job = self._get_job(job_id)
        packet = build_application_packet(
            JobInput(
                title=job.title,
                company=job.company,
                location=job.location,
                description=job.description,
                source_url=job.source_url,
            )
        )
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        packet_path = output_path / f"job-{job.id}-application-packet-{_slug(job.title)}.md"
        packet_path.write_text(packet.markdown, encoding="utf-8")
        return packet_path

    def update_status(self, job_id: int, status: str) -> None:
        allowed = {"new", "reviewing", "drafted", "submitted", "rejected"}
        if status not in allowed:
            raise ValueError(f"Unsupported status: {status}")
        with self._connect() as conn:
            cursor = conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
            if cursor.rowcount != 1:
                raise ValueError(f"Job not found: {job_id}")

    def update_application_status(self, job_id: int, application_status: str | bool) -> None:
        if application_status is True:
            application_status = "applied"
        elif application_status is False:
            application_status = "not_applied"
        allowed = {"not_applied", "applied"}
        if application_status not in allowed:
            raise ValueError(f"Unsupported application status: {application_status}")
        with self._connect() as conn:
            recorded_at = (
                datetime.now(timezone.utc).isoformat(timespec="seconds")
                if application_status == "applied"
                else ""
            )
            evidence = (
                "Marked manually by the user; not verified with the job platform."
                if application_status == "applied"
                else ""
            )
            cursor = conn.execute(
                """
                UPDATE jobs
                SET application_status = ?, application_recorded_at = ?,
                    application_evidence = ?
                WHERE id = ?
                """,
                (application_status, recorded_at, evidence, job_id),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"Job not found: {job_id}")

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL DEFAULT '',
                    location TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    source_url TEXT NOT NULL DEFAULT '',
                    dedupe_key TEXT NOT NULL UNIQUE,
                    score INTEGER NOT NULL,
                    decision TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'new',
                    reasons TEXT NOT NULL DEFAULT '',
                    remarks TEXT NOT NULL DEFAULT '',
                    application_status TEXT NOT NULL DEFAULT 'not_applied',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            _ensure_column(conn, "jobs", "reasons", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(conn, "jobs", "remarks", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(conn, "jobs", "posted_date", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(conn, "jobs", "apply_url", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(
                conn,
                "jobs",
                "application_status",
                "TEXT NOT NULL DEFAULT 'not_applied'",
            )
            _ensure_column(
                conn, "jobs", "application_recorded_at", "TEXT NOT NULL DEFAULT ''"
            )
            _ensure_column(
                conn, "jobs", "application_evidence", "TEXT NOT NULL DEFAULT ''"
            )

    def _find_duplicate(self, job: JobInput) -> int | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM jobs WHERE dedupe_key = ?",
                (_dedupe_key(job),),
            ).fetchone()
        if row is None:
            return None
        return int(row["id"])

    def _backfill_metadata(self, job_id: int, job: JobInput) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET posted_date = CASE
                        WHEN posted_date = '' THEN ? ELSE posted_date
                    END,
                    apply_url = CASE
                        WHEN apply_url = '' THEN ? ELSE apply_url
                    END
                WHERE id = ?
                """,
                (job.posted_date.strip(), job.apply_url.strip(), job_id),
            )

    def _get_job(self, job_id: int) -> JobRecord:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, title, company, location, description, source_url,
                       score, decision, status, reasons, remarks, posted_date, apply_url,
                       application_status, application_recorded_at, application_evidence
                FROM jobs
                WHERE id = ?
                """,
                (job_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Job not found: {job_id}")
        return _record_from_row(row)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _record_from_row(row: sqlite3.Row) -> JobRecord:
    return JobRecord(
        id=int(row["id"]),
        title=str(row["title"]),
        company=str(row["company"]),
        location=str(row["location"]),
        description=str(row["description"]),
        source_url=str(row["source_url"]),
        score=int(row["score"]),
        decision=str(row["decision"]),
        status=str(row["status"]),
        reasons=str(row["reasons"]),
        remarks=str(row["remarks"]),
        posted_date=str(row["posted_date"]),
        apply_url=str(row["apply_url"]),
        application_status=str(row["application_status"]),
        application_recorded_at=str(row["application_recorded_at"]),
        application_evidence=str(row["application_evidence"]),
    )


def _dedupe_key(job: JobInput) -> str:
    parts = [job.title, job.company, job.location]
    if all(part.strip() for part in parts):
        return "job:" + "|".join(_normalize(part) for part in parts)
    if job.source_url.strip():
        return f"url:{job.source_url.strip().casefold()}"
    return "job:" + "|".join(_normalize(part) for part in parts)


def _normalize(value: str) -> str:
    return " ".join(value.casefold().strip().split())


def _slug(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value.strip())
    parts = [part for part in cleaned.split("-") if part]
    return "-".join(parts) or "draft"


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, declaration: str) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
