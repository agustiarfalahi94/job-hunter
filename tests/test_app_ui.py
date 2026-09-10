import unittest

import pandas as pd
import pyarrow as pa

from job_hunter.app_ui import (
    application_destination,
    editable_criteria_defaults,
    filter_jobs,
    jobs_to_rows,
    provider_status_label,
    queue_column_widths,
    search_summary_to_rows,
    status_counts,
)
from job_hunter.queue import JobRecord
from job_hunter.search import SearchRunSummary


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
                    posted_date="2026-09-09",
                    apply_url="https://careers.example.com/apply/1",
                )
            ]
        )

        self.assertEqual(rows[0]["Score"], 96)
        self.assertEqual(rows[0]["Decision"], "shortlist")
        self.assertEqual(rows[0]["Remarks"], "Strong match")
        self.assertEqual(rows[0]["Description"], "Power BI role")
        self.assertEqual(rows[0]["Posted"], "2026-09-09")
        self.assertNotIn("Status", rows[0])

    def test_jobs_to_rows_labels_missing_posted_date_as_unknown(self):
        job = JobRecord(1, "BI Developer", "A", "Kuala Lumpur", "", "", 96, "shortlist", "new")

        row = jobs_to_rows([job])[0]

        self.assertEqual(row["Posted"], "Unknown")

    def test_filter_jobs_can_show_only_shortlisted_jobs(self):
        jobs = [
            JobRecord(1, "BI Developer", "A", "Kuala Lumpur", "", "", 96, "shortlist", "new"),
            JobRecord(2, "Support", "B", "Kuala Lumpur", "", "", 0, "skip", "new"),
        ]

        filtered = filter_jobs(jobs, decision="shortlist")

        self.assertEqual([job.id for job in filtered], [1])

    def test_application_destination_prefers_safe_apply_url_then_source(self):
        direct = JobRecord(
            1,
            "BI Developer",
            "A",
            "Kuala Lumpur",
            "",
            "https://example.com/jobs/1",
            96,
            "shortlist",
            "new",
            apply_url="https://careers.example.com/apply/1",
        )
        fallback = JobRecord(
            2,
            "Data Analyst",
            "B",
            "Kuala Lumpur",
            "",
            "https://example.com/jobs/2",
            92,
            "shortlist",
            "new",
            apply_url="http://unsafe.example/apply/2",
        )
        unsafe = JobRecord(
            3,
            "BI Analyst",
            "C",
            "Kuala Lumpur",
            "",
            "javascript:alert(1)",
            90,
            "shortlist",
            "new",
        )

        self.assertEqual(application_destination(direct), "https://careers.example.com/apply/1")
        self.assertEqual(application_destination(fallback), "https://example.com/jobs/2")
        self.assertEqual(application_destination(unsafe), "")

    def test_status_counts_includes_empty_defaults(self):
        jobs = [
            JobRecord(1, "BI Developer", "A", "Kuala Lumpur", "", "", 96, "shortlist", "new"),
            JobRecord(2, "BI Analyst", "B", "Kuala Lumpur", "", "", 91, "shortlist", "submitted"),
        ]

        counts = status_counts(jobs)

        self.assertEqual(counts["new"], 1)
        self.assertEqual(counts["submitted"], 1)
        self.assertEqual(counts["drafted"], 0)

    def test_search_summary_to_rows_formats_counts_and_logs(self):
        summary = SearchRunSummary(
            checked=2,
            added=1,
            duplicates=1,
            skipped=0,
            logs=("Searching LinkedIn", "Duplicate skipped: BI Developer at Acme"),
        )

        rows = search_summary_to_rows(summary)

        self.assertEqual(rows[0]["Metric"], "Checked")
        self.assertEqual(rows[0]["Value"], 2)
        self.assertIn("Duplicate skipped", rows[-1]["Detail"])

    def test_search_summary_rows_convert_to_arrow_without_mixed_value_types(self):
        summary = SearchRunSummary(
            checked=2,
            added=1,
            duplicates=0,
            skipped=1,
            logs=("Search complete",),
        )

        frame = pd.DataFrame(search_summary_to_rows(summary))
        self.assertFalse(any(isinstance(value, str) for value in frame["Value"]))
        table = pa.Table.from_pandas(frame, preserve_index=False)

        self.assertEqual(table.column("Value").to_pylist(), [2.0, 1.0, 0.0, 1.0, None])

    def test_provider_status_label_explains_api_and_fallback_modes(self):
        self.assertEqual(provider_status_label(True), "API search enabled")
        self.assertEqual(provider_status_label(False), "Free public search fallback")

    def test_editable_criteria_defaults_reads_preferences(self):
        defaults = editable_criteria_defaults(
            {
                "target_roles": ["BI Developer", "Data Analyst"],
                "primary_keywords": ["Power BI", "SSRS"],
                "bonus_keywords": ["Python", "Airflow"],
                "hard_skip_keywords": ["mandarin speaker is mandatory"],
                "daily_targets": {"strong_matches": 20, "suitable_matches": 50},
            }
        )

        self.assertEqual(defaults["target_roles"], ["BI Developer", "Data Analyst"])
        self.assertEqual(defaults["primary_keywords"], ["Power BI", "SSRS"])
        self.assertEqual(defaults["bonus_keywords"], ["Python", "Airflow"])
        self.assertEqual(defaults["hard_skip_keywords"], ["mandarin speaker is mandatory"])
        self.assertEqual(defaults["strong_target"], 20)
        self.assertEqual(defaults["session_cap"], 50)

    def test_queue_column_widths_make_text_fields_readable(self):
        widths = queue_column_widths()

        self.assertEqual(widths["Title"], "large")
        self.assertEqual(widths["Description"], "large")
        self.assertEqual(widths["Remarks"], "large")
        self.assertEqual(widths["Posted"], "medium")
        self.assertEqual(widths["Source URL"], "medium")


if __name__ == "__main__":
    unittest.main()
