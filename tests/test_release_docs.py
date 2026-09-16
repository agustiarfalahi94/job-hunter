import re
import unittest
from pathlib import Path


class ReleaseDocumentationTest(unittest.TestCase):
    def test_release_version_is_consistent(self):
        self.assertIn('version = "1.15.3"', Path("pyproject.toml").read_text())
        self.assertIn("v1.15.3", Path("README.md").read_text())
        self.assertIn("v1.15.3", Path("src/job_hunter/__init__.py").read_text())

    def test_readme_documents_modes_privacy_and_stop_limit(self):
        readme = Path("README.md").read_text()

        for phrase in (
            "GEMINI_API_KEY",
            "SERPAPI_API_KEY",
            "Criteria-based search",
            "CV-based search",
            "session-only",
            "in-flight",
        ):
            self.assertIn(phrase, readme)
        self.assertNotIn("Strong-match goal", readme)
        self.assertNotIn("Maximum jobs in one session", readme)

    def test_example_secret_keys_are_blank(self):
        secrets = Path(".streamlit/secrets.example.toml").read_text()

        self.assertRegex(secrets, r'(?m)^SERPAPI_API_KEY = ""$')
        self.assertRegex(secrets, r'(?m)^GEMINI_API_KEY = ""$')
        self.assertIsNone(re.search(r'(?m)^(?:SERPAPI|GEMINI)_API_KEY = ".+"$', secrets))


if __name__ == "__main__":
    unittest.main()
