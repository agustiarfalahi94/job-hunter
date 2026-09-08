import tempfile
import unittest
from pathlib import Path

from job_hunter.preferences import load_preferences


class PreferencesTest(unittest.TestCase):
    def test_loads_simple_yaml_preferences(self):
        text = """
target_roles:
  - Data Analyst
  - BI Developer
primary_keywords:
  - Power BI
  - SSRS
hard_skip_keywords:
  - locals/malaysian only
minimum_score_to_apply: 90
daily_targets:
  strong_matches: 20
  suitable_matches: 50
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "preferences.local.yaml"
            path.write_text(text, encoding="utf-8")

            preferences = load_preferences(path)

        self.assertEqual(preferences["target_roles"], ["Data Analyst", "BI Developer"])
        self.assertEqual(preferences["primary_keywords"], ["Power BI", "SSRS"])
        self.assertEqual(preferences["hard_skip_keywords"], ["locals/malaysian only"])
        self.assertEqual(preferences["minimum_score_to_apply"], 90)
        self.assertEqual(preferences["daily_targets"]["strong_matches"], 20)
        self.assertEqual(preferences["daily_targets"]["suitable_matches"], 50)


if __name__ == "__main__":
    unittest.main()
