import tempfile
import unittest
from pathlib import Path

from job_hunter.queue import JobInput, JobQueue


class JobQueueTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
