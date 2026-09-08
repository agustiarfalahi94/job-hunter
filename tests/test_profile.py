import unittest

from job_hunter.profile import CANDIDATE_PROFILE, public_profile_summary


class ProfileTest(unittest.TestCase):
    def test_public_profile_excludes_contact_details(self):
        summary = public_profile_summary(CANDIDATE_PROFILE)

        lower_summary = summary.lower()
        self.assertNotIn("@gmail", lower_summary)
        self.assertNotIn("+60", lower_summary)
        self.assertNotIn("phone", lower_summary)
        self.assertNotIn("email", lower_summary)

    def test_public_profile_keeps_cv_supported_strengths(self):
        summary = public_profile_summary(CANDIDATE_PROFILE)

        self.assertIn("BigQuery", summary)
        self.assertIn("MaxCompute", summary)
        self.assertIn("Airflow", summary)
        self.assertIn("Docker", summary)
        self.assertIn("Power BI", summary)


if __name__ == "__main__":
    unittest.main()
