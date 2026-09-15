import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from job_hunter.queue import JobQueue
from job_hunter.runtime_config import SearchProviderConfig
from job_hunter.search import (
    SearchCriteria,
    SearchProgress,
    build_serpapi_queries,
    build_direct_platform_queries,
    build_search_queries,
    extract_job_metadata,
    fetch_job_html,
    normalize_posted_date,
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
      <time class="job-search-card__listdate" datetime="2026-09-09">1 day ago</time>
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
      "snippet": "BigQuery dashboards and Python scripts.",
      "date": "2026-09-08"
    }
  ]
}
"""

CLOSED_LINKEDIN_HTML = """
<html>
  <body>
    <div class="base-search-card">
      <a class="base-card__full-link" href="https://my.linkedin.com/jobs/view/closed">BI Developer</a>
      <h3 class="base-search-card__title">BI Developer</h3>
      <h4 class="base-search-card__subtitle">Old Company</h4>
      <span class="job-search-card__location">Kuala Lumpur, Malaysia</span>
      <span>No longer accepting applications</span>
    </div>
    <div class="base-search-card">
      <a class="base-card__full-link" href="https://my.linkedin.com/jobs/view/open">Data Engineer</a>
      <h3 class="base-search-card__title">Data Engineer</h3>
      <h4 class="base-search-card__subtitle">Current Company</h4>
      <span class="job-search-card__location">Kuala Lumpur, Malaysia</span>
    </div>
  </body>
</html>
"""


class SearchTest(unittest.TestCase):
    def test_fetch_job_html_follows_safe_platform_redirect(self):
        redirect = MagicMock(
            is_redirect=True,
            headers={"Location": "https://my.linkedin.com/jobs/view/123"},
        )
        final = MagicMock(is_redirect=False, text="<main>Date posted: 2 days ago</main>")

        with patch("requests.get", side_effect=[redirect, final]) as request:
            html = fetch_job_html("https://www.linkedin.com/jobs/view/123")

        self.assertEqual(html, "<main>Date posted: 2 days ago</main>")
        self.assertEqual(request.call_count, 2)
        self.assertEqual(request.call_args_list[1].args[0], "https://my.linkedin.com/jobs/view/123")

    def test_fetch_job_html_rejects_untrusted_redirect(self):
        redirect = MagicMock(
            is_redirect=True,
            headers={"Location": "https://untrusted.example/jobs/view/123"},
        )

        with patch("requests.get", return_value=redirect):
            with self.assertRaisesRegex(RuntimeError, "untrusted destination"):
                fetch_job_html("https://www.linkedin.com/jobs/view/123")

    def test_normalize_posted_date_accepts_iso_and_relative_values(self):
        today = date(2026, 9, 10)

        self.assertEqual(normalize_posted_date("2026-09-09", today=today), "2026-09-09")
        self.assertEqual(normalize_posted_date("2 days ago", today=today), "2026-09-08")
        self.assertEqual(normalize_posted_date("1 week ago", today=today), "2026-09-03")
        self.assertEqual(normalize_posted_date("2 months ago", today=today), "2026-07-12")
        self.assertEqual(normalize_posted_date("1 year ago", today=today), "2025-09-10")
        self.assertEqual(normalize_posted_date("Yesterday", today=today), "2026-09-09")
        self.assertEqual(normalize_posted_date("not provided", today=today), "")

    def test_extract_job_metadata_reads_json_ld_date_and_safe_apply_link(self):
        html = """
        <script type="application/ld+json">
          {"@type": "JobPosting", "datePosted": "2026-09-08T09:00:00+08:00"}
        </script>
        <a href="/jobs/123/apply">Apply now</a>
        """

        metadata = extract_job_metadata(html, "https://careers.example.com/jobs/123")

        self.assertEqual(metadata.posted_date, "2026-09-08")
        self.assertEqual(metadata.apply_url, "https://careers.example.com/jobs/123/apply")

    def test_extract_job_metadata_reads_date_posted_meta(self):
        html = '<meta itemprop="datePosted" content="2026-09-08">'

        metadata = extract_job_metadata(html, "https://careers.example.com/jobs/123")

        self.assertEqual(metadata.posted_date, "2026-09-08")

    def test_extract_job_metadata_reads_relative_posted_element(self):
        html = '<div class="posted-time-ago__text">2 months ago</div>'

        metadata = extract_job_metadata(
            html,
            "https://my.linkedin.com/jobs/view/123",
            today=date(2026, 9, 10),
        )

        self.assertEqual(metadata.posted_date, "2026-07-12")

    def test_extract_job_metadata_reads_labeled_visible_posting_age(self):
        html = "<main>Date posted: 1 year ago</main>"

        metadata = extract_job_metadata(
            html,
            "https://my.linkedin.com/jobs/view/123",
            today=date(2026, 9, 10),
        )

        self.assertEqual(metadata.posted_date, "2025-09-10")

    def test_extract_job_metadata_reads_embedded_job_date(self):
        html = '<script>window.__JOB__ = {"postedAt":"2026-09-07"};</script>'

        metadata = extract_job_metadata(html, "https://careers.example.com/jobs/123")

        self.assertEqual(metadata.posted_date, "2026-09-07")

    def test_extract_job_metadata_ignores_unrelated_relative_age(self):
        html = "<main>Our company was founded 1 year ago.</main>"

        metadata = extract_job_metadata(
            html,
            "https://careers.example.com/jobs/123",
            today=date(2026, 9, 10),
        )

        self.assertEqual(metadata.posted_date, "")

    def test_extract_job_metadata_rejects_non_https_apply_link(self):
        html = '<a href="http://careers.example.com/jobs/123/apply">Apply now</a>'

        metadata = extract_job_metadata(html, "https://careers.example.com/jobs/123")

        self.assertEqual(metadata.apply_url, "")

    def test_extract_job_metadata_rejects_unknown_cross_site_apply_link(self):
        html = '<a href="https://unrelated.example/apply/123">Apply now</a>'

        metadata = extract_job_metadata(html, "https://careers.example.com/jobs/123")

        self.assertEqual(metadata.apply_url, "")

    def test_extract_job_metadata_accepts_known_ats_apply_link(self):
        html = '<a href="https://jobs.lever.co/example/123">Apply now</a>'

        metadata = extract_job_metadata(html, "https://careers.example.com/jobs/123")

        self.assertEqual(metadata.apply_url, "https://jobs.lever.co/example/123")

    def test_build_search_queries_targets_selected_platforms(self):
        criteria = SearchCriteria(
            title_terms=("Data Analyst", "BI Developer"),
            description_terms=("Power BI",),
            location="Kuala Lumpur",
            platforms=("LinkedIn", "Company career pages"),
            max_results=50,
        )

        queries = build_search_queries(criteria)

        self.assertEqual(len(queries), 4)
        self.assertIn("site:linkedin.com/jobs", queries[0].query)
        self.assertIn('"Data Analyst" OR "BI Developer"', queries[0].query)
        self.assertNotIn('"Power BI"', queries[0].query)
        self.assertIn('"Kuala Lumpur"', queries[0].query)
        self.assertIn("site:careers.accenture.com", queries[1].query)
        self.assertIn('"Power BI"', queries[2].query)

    def test_build_direct_platform_queries_creates_linkedin_public_url(self):
        criteria = SearchCriteria(
            title_terms=("BI Developer",),
            description_terms=("Power BI",),
            location="Kuala Lumpur",
            platforms=("LinkedIn", "Indeed"),
            max_results=10,
        )

        queries = build_direct_platform_queries(criteria)

        self.assertEqual(len(queries), 2)
        self.assertEqual(queries[0].platform, "LinkedIn")
        self.assertIn("linkedin.com/jobs/search", queries[0].url)
        self.assertIn("BI+Developer", queries[0].url)
        self.assertNotIn("Power+BI", queries[0].url)
        self.assertIn("Power+BI", queries[1].url)

    def test_posting_age_filters_reach_linkedin_and_serpapi_queries(self):
        criteria = SearchCriteria(
            title_terms=("BI Developer",),
            description_terms=("Power BI",),
            location="Kuala Lumpur",
            platforms=("LinkedIn",),
            max_results=10,
            posted_within_days=30,
        )

        direct_query = build_direct_platform_queries(criteria)[0]
        serpapi_query = build_serpapi_queries(criteria, api_key="secret-key")[0]

        self.assertIn("f_TPR=r2592000", direct_query.url)
        self.assertIn("tbs=qdr%3Am", serpapi_query.url)

    def test_build_serpapi_queries_uses_key_without_exposing_it_in_query(self):
        criteria = SearchCriteria(
            title_terms=("Data Analyst",),
            description_terms=("Power BI",),
            location="Kuala Lumpur",
            platforms=("JobStreet",),
            max_results=10,
        )

        queries = build_serpapi_queries(criteria, api_key="secret-key")

        self.assertEqual(len(queries), 2)
        self.assertEqual(queries[0].parser, "serpapi")
        self.assertIn("api_key=secret-key", queries[0].url)
        self.assertNotIn("secret-key", queries[0].query)

    def test_parse_serpapi_results_extracts_candidates(self):
        candidates = parse_serpapi_results(SERPAPI_JSON, platform="JobStreet", location="Kuala Lumpur", limit=5)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].title, "Data Analyst")
        self.assertEqual(candidates[0].company, "Example Bank")
        self.assertIn("BigQuery", candidates[0].description)
        self.assertEqual(candidates[0].posted_date, "2026-09-08")

    def test_parse_serpapi_results_reads_known_nested_posting_date_fields(self):
        payload = """
        {
          "organic_results": [
            {
              "title": "BI Developer - Example One",
              "link": "https://my.linkedin.com/jobs/view/posted-one",
              "snippet": "Power BI role.",
              "rich_snippet": {
                "top": {"detected_extensions": {"posted_at": "Sep 8, 2026"}}
              }
            },
            {
              "title": "Data Analyst - Example Two",
              "link": "https://my.linkedin.com/jobs/view/posted-two",
              "snippet": "SSRS role.",
              "date_posted": "2026-09-07"
            }
          ]
        }
        """

        candidates = parse_serpapi_results(
            payload, platform="LinkedIn", location="Kuala Lumpur", limit=5
        )

        self.assertEqual(
            [candidate.posted_date for candidate in candidates],
            ["2026-09-08", "2026-09-07"],
        )

    def test_parse_linkedin_jobs_extracts_public_job_cards(self):
        candidates = parse_linkedin_jobs(LINKEDIN_HTML, location="Kuala Lumpur", limit=5)

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].title, "Power BI Developer")
        self.assertEqual(candidates[0].company, "HCLTech")
        self.assertIn("Power BI Developer", candidates[0].description)
        self.assertEqual(candidates[0].platform, "LinkedIn")
        self.assertEqual(candidates[0].posted_date, "2026-09-09")

    def test_run_public_search_skips_known_stale_posting(self):
        criteria = SearchCriteria(
            title_terms=("BI Developer",),
            description_terms=("Power BI",),
            location="Kuala Lumpur",
            platforms=("LinkedIn",),
            max_results=1,
            posted_within_days=7,
        )
        search_html = """
        <div class="base-search-card">
          <a class="base-card__full-link" href="https://my.linkedin.com/jobs/view/stale">BI Developer</a>
          <h3 class="base-search-card__title">BI Developer</h3>
          <h4 class="base-search-card__subtitle">Old Company</h4>
          <span class="job-search-card__location">Kuala Lumpur</span>
          <time class="job-search-card__listdate" datetime="2025-09-01">1 year ago</time>
        </div>
        """

        with tempfile.TemporaryDirectory() as tmpdir:
            queue = JobQueue(Path(tmpdir) / "jobs.db")
            summary = run_public_search(
                criteria,
                {},
                queue,
                fetcher=lambda url: search_html,
            )

        self.assertEqual(summary.added, 0)
        self.assertEqual(summary.skipped, 1)
        self.assertTrue(any("older than 7 days" in line for line in summary.logs))

    def test_run_public_search_stores_destination_metadata(self):
        criteria = SearchCriteria(
            title_terms=("BI Developer",),
            description_terms=("Power BI",),
            location="Kuala Lumpur",
            platforms=("LinkedIn",),
            max_results=1,
            posted_within_days=None,
        )
        search_html = """
        <div class="base-search-card">
          <a class="base-card__full-link" href="https://my.linkedin.com/jobs/view/current">BI Developer</a>
          <h3 class="base-search-card__title">BI Developer</h3>
          <h4 class="base-search-card__subtitle">Current Company</h4>
          <span class="job-search-card__location">Kuala Lumpur</span>
        </div>
        """
        detail_html = """
        <script type="application/ld+json">
          {"@type": "JobPosting", "datePosted": "2026-09-10"}
        </script>
        <a href="https://jobs.lever.co/current/123">Apply for this job</a>
        """

        def fetcher(url: str) -> str:
            return search_html if "jobs/search" in url else detail_html

        with tempfile.TemporaryDirectory() as tmpdir:
            queue = JobQueue(Path(tmpdir) / "jobs.db")
            run_public_search(criteria, {}, queue, fetcher=fetcher)
            job = queue.list_jobs()[0]

        self.assertEqual(job.posted_date, "2026-09-10")
        self.assertEqual(job.apply_url, "https://jobs.lever.co/current/123")

    def test_run_public_search_skips_stale_relative_date_from_job_page(self):
        criteria = SearchCriteria(
            title_terms=("BI Developer",),
            description_terms=("Power BI",),
            location="Kuala Lumpur",
            platforms=("LinkedIn",),
            max_results=1,
            posted_within_days=30,
        )
        search_html = """
        <div class="base-search-card">
          <a class="base-card__full-link" href="https://my.linkedin.com/jobs/view/stale-detail">BI Developer</a>
          <h3 class="base-search-card__title">BI Developer</h3>
          <h4 class="base-search-card__subtitle">Old Company</h4>
          <span class="job-search-card__location">Kuala Lumpur</span>
        </div>
        """

        def fetcher(url: str) -> str:
            if "jobs/search" in url:
                return search_html
            return "<main>Date posted: 1 year ago</main>"

        with tempfile.TemporaryDirectory() as tmpdir:
            queue = JobQueue(Path(tmpdir) / "jobs.db")
            summary = run_public_search(criteria, {}, queue, fetcher=fetcher)
            jobs = queue.list_jobs()

        self.assertEqual(summary.added, 0)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(jobs, [])
        self.assertTrue(any("older than 30 days" in line for line in summary.logs))

    def test_run_public_search_logs_when_posting_date_is_unavailable(self):
        criteria = SearchCriteria(
            title_terms=("BI Developer",),
            description_terms=("Power BI",),
            location="Kuala Lumpur",
            platforms=("LinkedIn",),
            max_results=1,
            posted_within_days=30,
        )
        search_html = """
        <div class="base-search-card">
          <a class="base-card__full-link" href="https://my.linkedin.com/jobs/view/no-date">BI Developer</a>
          <h3 class="base-search-card__title">BI Developer</h3>
          <h4 class="base-search-card__subtitle">Current Company</h4>
          <span class="job-search-card__location">Kuala Lumpur</span>
        </div>
        """

        def fetcher(url: str) -> str:
            if "jobs/search" in url:
                return search_html
            return "<main>Power BI reporting role. Applications are open.</main>"

        with tempfile.TemporaryDirectory() as tmpdir:
            queue = JobQueue(Path(tmpdir) / "jobs.db")
            summary = run_public_search(criteria, {}, queue, fetcher=fetcher)

        self.assertEqual(summary.added, 1)
        self.assertTrue(
            any("Posting date unavailable" in line for line in summary.logs)
        )

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

    def test_parse_results_rejects_job_like_paths_on_untrusted_domains(self):
        html = """
        <a class="result__a" href="https://internal.example/jobs/view/789">BI Developer - Fake Company</a>
        <a class="result__snippet">Power BI role in Kuala Lumpur.</a>
        <a class="result__a" href="http://www.linkedin.com/jobs/view/790">BI Developer - Insecure Link</a>
        <a class="result__snippet">Power BI role in Kuala Lumpur.</a>
        """

        candidates = parse_duckduckgo_results(
            html,
            platform="LinkedIn",
            location="Kuala Lumpur",
            limit=2,
        )

        self.assertEqual(candidates, [])

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

    def test_run_public_search_skips_closed_jobs_and_reports_live_progress(self):
        preferences = {
            "target_roles": ["BI Developer", "Data Engineer"],
            "target_locations": ["Kuala Lumpur"],
            "primary_keywords": ["Power BI"],
            "minimum_score_to_apply": 90,
        }
        criteria = SearchCriteria(
            title_terms=("BI Developer", "Data Engineer"),
            description_terms=("Power BI",),
            location="Kuala Lumpur",
            platforms=("LinkedIn",),
            max_results=2,
        )
        progress: list[SearchProgress] = []

        def fetcher(url: str) -> str:
            if "jobs/search" in url:
                return CLOSED_LINKEDIN_HTML
            return "<main>Applications are open</main>"

        with tempfile.TemporaryDirectory() as tmpdir:
            queue = JobQueue(Path(tmpdir) / "jobs.db")
            summary = run_public_search(
                criteria,
                preferences,
                queue,
                fetcher=fetcher,
                progress_callback=progress.append,
            )
            jobs = queue.list_jobs()

        self.assertEqual(summary.checked, 2)
        self.assertEqual(summary.added, 1)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual([job.title for job in jobs], ["Data Engineer"])
        self.assertTrue(any("No longer accepting applications" in event.message for event in progress))
        self.assertEqual(progress[-1].stage, "complete")
        self.assertEqual(progress[-1].checked, 2)

    def test_run_public_search_checks_job_page_for_closed_status_before_adding(self):
        criteria = SearchCriteria(
            title_terms=("BI Developer",),
            description_terms=("Power BI",),
            location="Kuala Lumpur",
            platforms=("LinkedIn",),
            max_results=1,
        )
        search_html = """
        <div class="base-search-card">
          <a class="base-card__full-link" href="https://my.linkedin.com/jobs/view/closed-detail">BI Developer</a>
          <h3 class="base-search-card__title">BI Developer</h3>
          <h4 class="base-search-card__subtitle">Old Company</h4>
          <span class="job-search-card__location">Kuala Lumpur</span>
        </div>
        """

        def fetcher(url: str) -> str:
            if "jobs/search" in url:
                return search_html
            return "<main>No longer accepting applications</main>"

        with tempfile.TemporaryDirectory() as tmpdir:
            queue = JobQueue(Path(tmpdir) / "jobs.db")
            summary = run_public_search(criteria, {}, queue, fetcher=fetcher)
            jobs = queue.list_jobs()

        self.assertEqual(summary.checked, 1)
        self.assertEqual(summary.added, 0)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(jobs, [])
        self.assertTrue(any("Checking availability" in line for line in summary.logs))
        self.assertTrue(any("No longer accepting applications" in line for line in summary.logs))

    def test_run_public_search_excludes_local_only_title_before_queue_insertion(self):
        criteria = SearchCriteria(
            title_terms=("BI Developer",),
            description_terms=("Power BI",),
            location="Kuala Lumpur",
            platforms=("LinkedIn",),
            max_results=1,
            posted_within_days=None,
        )
        search_html = """
        <div class="base-search-card">
          <a class="base-card__full-link" href="https://my.linkedin.com/jobs/view/local-only">BI Developer (Local Applicant Only)</a>
          <h3 class="base-search-card__title">BI Developer (Local Applicant Only)</h3>
          <h4 class="base-search-card__subtitle">Restricted Company</h4>
          <span class="job-search-card__location">Kuala Lumpur</span>
        </div>
        """

        with tempfile.TemporaryDirectory() as tmpdir:
            queue = JobQueue(Path(tmpdir) / "jobs.db")
            summary = run_public_search(
                criteria,
                {"hard_skip_keywords": ["locals/malaysian only"]},
                queue,
                fetcher=lambda url: search_html,
            )
            jobs = queue.list_jobs()

        self.assertEqual(summary.added, 0)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(jobs, [])
        self.assertTrue(any("Hard skip keyword found" in line for line in summary.logs))

    def test_run_public_search_excludes_restriction_found_on_job_page(self):
        criteria = SearchCriteria(
            title_terms=("BI Developer",),
            description_terms=("Power BI",),
            location="Kuala Lumpur",
            platforms=("LinkedIn",),
            max_results=1,
            posted_within_days=None,
        )
        search_html = """
        <div class="base-search-card">
          <a class="base-card__full-link" href="https://my.linkedin.com/jobs/view/restricted-detail">BI Developer</a>
          <h3 class="base-search-card__title">BI Developer</h3>
          <h4 class="base-search-card__subtitle">Restricted Company</h4>
          <span class="job-search-card__location">Kuala Lumpur</span>
        </div>
        """

        def fetcher(url: str) -> str:
            if "jobs/search" in url:
                return search_html
            return "<main>Power BI reporting role. Local applicants only.</main>"

        with tempfile.TemporaryDirectory() as tmpdir:
            queue = JobQueue(Path(tmpdir) / "jobs.db")
            summary = run_public_search(
                criteria,
                {"hard_skip_keywords": ["locals/malaysian only"]},
                queue,
                fetcher=fetcher,
            )
            jobs = queue.list_jobs()

        self.assertEqual(summary.added, 0)
        self.assertEqual(summary.skipped, 1)
        self.assertEqual(jobs, [])
        self.assertTrue(any("Hard skip keyword found" in line for line in summary.logs))

    def test_run_public_search_reports_blocked_availability_check_for_manual_review(self):
        criteria = SearchCriteria(
            title_terms=("BI Developer",),
            description_terms=("Power BI",),
            location="Kuala Lumpur",
            platforms=("LinkedIn",),
            max_results=1,
        )
        search_html = """
        <div class="base-search-card">
          <a class="base-card__full-link" href="https://my.linkedin.com/jobs/view/open-detail">BI Developer</a>
          <h3 class="base-search-card__title">BI Developer</h3>
          <h4 class="base-search-card__subtitle">Current Company</h4>
          <span class="job-search-card__location">Kuala Lumpur</span>
        </div>
        """

        def fetcher(url: str) -> str:
            if "jobs/search" in url:
                return search_html
            return '<form id="challenge-form">Verify you are human</form>'

        with tempfile.TemporaryDirectory() as tmpdir:
            queue = JobQueue(Path(tmpdir) / "jobs.db")
            summary = run_public_search(criteria, {}, queue, fetcher=fetcher)
            jobs = queue.list_jobs()

        self.assertEqual(summary.added, 1)
        self.assertEqual(len(jobs), 1)
        self.assertTrue(any("Availability could not be confirmed" in line for line in summary.logs))

    def test_search_progress_total_respects_the_fifty_job_safety_cap(self):
        criteria = SearchCriteria(
            title_terms=("BI Developer",),
            description_terms=("Power BI",),
            location="Kuala Lumpur",
            platforms=("LinkedIn",),
            max_results=100,
        )
        progress: list[SearchProgress] = []

        with tempfile.TemporaryDirectory() as tmpdir:
            queue = JobQueue(Path(tmpdir) / "jobs.db")
            run_public_search(
                criteria,
                {},
                queue,
                fetcher=lambda url: "<html></html>",
                progress_callback=progress.append,
            )

        self.assertEqual(progress[-1].total, 50)

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

        self.assertEqual(summary.skipped, 2)
        self.assertNotIn("secret-key", "\n".join(summary.logs))
        self.assertIn("request failed", "\n".join(summary.logs))


if __name__ == "__main__":
    unittest.main()
