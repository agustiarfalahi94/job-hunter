from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

from job_hunter.queue import JobInput, JobQueue


class JobQueueTest(unittest.TestCase):
    def test_add_job_stores_posted_date_and_apply_url(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            queue = JobQueue(Path(tmpdir) / "jobs.db")
            queue.add_job(
                JobInput(
                    title="BI Developer",
                    company="Example Analytics",
                    location="Kuala Lumpur",
                    description="Power BI reporting role",
                    source_url="https://example.com/jobs/bi",
                    posted_date="2026-09-09",
                    apply_url="https://careers.example.com/apply/bi",
                ),
                {"target_roles": ["BI Developer"], "primary_keywords": ["Power BI"]},
            )

            job = queue.list_jobs()[0]

        self.assertEqual(job.posted_date, "2026-09-09")
        self.assertEqual(job.apply_url, "https://careers.example.com/apply/bi")

    def test_existing_database_is_migrated_without_losing_jobs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "jobs.db"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute(
                    """
                    CREATE TABLE jobs (
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
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO jobs (
                        title, company, location, description, source_url,
                        dedupe_key, score, decision, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "Data Analyst",
                        "Acme",
                        "Kuala Lumpur",
                        "Power BI dashboards",
                        "https://example.com/jobs/1",
                        "job:data analyst|acme|kuala lumpur",
                        95,
                        "shortlist",
                        "new",
                    ),
                )
                conn.commit()

            queue = JobQueue(db_path)
            jobs = queue.list_jobs()
            with closing(sqlite3.connect(db_path)) as conn:
                columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Data Analyst")
        self.assertEqual(jobs[0].posted_date, "")
        self.assertEqual(jobs[0].apply_url, "")
        self.assertIn("posted_date", columns)
        self.assertIn("apply_url", columns)

    def test_add_scores_and_lists_job_for_review(self):
        preferences = {
            "target_roles": ["Data Engineer"],
            "target_locations": ["Kuala Lumpur"],
            "preferred_keywords": ["SQL", "Python", "Airflow", "BigQuery"],
            "avoid_keywords": ["sales quota"],
            "minimum_score_to_apply": 70,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            queue = JobQueue(Path(tmpdir) / "jobs.db")
            created = queue.add_job(
                JobInput(
                    title="Data Engineer",
                    company="Example Analytics",
                    location="Kuala Lumpur",
                    description="SQL Python Airflow BigQuery migration pipelines",
                    source_url="https://example.com/jobs/1",
                ),
                preferences,
            )

            jobs = queue.list_jobs()

        self.assertTrue(created.created)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Data Engineer")
        self.assertEqual(jobs[0].company, "Example Analytics")
        self.assertEqual(jobs[0].decision, "shortlist")
        self.assertGreaterEqual(jobs[0].score, 70)
        self.assertEqual(jobs[0].status, "new")

    def test_add_job_deduplicates_by_source_url(self):
        preferences = {"target_roles": ["BI Developer"]}
        with tempfile.TemporaryDirectory() as tmpdir:
            queue = JobQueue(Path(tmpdir) / "jobs.db")
            first = queue.add_job(
                JobInput(
                    title="BI Developer",
                    company="Acme",
                    location="Remote",
                    description="Power BI and SQL reports",
                    source_url="https://example.com/jobs/bi",
                ),
                preferences,
            )
            second = queue.add_job(
                JobInput(
                    title="BI Developer",
                    company="Acme",
                    location="Remote",
                    description="Power BI and SQL reports updated",
                    source_url="https://example.com/jobs/bi",
                ),
                preferences,
            )

            jobs = queue.list_jobs()

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.job_id, second.job_id)
        self.assertEqual(len(jobs), 1)

    def test_add_job_deduplicates_cross_platform_exact_same_role(self):
        preferences = {"target_roles": ["Data Analyst"], "primary_keywords": ["Power BI"]}
        with tempfile.TemporaryDirectory() as tmpdir:
            queue = JobQueue(Path(tmpdir) / "jobs.db")
            first = queue.add_job(
                JobInput(
                    title="Data Analyst",
                    company="Acme",
                    location="Kuala Lumpur",
                    description="Power BI reporting role",
                    source_url="https://linkedin.example/jobs/123",
                ),
                preferences,
            )
            second = queue.add_job(
                JobInput(
                    title="data analyst",
                    company=" ACME ",
                    location=" kuala lumpur ",
                    description="Power BI and SQL reporting role",
                    source_url="https://foundit.example/jobs/abc",
                ),
                preferences,
            )

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.job_id, second.job_id)

    def test_add_job_deduplicates_by_title_company_location_when_url_missing(self):
        preferences = {"target_roles": ["Analytics Engineer"]}
        with tempfile.TemporaryDirectory() as tmpdir:
            queue = JobQueue(Path(tmpdir) / "jobs.db")
            first = queue.add_job(
                JobInput(
                    title="Analytics Engineer",
                    company="Data House",
                    location="Malaysia",
                    description="SQL models",
                ),
                preferences,
            )
            second = queue.add_job(
                JobInput(
                    title=" analytics engineer ",
                    company="data house",
                    location=" malaysia ",
                    description="SQL models and dashboards",
                ),
                preferences,
            )

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.job_id, second.job_id)

    def test_imports_jobs_from_csv(self):
        preferences = {
            "target_roles": ["Data Analyst"],
            "preferred_keywords": ["SQL", "Power BI"],
        }
        csv_text = (
            "title,company,location,description,source_url\n"
            "Data Analyst,Acme,Remote,SQL and Power BI dashboards,https://example.com/1\n"
            "Data Analyst,Acme,Remote,Duplicate row,https://example.com/1\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "jobs.csv"
            csv_path.write_text(csv_text, encoding="utf-8")
            queue = JobQueue(Path(tmpdir) / "jobs.db")

            summary = queue.import_csv(csv_path, preferences)

        self.assertEqual(summary.created, 1)
        self.assertEqual(summary.duplicates, 1)

    def test_stores_remarks_for_low_suitability_job(self):
        preferences = {
            "target_roles": ["Data Engineer"],
            "primary_keywords": ["Power BI"],
            "hard_skip_keywords": ["locals/malaysian only"],
            "minimum_score_to_apply": 90,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            queue = JobQueue(Path(tmpdir) / "jobs.db")
            queue.add_job(
                JobInput(
                    title="Customer Support",
                    company="Acme",
                    location="Kuala Lumpur",
                    description="Handle general customer tickets.",
                ),
                preferences,
            )

            job = queue.list_jobs()[0]

        self.assertIn("Missing primary keyword", job.remarks)
        self.assertIn("Low suitability", job.remarks)


if __name__ == "__main__":
    unittest.main()
