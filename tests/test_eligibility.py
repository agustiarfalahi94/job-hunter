import unittest

from job_hunter.eligibility import hard_skip_matches


class EligibilityTest(unittest.TestCase):
    def test_local_only_aliases_match_restricted_titles(self):
        keywords = ["locals/malaysian only"]

        matches = hard_skip_matches("Senior BI Specialist (Local Applicant Only)", keywords)

        self.assertEqual(matches, ("locals/malaysian only",))

    def test_punctuation_and_case_are_normalized(self):
        matches = hard_skip_matches(
            "POWER BI role - MANDARIN SPEAKER IS MANDATORY!",
            ["mandarin speaker is mandatory"],
        )

        self.assertEqual(matches, ("mandarin speaker is mandatory",))

    def test_local_team_wording_is_not_restricted(self):
        matches = hard_skip_matches(
            "Build reports with the local analytics team.",
            ["locals/malaysian only"],
        )

        self.assertEqual(matches, ())


if __name__ == "__main__":
    unittest.main()
