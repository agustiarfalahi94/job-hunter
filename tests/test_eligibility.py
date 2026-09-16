import unittest

from job_hunter.eligibility import hard_skip_matches


class EligibilityTest(unittest.TestCase):
    def test_requirement_words_in_unrelated_sentences_do_not_trigger_local_skip(self):
        self.assertEqual(hard_skip_matches(
            "Work with the local analytics team. Applicants must know Python.",
            ["local applicant only"],
        ), ())

    def test_optional_skill_does_not_hide_separate_mandatory_mandarin_requirement(self):
        self.assertEqual(hard_skip_matches(
            "Mandarin fluency is required. SQL is an advantage.",
            ["mandarin speaker is mandatory"],
        ), ("mandarin speaker is mandatory",))

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

    def test_local_only_rule_matches_equivalent_eligibility_wording(self):
        matches = hard_skip_matches(
            "Applicants must be Malaysian citizens to be considered.",
            ["local applicant only"],
        )

        self.assertEqual(matches, ("local applicant only",))

    def test_mandarin_rule_matches_equivalent_mandatory_wording(self):
        matches = hard_skip_matches(
            "Fluency in Mandarin is required for this position.",
            ["mandarin speaker is mandatory"],
        )

        self.assertEqual(matches, ("mandarin speaker is mandatory",))

    def test_optional_mandarin_wording_is_not_restricted(self):
        matches = hard_skip_matches(
            "Mandarin language skills are an advantage but not required.",
            ["mandarin speaker is mandatory"],
        )

        self.assertEqual(matches, ())

        matches = hard_skip_matches(
            "Mandarin is not required for this position.",
            ["mandarin required"],
        )

        self.assertEqual(matches, ())


if __name__ == "__main__":
    unittest.main()
