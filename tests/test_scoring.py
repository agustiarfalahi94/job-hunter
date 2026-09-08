import unittest


from job_hunter.scoring import DEFAULT_WEIGHTS, score_job


class ScoringTest(unittest.TestCase):
    def test_scores_strong_data_engineering_match_above_threshold(self):
        job = {
            "title": "Data Engineer",
            "description": (
                "Build SQL and Python pipelines with Airflow, Docker, BigQuery, "
                "data migration validation, CI/CD, and stakeholder reporting."
            ),
            "location": "Kuala Lumpur, Malaysia",
            "employment_type": "Full-time",
            "remote_policy": "Hybrid",
        }
        preferences = {
            "target_roles": ["Data Engineer", "Analytics Engineer", "BI Developer"],
            "target_locations": ["Kuala Lumpur", "Malaysia", "Remote"],
            "preferred_keywords": [
                "SQL",
                "Python",
                "Airflow",
                "Docker",
                "BigQuery",
                "data migration",
                "Power BI",
            ],
            "avoid_keywords": ["senior manager", "sales quota"],
            "minimum_score_to_apply": 70,
        }

        result = score_job(job, preferences)

        self.assertGreaterEqual(result.score, preferences["minimum_score_to_apply"])
        self.assertEqual(result.decision, "shortlist")
        self.assertIn("Role title matches target role: Data Engineer", result.reasons)
        self.assertIn(
            "Matched preferred keywords: SQL, Python, Airflow, Docker, BigQuery, data migration",
            result.reasons,
        )

    def test_rejects_job_with_too_many_avoid_keywords(self):
        job = {
            "title": "Sales Manager",
            "description": "Own sales quota and cold calling for a senior manager role.",
            "location": "Kuala Lumpur",
        }
        preferences = {
            "target_roles": ["Data Engineer"],
            "target_locations": ["Kuala Lumpur"],
            "preferred_keywords": ["SQL", "Python"],
            "avoid_keywords": ["sales quota", "cold calling", "senior manager"],
            "minimum_score_to_apply": 70,
        }

        result = score_job(job, preferences)

        self.assertEqual(result.decision, "reject")
        self.assertLess(result.score, 50)
        self.assertIn("Avoid keywords found: sales quota, cold calling, senior manager", result.reasons)

    def test_uses_default_weights_when_preferences_are_sparse(self):
        job = {
            "title": "BI Developer",
            "description": "Maintain Power BI, SSRS, SQL, PostgreSQL, and stakeholder reporting.",
            "location": "Remote",
        }

        result = score_job(job, {"target_roles": ["BI Developer"]})

        self.assertGreaterEqual(result.score, 0)
        self.assertLessEqual(result.score, 100)
        self.assertEqual(result.weights, DEFAULT_WEIGHTS)
        self.assertIn(result.decision, {"shortlist", "review", "reject"})


if __name__ == "__main__":
    unittest.main()
