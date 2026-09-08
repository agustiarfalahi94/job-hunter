import unittest

from job_hunter.app_ui import filter_jobs, jobs_to_rows, status_counts
from job_hunter.queue import JobRecord


class AppUiTest(unittest.TestCase):
    def test_jobs_to_rows_contains_decision_and_remarks(self):
        rows = jobs_to_rows(
            [
                JobRecord(
                    id=1,
                    title="BI Developer",
                    company="Acme",
                    location="Kuala Lumpur",
                    description="Power BI role",
                    source_url="https://example.com/job",
                    score=96,
                    decision="shortlist",
                    status="new",
                    remarks="Strong match",
                )
            ]
        )

        self.assertEqual(rows[0]["Score"], 96)
        self.assertEqual(rows[0]["Decision"], "shortlist")
        self.assertEqual(rows[0]["Remarks"], "Strong match")

    def test_filter_jobs_can_show_only_shortlisted_jobs(self):
        jobs = [
            JobRecord(1, "BI Developer", "A", "Kuala Lumpur", "", "", 96, "shortlist", "new"),
            JobRecord(2, "Support", "B", "Kuala Lumpur", "", "", 0, "skip", "new"),
        ]

        filtered = filter_jobs(jobs, decision="shortlist", status="all")

        self.assertEqual([job.id for job in filtered], [1])

    def test_status_counts_includes_empty_defaults(self):
        jobs = [
            JobRecord(1, "BI Developer", "A", "Kuala Lumpur", "", "", 96, "shortlist", "new"),
            JobRecord(2, "BI Analyst", "B", "Kuala Lumpur", "", "", 91, "shortlist", "submitted"),
        ]

        counts = status_counts(jobs)

        self.assertEqual(counts["new"], 1)
        self.assertEqual(counts["submitted"], 1)
        self.assertEqual(counts["drafted"], 0)


if __name__ == "__main__":
    unittest.main()
