"""Command-line interface for local Job Hunter workflows."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from job_hunter.queue import JobInput, JobQueue


DEFAULT_DB = Path("data/applications.db")
DEFAULT_PREFERENCES = {
    "target_roles": ["Data Engineer", "Analytics Engineer", "BI Developer", "Data Analyst"],
    "target_locations": ["Kuala Lumpur", "Malaysia", "Remote", "Singapore"],
    "preferred_keywords": [
        "SQL",
        "Python",
        "BigQuery",
        "MaxCompute",
        "Airflow",
        "Docker",
        "CI/CD",
        "data migration",
        "Power BI",
        "SSRS",
        "PostgreSQL",
        "MySQL",
    ],
    "avoid_keywords": ["unpaid", "commission only", "senior manager", "sales quota", "cold calling"],
    "minimum_score_to_apply": 70,
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    queue = JobQueue(args.db)

    if args.command == "add":
        result = queue.add_job(
            JobInput(
                title=args.title,
                company=args.company,
                location=args.location,
                description=args.description,
                source_url=args.source_url,
            ),
            DEFAULT_PREFERENCES,
        )
        action = "created" if result.created else "duplicate"
        print(f"{action}: job_id={result.job_id} score={result.score} decision={result.decision}")
        return 0

    if args.command == "import-csv":
        summary = queue.import_csv(args.path, DEFAULT_PREFERENCES)
        print(f"imported: created={summary.created} duplicates={summary.duplicates}")
        return 0

    if args.command == "list":
        jobs = queue.list_jobs(status=args.status)
        if not jobs:
            print("No jobs in queue.")
            return 0
        for job in jobs:
            print(
                f"{job.id}\t{job.score}\t{job.decision}\t{job.status}\t"
                f"{job.title}\t{job.company}\t{job.location}"
            )
        return 0

    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="job-hunter")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    subparsers = parser.add_subparsers(dest="command")

    add = subparsers.add_parser("add", help="Add one job to the local queue")
    add.add_argument("--title", required=True)
    add.add_argument("--company", default="")
    add.add_argument("--location", default="")
    add.add_argument("--description", required=True)
    add.add_argument("--source-url", default="")

    import_csv = subparsers.add_parser("import-csv", help="Import jobs from a CSV file")
    import_csv.add_argument("path", type=Path)

    list_jobs = subparsers.add_parser("list", help="List queued jobs")
    list_jobs.add_argument("--status", default=None)

    return parser


if __name__ == "__main__":
    raise SystemExit(main())
