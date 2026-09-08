"""SQLite-backed local job queue."""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from job_hunter.scoring import score_job


@dataclass(frozen=True)
class JobInput:
    title: str
    company: str = ""
    location: str = ""
    description: str = ""
    source_url: str = ""


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
                    dedupe_key, score, decision, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new')
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
            SELECT id, title, company, location, description, source_url, score, decision, status
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
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
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

    def _get_job(self, job_id: int) -> JobRecord:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, title, company, location, description, source_url, score, decision, status
                FROM jobs
                WHERE id = ?
                """,
                (job_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Job not found: {job_id}")
        return _record_from_row(row)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


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
    )


def _dedupe_key(job: JobInput) -> str:
    if job.source_url.strip():
        return f"url:{job.source_url.strip().casefold()}"
    parts = [job.title, job.company, job.location]
    return "job:" + "|".join(_normalize(part) for part in parts)


def _normalize(value: str) -> str:
    return " ".join(value.casefold().strip().split())
