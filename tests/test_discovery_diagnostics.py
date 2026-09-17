import json
import unittest
from dataclasses import replace

from job_hunter.search import parse_serpapi_results
from job_hunter.search_runner import SearchRunController
from job_hunter.runtime_config import SearchProviderConfig
from test_search_runner import _request, _score


class DiscoveryDiagnosticsTest(unittest.TestCase):
    def run_payload(self, data):
        request = replace(_request(), provider_config=SearchProviderConfig(serpapi_key="private-key"))
        controller = SearchRunController(discovery_fetcher=lambda _: json.dumps(data), page_fetcher=lambda _: "", scorer=_score)
        controller.start(request)
        self.assertTrue(controller.wait(2))
        events, matches = controller.drain()
        return controller.snapshot(), "\n".join(event.message for event in events), matches

    def test_empty_success_explains_no_candidates_not_scored_success(self):
        snapshot, logs, matches = self.run_payload({
            "search_metadata": {"status": "Success"},
            "search_information": {"organic_results_state": "Fully empty"},
            "error": "Google hasn't returned any results for this query.",
        })
        self.assertEqual(snapshot.state, "completed")
        self.assertIn("No jobs discovered", snapshot.message)
        self.assertIn("0 web results", logs)
        self.assertNotIn("Review the scored jobs", snapshot.message)
        self.assertFalse(matches)

    def test_rejected_search_pages_are_counted(self):
        snapshot, logs, _ = self.run_payload({"organic_results": [
            {"title": "Data Analyst jobs", "link": "https://www.linkedin.com/jobs/search/"},
            {"title": "Data Analyst jobs", "link": "https://example.com/jobs/"},
        ]})
        self.assertIn("2 web results", logs)
        self.assertIn("1 eligible job", logs)

    def test_provider_error_does_not_become_empty_success_or_leak_response(self):
        snapshot, logs, matches = self.run_payload({
            "search_metadata": {"status": "Error"},
            "error": "Your account has run out of searches. private-key https://secret.example",
        })
        self.assertEqual(snapshot.state, "failed")
        self.assertIn("SerpAPI search allowance", logs)
        self.assertNotIn("private-key", logs)
        self.assertNotIn("secret.example", logs)
        self.assertFalse(matches)

    def test_parser_rejects_provider_error(self):
        with self.assertRaisesRegex(RuntimeError, "SerpAPI"):
            parse_serpapi_results(json.dumps({"error": "Invalid API key"}), "Indeed", "", 50)

    def test_empty_markers_never_hide_quota_or_authentication_error(self):
        for error in ("Your account has run out of searches", "Invalid API key"):
            with self.subTest(error=error):
                snapshot, _, _ = self.run_payload({
                    "search_metadata": {"status": "Success"},
                    "search_information": {"organic_results_state": "Fully empty"},
                    "error": error,
                })
                self.assertEqual(snapshot.state, "failed")

    def test_legacy_search_continues_after_safe_provider_error(self):
        import tempfile
        from pathlib import Path
        from job_hunter.queue import JobQueue
        from job_hunter.search import run_public_search
        request = _request()
        responses = iter([json.dumps({"error": "Invalid API key private-key"}),
                          json.dumps({"organic_results": []})])
        with tempfile.TemporaryDirectory() as directory:
            queue = JobQueue(Path(directory) / "queue.sqlite")
            summary = run_public_search(request.criteria, {}, queue,
                fetcher=lambda _: next(responses),
                provider_config=SearchProviderConfig(serpapi_key="private-key"))
        self.assertGreater(summary.skipped, 0)
        self.assertIn("authentication", "\n".join(summary.logs))
        self.assertNotIn("private-key", "\n".join(summary.logs))

    def test_indeed_queries_target_individual_vacancies(self):
        from job_hunter.search import SearchCriteria, build_search_queries
        criteria = SearchCriteria(title_terms=("Data Analyst",), description_terms=("Power BI",),
                                  location="Kuala Lumpur", platforms=("Indeed",), posted_within_days=None)
        for query in build_search_queries(criteria):
            self.assertIn("inurl:viewjob", query.query)
            self.assertIn("site:indeed.com.my", query.query)

    def test_indeed_aggregate_results_explain_why_rejected(self):
        request = replace(_request(), criteria=replace(_request().criteria, platforms=("Indeed",)),
                          provider_config=SearchProviderConfig(serpapi_key="test"))
        controller = SearchRunController(discovery_fetcher=lambda _: json.dumps({"organic_results": [
            {"title": "Data Analyst jobs", "link": "https://malaysia.indeed.com/q-data-analyst-l-kuala-lumpur-jobs.html"},
            {"title": "Power BI jobs", "link": "https://evil.example/viewjob?api_key=private-key"},
        ]}))
        controller.start(request)
        self.assertTrue(controller.wait(2))
        events, _ = controller.drain()
        logs = "\n".join(event.message for event in events)
        self.assertIn("not a vacancy page: 1", logs)
        self.assertIn("outside selected source: 1", logs)
        self.assertNotIn("private-key", logs)
