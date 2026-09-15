import unittest
from pathlib import Path

from job_hunter.descriptions import extract_job_description


FIXTURES = Path(__file__).parent / "fixtures" / "jobs"


class DescriptionExtractionTest(unittest.TestCase):
    def test_structured_jobposting_description_replaces_snippet(self):
        html = (FIXTURES / "linkedin_structured_description.html").read_text(
            encoding="utf-8"
        )

        result = extract_job_description(html, snippet="Short search text")

        self.assertEqual(result.kind, "full")
        self.assertIn("Power BI dashboards", result.text)
        self.assertIn("SSRS reports", result.text)
        self.assertEqual(result.source, "JobPosting.description")
        self.assertEqual(result.limitation, "")

    def test_recognized_job_description_container_is_full(self):
        html = """
        <nav>Navigation and cookies</nav>
        <section id="jobDescriptionText">
          Build Power BI dashboards and SSRS reports for regional stakeholders.
          Maintain semantic models, document requirements, and validate reporting data.
        </section>
        <footer>Privacy policy</footer>
        """

        result = extract_job_description(html, snippet="Short result")

        self.assertEqual(result.kind, "full")
        self.assertIn("semantic models", result.text)
        self.assertNotIn("Navigation", result.text)

    def test_content_free_page_retains_snippet_with_limitation(self):
        result = extract_job_description(
            "<html><title>Access denied</title><body>Challenge</body></html>",
            snippet="BI role",
        )

        self.assertEqual(result.kind, "snippet")
        self.assertEqual(result.text, "BI role")
        self.assertEqual(result.source, "search result")
        self.assertTrue(result.limitation)

    def test_missing_page_and_snippet_is_unavailable(self):
        result = extract_job_description("", snippet="")

        self.assertEqual(result.kind, "unavailable")
        self.assertEqual(result.text, "")
        self.assertTrue(result.limitation)


if __name__ == "__main__":
    unittest.main()
