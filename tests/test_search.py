import tempfile
import unittest
from pathlib import Path

from job_hunter.queue import JobQueue
from job_hunter.runtime_config import SearchProviderConfig
from job_hunter.search import (
    SearchCriteria,
    build_serpapi_queries,
    build_direct_platform_queries,
    build_search_queries,
    parse_serpapi_results,
    parse_linkedin_jobs,
    parse_duckduckgo_results,
    run_public_search,
)


DUCKDUCKGO_HTML = """
<html>
  <body>
    <a class="result__a" href="https://www.linkedin.com/jobs/view/123">BI Developer - Acme</a>
    <a class="result__snippet">Power BI and SSRS reporting role in Kuala Lumpur.</a>
    <a class="result__a" href="https://www.foundit.my/job/456">Data Engineer - Beta</a>
    <a class="result__snippet">BigQuery pipelines with Python and Airflow.</a>
  </body>
</html>
"""

NOISY_HTML = """
<html>
  <body>
    <a class="result__a" href="https://www.linkedin.com/learning/power-bi-developer-course">Power BI Developer course - Learn Power BI In 15 Days</a>
    <a class="result__snippet">Training course, not a job opening.</a>
    <a class="result__a" href="https://www.linkedin.com/jobs/view/789">BI Developer - Acme</a>
    <a class="result__snippet">Power BI reporting role in Kuala Lumpur.</a>
  </body>
</html>
"""

LINKEDIN_HTML = """
<html>
  <body>
    <div class="base-search-card">
      <a class="base-card__full-link" href="https://my.linkedin.com/jobs/view/123">Power BI Developer</a>
      <h3 class="base-search-card__title">Power BI Developer</h3>
      <h4 class="base-search-card__subtitle">HCLTech</h4>
      <span class="job-search-card__location">Kuala Lumpur, Malaysia</span>
    </div>
    <div class="base-search-card">
      <a class="base-card__full-link" href="https://my.linkedin.com/jobs/view/456">Business Intelligence Analyst</a>
      <h3 class="base-search-card__title">Business Intelligence Analyst</h3>
      <h4 class="base-search-card__subtitle">Example Bank</h4>
      <span class="job-search-card__location">Greater Kuala Lumpur</span>
    </div>
  </body>
</html>
"""

SERPAPI_JSON = """
{
  "organic_results": [
    {
      "title": "BI Developer - HCLTech",
      "link": "https://my.linkedin.com/jobs/view/123",
      "snippet": "Power BI reporting role in Kuala Lumpur."
    },
    {
      "title": "Data Analyst - Example Bank",
      "link": "https://my.jobstreet.com/job/456",
      "snippet": "BigQuery dashboards and Python scripts."
    }
  ]
}
"""


class SearchTest(unittest.TestCase):
    def test_build_search_queries_targets_selected_platforms(self):
        criteria = SearchCriteria(
            title_terms=("Data Analyst", "BI Developer"),
            description_terms=("Power BI",),
            location="Kuala Lumpur",
            platforms=("LinkedIn", "Company career pages"),
            max_results=50,
        )

        queries = build_search_queries(criteria)

        self.assertEqual(len(queries), 2)
        self.assertIn("site:linkedin.com/jobs", queries[0].query)
        self.assertIn('"Data Analyst" OR "BI Developer"', queries[0].query)
        self.assertIn('"Power BI"', queries[0].query)
        self.assertIn('"Kuala Lumpur"', queries[0].query)
        self.assertIn("site:careers.accenture.com", queries[1].query)

    def test_build_direct_platform_queries_creates_linkedin_public_url(self):
        criteria = SearchCriteria(
            title_terms=("BI Developer",),
            description_terms=("Power BI",),
            location="Kuala Lumpur",
            platforms=("LinkedIn", "Indeed"),
            max_results=10,
        )

        queries = build_direct_platform_queries(criteria)

        self.assertEqual(len(queries), 1)
        self.assertEqual(queries[0].platform, "LinkedIn")
        self.assertIn("linkedin.com/jobs/search", queries[0].url)
        self.assertIn("BI+Developer+Power+BI", queries[0].url)

    def test_build_serpapi_queries_uses_key_without_exposing_it_in_query(self):
        criteria = SearchCriteria(
            title_terms=("Data Analyst",),
            description_terms=("Power BI",),
            location="Kuala Lumpur",
            platforms=("JobStreet",),
            max_results=10,
        )

        queries = build_serpapi_queries(criteria, api_key="secret-key")

        self.assertEqual(len(queries), 1)
        self.assertEqual(queries[0].parser, "serpapi")
        self.assertIn("api_key=secret-key", queries[0].url)
        self.assertNotIn("secret-key", queries[0].query)

    def test_parse_serpapi_results_extracts_candidates(self):
        candidates = parse_serpapi_results(SERPAPI_JSON, platform="JobStreet", location="Kuala Lumpur", limit=5)

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].title, "BI Developer")
        self.assertEqual(candidates[0].company, "HCLTech")
        self.assertIn("Power BI", candidates[0].description)

    def test_parse_linkedin_jobs_extracts_public_job_cards(self):
        candidates = parse_linkedin_jobs(LINKEDIN_HTML, location="Kuala Lumpur", limit=5)

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].title, "Power BI Developer")
        self.assertEqual(candidates[0].company, "HCLTech")
        self.assertIn("Power BI Developer", candidates[0].description)
        self.assertEqual(candidates[0].platform, "LinkedIn")

    def test_parse_duckduckgo_results_extracts_candidates(self):
        candidates = parse_duckduckgo_results(
            DUCKDUCKGO_HTML,
            platform="LinkedIn",
            location="Kuala Lumpur",
            limit=2,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].title, "BI Developer")
        self.assertEqual(candidates[0].company, "Acme")
        self.assertIn("Power BI", candidates[0].description)

    def test_parse_duckduckgo_results_skips_non_job_platform_noise(self):
        candidates = parse_duckduckgo_results(
            NOISY_HTML,
            platform="LinkedIn",
            location="Kuala Lumpur",
            limit=2,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].title, "BI Developer")
        self.assertNotIn("course", candidates[0].source_url)

    def test_run_public_search_scores_and_adds_results_to_queue(self):
        preferences = {
            "target_roles": ["BI Developer", "Data Engineer"],
            "target_locations": ["Kuala Lumpur"],
            "primary_keywords": ["Power BI", "BigQuery"],
            "bonus_keywords": ["Python", "Airflow"],
            "minimum_score_to_apply": 90,
        }
        criteria = SearchCriteria(
            title_terms=("BI Developer", "Data Engineer"),
            description_terms=("Power BI", "BigQuery"),
            location="Kuala Lumpur",
            platforms=("LinkedIn",),
            max_results=2,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            queue = JobQueue(Path(tmpdir) / "jobs.db")
            summary = run_public_search(criteria, preferences, queue, fetcher=lambda url: LINKEDIN_HTML)
            jobs = queue.list_jobs()

        self.assertEqual(summary.checked, 2)
        self.assertEqual(summary.added, 2)
        self.assertEqual(summary.duplicates, 0)
        self.assertEqual(len(jobs), 2)
        self.assertTrue(any("Added Power BI Developer" in line for line in summary.logs))

    def test_run_public_search_uses_serpapi_when_key_is_available(self):
        preferences = {
            "target_roles": ["Data Analyst"],
            "target_locations": ["Kuala Lumpur"],
            "primary_keywords": ["BigQuery"],
            "minimum_score_to_apply": 90,
        }
        criteria = SearchCriteria(
            title_terms=("Data Analyst",),
            description_terms=("BigQuery",),
            location="Kuala Lumpur",
            platforms=("JobStreet",),
            max_results=1,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            queue = JobQueue(Path(tmpdir) / "jobs.db")
            summary = run_public_search(
                criteria,
                preferences,
                queue,
                fetcher=lambda url: SERPAPI_JSON,
                provider_config=SearchProviderConfig(serpapi_key="secret-key"),
            )

        self.assertEqual(summary.checked, 1)
        self.assertEqual(summary.added, 1)
        self.assertTrue(any("API search JobStreet" in line for line in summary.logs))

    def test_run_public_search_does_not_log_api_key_from_provider_errors(self):
        criteria = SearchCriteria(
            title_terms=("Data Analyst",),
            description_terms=("BigQuery",),
            location="Kuala Lumpur",
            platforms=("JobStreet",),
            max_results=1,
        )

        def failing_fetcher(url):
            raise RuntimeError(f"403 for {url}")

        with tempfile.TemporaryDirectory() as tmpdir:
            queue = JobQueue(Path(tmpdir) / "jobs.db")
            summary = run_public_search(
                criteria,
                {},
                queue,
                fetcher=failing_fetcher,
                provider_config=SearchProviderConfig(serpapi_key="secret-key"),
            )

        self.assertEqual(summary.skipped, 1)
        self.assertNotIn("secret-key", "\n".join(summary.logs))
        self.assertIn("request failed", "\n".join(summary.logs))


if __name__ == "__main__":
    unittest.main()
