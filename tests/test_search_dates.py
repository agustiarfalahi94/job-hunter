import unittest
from datetime import date
from pathlib import Path

from job_hunter.search import extract_job_metadata


FIXTURES = Path(__file__).parent / "fixtures" / "jobs"
SOURCE = "https://my.linkedin.com/jobs/view/123"


class SearchDateProvenanceTest(unittest.TestCase):
    def test_jobposting_date_wins_over_update_and_application_dates(self):
        html = (FIXTURES / "linkedin_inconsistent_dates.html").read_text(
            encoding="utf-8"
        )

        metadata = extract_job_metadata(html, SOURCE, today=date(2026, 9, 15))

        self.assertEqual(metadata.posted_date, "2026-09-10")
        self.assertTrue(metadata.posted_date_verified)
        self.assertEqual(metadata.posted_date_source, "JobPosting.datePosted")
        self.assertEqual(metadata.posted_date_reason, "")

    def test_generic_updated_page_does_not_become_posting_date(self):
        html = (FIXTURES / "generic_updated_page.html").read_text(encoding="utf-8")

        metadata = extract_job_metadata(html, SOURCE, today=date(2026, 9, 15))

        self.assertEqual(metadata.posted_date, "")
        self.assertFalse(metadata.posted_date_verified)
        self.assertEqual(
            metadata.posted_date_reason, "No job-specific posting date found"
        )

    def test_job_specific_visible_relative_date_records_provenance(self):
        metadata = extract_job_metadata(
            '<div class="posted-time-ago__text">2 months ago</div>',
            SOURCE,
            today=date(2026, 9, 15),
        )

        self.assertEqual(metadata.posted_date, "2026-07-17")
        self.assertTrue(metadata.posted_date_verified)
        self.assertEqual(metadata.posted_date_source, "job page element")


if __name__ == "__main__":
    unittest.main()
