"""Command-line interface for local Job Hunter workflows."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from job_hunter.preferences import load_preferences
from job_hunter.queue import JobQueue
from job_hunter.queue_types import JobInput
from job_hunter.workflow import daily_summary, summary_to_text


DEFAULT_DB = Path("data/applications.db")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    queue = JobQueue(args.db)
    preferences = load_preferences(args.preferences)

    if args.command == "add":
        result = queue.add_job(
            JobInput(
                title=args.title,
                company=args.company,
                location=args.location,
                description=args.description,
                source_url=args.source_url,
            ),
            preferences,
        )
        action = "created" if result.created else "duplicate"
        print(f"{action}: job_id={result.job_id} score={result.score} decision={result.decision}")
        return 0

    if args.command == "import-csv":
        summary = queue.import_csv(args.path, preferences)
        print(f"imported: created={summary.created} duplicates={summary.duplicates}")
        return 0

    if args.command == "list":
        jobs = queue.list_jobs(status=args.status)
        if not jobs:
            print("No jobs in queue.")
            return 0
        for job in jobs:
            remarks = f"\t{job.remarks}" if job.remarks else ""
            print(
                f"{job.id}\t{job.score}\t{job.decision}\t{job.status}\t"
                f"{job.title}\t{job.company}\t{job.location}{remarks}"
            )
        return 0

    if args.command == "draft":
        draft_path = queue.export_draft(args.job_id, args.output_dir)
        print(f"draft exported: {draft_path}")
        return 0

    if args.command == "packet":
        packet_path = queue.export_application_packet(args.job_id, args.output_dir)
        print(f"application packet exported: {packet_path}")
        return 0

    if args.command == "status":
        queue.update_status(args.job_id, args.status)
        print(f"status updated: job_id={args.job_id} status={args.status}")
        return 0

    if args.command == "today":
        print(summary_to_text(daily_summary(queue, args.target)), end="")
        return 0

    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="job-hunter")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--preferences", type=Path, default=Path("config/preferences.local.yaml"))
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

    draft = subparsers.add_parser("draft", help="Export a draft for a queued job")
    draft.add_argument("job_id", type=int)
    draft.add_argument("--output-dir", type=Path, default=Path("exports/drafts"))

    packet = subparsers.add_parser("packet", help="Export a dry-run application packet")
    packet.add_argument("job_id", type=int)
    packet.add_argument("--output-dir", type=Path, default=Path("exports/application-packets"))

    status = subparsers.add_parser("status", help="Update a queued job status")
    status.add_argument("job_id", type=int)
    status.add_argument("status", choices=["new", "reviewing", "drafted", "submitted", "rejected"])

    today = subparsers.add_parser("today", help="Show today's application workflow summary")
    today.add_argument("--target", type=int, default=100)

    return parser


if __name__ == "__main__":
    raise SystemExit(main())
