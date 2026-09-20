import re
import tomllib
import unittest
from pathlib import Path


class ReleaseDocumentationTest(unittest.TestCase):
    def test_account_template_is_disabled_and_credentials_are_empty(self):
        raw = tomllib.loads(Path(".streamlit/accounts.secrets.example.toml").read_text())
        self.assertIs(raw["accounts"]["enabled"], False)
        for key in ("supabase_url", "supabase_secret_key", "encryption_key"):
            self.assertEqual(raw["accounts"][key], "")
        self.assertEqual(raw["auth"]["cookie_secret"], "")
        for key in ("client_id", "client_secret"):
            self.assertEqual(raw["auth"]["google"][key], "")
        self.assertEqual(raw["auth"]["redirect_uri"], "https://jobs-hunter.streamlit.app/oauth2callback")
        self.assertTrue(Path("docs/ACCOUNT_SETUP.md").is_file())

    def test_release_version_is_consistent(self):
        self.assertIn('version = "1.18.5"', Path("pyproject.toml").read_text())
        self.assertIn("v1.18.5", Path("README.md").read_text())
        self.assertIn("v1.18.5", Path("src/job_hunter/__init__.py").read_text())
        self.assertIn("v1.18.5", Path("AGENTS.md").read_text())
        self.assertIn("v1.18.5", Path("docs/ARCHITECTURE.md").read_text())

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
        self.assertIn("empty platform selection does not mean all platforms", readme.casefold())
        self.assertIn("CV-derived selections", readme)
        self.assertIn("Red asterisks mark the only three required selections", readme)

    def test_example_secret_keys_are_blank(self):
        secrets = Path(".streamlit/secrets.example.toml").read_text()

        self.assertRegex(secrets, r'(?m)^SERPAPI_API_KEY = ""$')
        self.assertRegex(secrets, r'(?m)^GEMINI_API_KEY = ""$')
        self.assertIsNone(re.search(r'(?m)^(?:SERPAPI|GEMINI)_API_KEY = ".+"$', secrets))


if __name__ == "__main__":
    unittest.main()
