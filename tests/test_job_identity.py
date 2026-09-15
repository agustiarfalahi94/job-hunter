import unittest

from job_hunter.job_identity import (
    canonicalize_job_url,
    stable_job_id,
    vacancy_fingerprint,
)


class JobIdentityTest(unittest.TestCase):
    def test_tracking_variants_have_one_canonical_url_and_stable_id(self):
        first = "https://www.linkedin.com/jobs/view/123/?trk=feed&utm_source=x"
        second = "https://linkedin.com/jobs/view/123#details"

        self.assertEqual(canonicalize_job_url(first), canonicalize_job_url(second))
        self.assertEqual(stable_job_id("LinkedIn", first), "123")

    def test_extracts_known_provider_ids(self):
        self.assertEqual(
            stable_job_id("Indeed", "https://my.indeed.com/viewjob?jk=abc123"),
            "abc123",
        )
        self.assertEqual(
            stable_job_id("JobStreet", "https://my.jobstreet.com/job/987654"),
            "987654",
        )
        self.assertEqual(
            stable_job_id("Foundit", "https://www.foundit.my/job/bi-analyst-456789"),
            "456789",
        )

    def test_fingerprint_requires_specific_title_company_and_location(self):
        self.assertTrue(
            vacancy_fingerprint("BI Analyst", "Example Bank", "Kuala Lumpur")
        )
        self.assertEqual(vacancy_fingerprint("Job", "", "Kuala Lumpur"), "")
        self.assertEqual(vacancy_fingerprint("Data Analyst", "Unknown", "Malaysia"), "")


if __name__ == "__main__":
    unittest.main()
