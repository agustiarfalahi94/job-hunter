import tempfile
import unittest
from pathlib import Path

from job_hunter.queue import JobQueue
from job_hunter.queue_types import JobInput
from job_hunter.workflow import daily_summary


class WorkflowTest(unittest.TestCase):
    def test_updates_status_and_counts_daily_progress(self):
        preferences = {"target_roles": ["Data Engineer"], "preferred_keywords": ["SQL", "Python"]}
        with tempfile.TemporaryDirectory() as tmpdir:
            queue = JobQueue(Path(tmpdir) / "jobs.db")
            first = queue.add_job(
                JobInput(title="Data Engineer", company="A", description="SQL Python"),
                preferences,
            )
            queue.add_job(
                JobInput(title="BI Developer", company="B", description="Power BI SQL"),
                preferences,
            )
            queue.update_status(first.job_id, "submitted")

            summary = daily_summary(queue, daily_target=100)

        self.assertEqual(summary.daily_target, 100)
        self.assertEqual(summary.submitted_today, 1)
        self.assertEqual(summary.remaining_today, 99)
        self.assertEqual(summary.total_queued, 2)
        self.assertEqual(summary.by_status["submitted"], 1)
        self.assertEqual(summary.by_status["new"], 1)

    def test_next_action_prioritizes_new_shortlisted_jobs(self):
        preferences = {
            "target_roles": ["Data Engineer"],
            "preferred_keywords": ["SQL", "Python", "Airflow", "BigQuery"],
            "minimum_score_to_apply": 70,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            queue = JobQueue(Path(tmpdir) / "jobs.db")
            queue.add_job(
                JobInput(title="Data Engineer", company="A", description="SQL Python Airflow BigQuery"),
                preferences,
            )

            summary = daily_summary(queue, daily_target=100)

        self.assertEqual(summary.next_action, "Review 1 shortlisted job and export application packets.")


if __name__ == "__main__":
    unittest.main()
