import json
import unittest
from dataclasses import replace
from urllib.parse import parse_qs, urlparse

from job_hunter.runtime_config import SearchProviderConfig
from job_hunter.search import (
    SearchCriteria,
    PlatformQuery,
    auto_advance_serpapi_query,
    build_serpapi_queries,
    next_serpapi_query,
    parse_duckduckgo_results,
    parse_serpapi_results,
)
from job_hunter.search_runner import SearchRunController
from test_search_runner import _request, _score


TARGET = "https://malaysia.indeed.com/viewjob?jk=9e3ad6434cb74fde"


class IndeedCoverageTest(unittest.TestCase):
    def request(self):
        return replace(_request(), criteria=SearchCriteria(("Data Analyst",), ("Power BI",), "Kuala Lumpur", ("Indeed",), posted_within_days=None),
                       provider_config=SearchProviderConfig(serpapi_key="synthetic-key"))

    def test_continuation_preserves_original_secret_query_and_filters(self):
        criteria = replace(self.request().criteria, posted_within_days=30)
        original = build_serpapi_queries(criteria, "original-secret")[0]
        body = {"organic_results": [{"title": "Analyst", "link": TARGET}],
                "serpapi_pagination": {"next": "https://serpapi.com/search.json?start=10&q=changed&api_key=attacker&tbs=changed"}}
        following = next_serpapi_query(original, json.dumps(body))
        actual = parse_qs(urlparse(following.url).query)
        expected = parse_qs(urlparse(original.url).query)
        self.assertEqual(actual, {**expected, "start": ["10"]})
        self.assertNotIn("attacker", following.url)
        self.assertNotIn("num", actual)
        self.assertEqual(following.query, original.query)

    def test_invalid_or_nonadvancing_continuations_are_ignored(self):
        original = build_serpapi_queries(self.request().criteria, "synthetic-key")[0]
        links = ("https://evil.test/search.json?start=10", "https://serpapi.com.evil.test/search.json?start=10",
                 "http://serpapi.com/search.json?start=10", "https://user:password@serpapi.com/search.json?start=10",
                 "https://serpapi.com:444/search.json?start=10", "https://serpapi.com/other?start=10",
                 "https://[broken", "https://serpapi.com/search.json?start=0", "https://serpapi.com/search.json?start=-10",
                 "https://serpapi.com/search.json?start=120", "https://serpapi.com/search.json?start=10&start=20",
                 "https://serpapi.com/search.json?start=1e100", "https://serpapi.com/search.json?start=10#fragment", None, [])
        for link in links:
            payload = json.dumps({"organic_results": [{"title": "Analyst", "link": TARGET}], "serpapi_pagination": {"next": link}})
            with self.subTest(link=link):
                self.assertIsNone(next_serpapi_query(original, payload))
        self.assertIsNone(next_serpapi_query(original, json.dumps({"organic_results": [], "serpapi_pagination": {"next": "https://serpapi.com/search.json?start=10"}})))

    def test_repeated_pages_stop_without_duplicate_matches(self):
        calls = []
        def fetch(url):
            calls.append(url)
            offset = int(parse_qs(urlparse(url).query).get("start", ["0"])[0])
            return json.dumps({"organic_results": [{"title": "Analyst - Kuala Lumpur", "link": TARGET}],
                               "serpapi_pagination": {"next": f"https://serpapi.com/search.json?start={offset + 10}"}})
        controller = SearchRunController(discovery_fetcher=fetch, page_fetcher=lambda _: "", scorer=_score)
        controller.start(self.request())
        self.assertTrue(controller.wait(2))
        self.assertEqual(len(calls), 4)
        self.assertEqual(len(controller.drain()[1]), 1)

    def test_continuation_accepts_variable_result_offsets(self):
        original = build_serpapi_queries(self.request().criteria, "synthetic-key")[0]
        payload = json.dumps({"organic_results": [{"link": f"https://example.test/{index}"} for index in range(9)],
                              "serpapi_pagination": {"next": "https://serpapi.com/search.json?start=9"}})
        following = next_serpapi_query(original, payload)
        self.assertIsNotNone(following)
        self.assertEqual(parse_qs(urlparse(following.url).query)["start"], ["9"])

    def test_distinct_rejected_pages_do_not_hide_later_vacancy(self):
        calls = []
        def fetch(url):
            params = parse_qs(urlparse(url).query)
            offset = int(params.get("start", ["0"])[0])
            calls.append(offset)
            if offset == 20:
                return json.dumps({"organic_results": [{"title": "Data Analyst - Kuala Lumpur", "link": TARGET, "snippet": "Power BI"}]})
            return json.dumps({"organic_results": [{"title": "Browse jobs", "link": f"https://malaysia.indeed.com/jobs?q=category-{offset}"}],
                               "serpapi_pagination": {"next": f"https://serpapi.com/search.json?start={offset + 10}"}})
        controller = SearchRunController(discovery_fetcher=fetch, page_fetcher=lambda _: "", scorer=_score)
        controller.start(self.request())
        self.assertTrue(controller.wait(2))
        self.assertEqual(calls, [0, 0, 10, 10, 20, 20])
        self.assertEqual([match.job.source_url for match in controller.drain()[1]], [TARGET])

    def test_malformed_rejected_link_does_not_abort_other_queries(self):
        calls = []
        def fetch(url):
            calls.append(url)
            rows = [{"link": "https://[broken"}] if len(calls) == 1 else [{"title": "Data Analyst - Kuala Lumpur", "link": TARGET}]
            return json.dumps({"organic_results": rows})
        controller = SearchRunController(discovery_fetcher=fetch, page_fetcher=lambda _: "", scorer=_score)
        controller.start(self.request())
        self.assertTrue(controller.wait(2))
        self.assertEqual(controller.snapshot().state, "completed")
        self.assertEqual(len(calls), 2)
        self.assertEqual([match.job.source_url for match in controller.drain()[1]], [TARGET])

    def test_pagination_never_exceeds_request_or_candidate_caps(self):
        for count, expected_requests, expected_jobs in ((1, 12, 12), (10, 9, 50)):
            calls = []
            def fetch(url):
                calls.append(url)
                offset = int(parse_qs(urlparse(url).query).get("start", ["0"])[0])
                first = len(calls) if count == 1 else offset
                rows = [{"title": f"Analyst {first + index} - Kuala Lumpur", "link": f"https://malaysia.indeed.com/viewjob?jk=synthetic-{first + index}"} for index in range(count)]
                return json.dumps({"organic_results": rows, "serpapi_pagination": {"next": f"https://serpapi.com/search.json?start={offset + 10}"}})
            with self.subTest(count=count):
                controller = SearchRunController(discovery_fetcher=fetch, page_fetcher=lambda _: "", scorer=_score)
                controller.start(self.request())
                self.assertTrue(controller.wait(3))
                snapshot = controller.snapshot()
                self.assertEqual(snapshot.discovery_requests, expected_requests)
                self.assertEqual(snapshot.discovered, expected_jobs)
                self.assertEqual(snapshot.completed, expected_jobs)
                self.assertLessEqual(snapshot.page_fetches, 50)

    def test_cancellation_prevents_continuation_fetch(self):
        calls = []
        def fetch(url):
            calls.append(url)
            controller.cancel()
            return json.dumps({"organic_results": [{"title": "Analyst", "link": TARGET}],
                               "serpapi_pagination": {"next": "https://serpapi.com/search.json?start=10"}})
        controller = SearchRunController(discovery_fetcher=fetch, page_fetcher=lambda _: "", scorer=_score)
        controller.start(self.request())
        self.assertTrue(controller.wait(2))
        self.assertEqual(len(calls), 1)
        self.assertEqual(controller.snapshot().state, "cancelled")

    def test_public_fallback_uses_the_same_indeed_title_fields(self):
        html = f'<a class="result__a" href="{TARGET}">Analyst (SQL - Power BI) - Kuala Lumpur - Indeed.com</a>'
        job = parse_duckduckgo_results(html, "Indeed", "Jakarta", 50)[0]
        self.assertEqual((job.title, job.company, job.location), ("Analyst (SQL - Power BI)", "", "Kuala Lumpur"))

    def test_city_is_not_employer_and_parenthesized_hyphen_is_kept(self):
        titles = (
            ("Reporting Analyst - Kuala Lumpur", "Reporting Analyst", "Kuala Lumpur"),
            ("Senior Software Engineer (Data Visualization - Power BI) - Kuala Lumpur - Indeed.com",
             "Senior Software Engineer (Data Visualization - Power BI)", "Kuala Lumpur"),
            ("Senior Software Engineer (Data Visualization - Power BI)",
             "Senior Software Engineer (Data Visualization - Power BI)", ""),
            ("Analyst - Unknown City - Indeed.com", "Analyst - Unknown City", ""),
        )
        for text, title, location in titles:
            with self.subTest(text=text):
                payload = json.dumps({"organic_results": [{"title": text, "link": TARGET}]})
                job = parse_serpapi_results(payload, "Indeed", "Kuala Lumpur", 50)[0]
                self.assertEqual((job.title, job.company, job.location), (title, "", location))

    def test_later_page_finds_fixture_after_both_initial_signals(self):
        calls = []
        def fetch(url):
            params = parse_qs(urlparse(url).query)
            calls.append((params["q"][0], params.get("start", ["0"])[0]))
            if "start" in params:
                return json.dumps({"organic_results": [{"title": "Senior Data Analyst - Kuala Lumpur", "link": TARGET, "snippet": "Power BI reporting using SQL"}]})
            return json.dumps({"organic_results": [{"title": "Other Analyst - Kuala Lumpur", "link": "https://malaysia.indeed.com/viewjob?jk=first", "snippet": "Power BI"}],
                               "serpapi_pagination": {"next": "https://serpapi.com/search.json?start=10"}})
        request = replace(_request(), criteria=SearchCriteria(("Data Analyst",), ("Power BI",), "Kuala Lumpur", ("Indeed",), posted_within_days=None),
                          provider_config=SearchProviderConfig(serpapi_key="synthetic-key"))
        controller = SearchRunController(discovery_fetcher=fetch, page_fetcher=lambda _: "", scorer=_score)
        controller.start(request)
        self.assertTrue(controller.wait(2))
        _, matches = controller.drain()
        self.assertIn(TARGET, [match.job.source_url for match in matches])
        self.assertEqual([start for _, start in calls], ["0", "0", "10", "10"])
        self.assertEqual(controller.snapshot().discovery_requests, 4)

    def test_auto_advance_advances_by_ten_and_preserves_query(self):
        original = build_serpapi_queries(self.request().criteria, "synthetic-key")[0]
        payload = json.dumps({"organic_results": [
            {"title": f"Analyst {index}", "link": f"{TARGET}-{index}"}
            for index in range(10)
        ]})
        following = auto_advance_serpapi_query(original, payload)
        self.assertIsNotNone(following)
        params = parse_qs(urlparse(following.url).query)
        orig_params = parse_qs(urlparse(original.url).query)
        self.assertEqual(params["start"], ["10"])
        self.assertEqual(params["api_key"], orig_params["api_key"])
        self.assertEqual(params["q"], orig_params["q"])
        self.assertEqual(params["engine"], orig_params["engine"])

    def test_auto_advance_returns_none_when_short_final_invalid_or_capped(self):
        original = build_serpapi_queries(self.request().criteria, "synthetic-key")[0]
        empty_payload = json.dumps({"organic_results": []})
        self.assertIsNone(auto_advance_serpapi_query(original, empty_payload))

        short_payload = json.dumps({"organic_results": [{"title": "Analyst", "link": TARGET}]})
        self.assertIsNone(auto_advance_serpapi_query(original, short_payload))

        explicit_final_payload = json.dumps({
            "organic_results": [
                {"title": f"Analyst {index}", "link": f"{TARGET}-{index}"}
                for index in range(10)
            ],
            "serpapi_pagination": {"current": 1},
        })
        self.assertIsNone(auto_advance_serpapi_query(original, explicit_final_payload))

        invalid_continuation_payload = json.dumps({
            "organic_results": [
                {"title": f"Analyst {index}", "link": f"{TARGET}-{index}"}
                for index in range(10)
            ],
            "serpapi_pagination": {"next": "https://evil.test/search.json?start=10"},
        })
        self.assertIsNone(auto_advance_serpapi_query(original, invalid_continuation_payload))

        error_payload = json.dumps({"error": "SerpAPI could not complete this query."})
        self.assertIsNone(auto_advance_serpapi_query(original, error_payload))

        non_serp = replace(original, parser="duckduckgo")
        valid_payload = json.dumps({"organic_results": [{"title": "Analyst", "link": TARGET}]})
        self.assertIsNone(auto_advance_serpapi_query(non_serp, valid_payload))

        capped = replace(original, url="https://serpapi.com/search.json?engine=google&start=40&api_key=key")
        self.assertIsNone(auto_advance_serpapi_query(capped, valid_payload))

    def test_auto_advance_does_not_apply_google_jobs_offset_pagination(self):
        original = build_serpapi_queries(self.request().criteria, "synthetic-key")[0]
        payload = json.dumps({"jobs_results": [
            {"title": f"Analyst {index}", "apply_options": [{"link": f"{TARGET}-{index}"}]}
            for index in range(10)
        ]})
        following = auto_advance_serpapi_query(original, payload)
        self.assertIsNone(following)

    def test_auto_advance_discovers_up_to_fifty_results_without_pagination_object(self):
        calls = []
        def fetch(url):
            params = parse_qs(urlparse(url).query)
            offset = int(params.get("start", ["0"])[0])
            calls.append(offset)
            # 10 results per page, NO serpapi_pagination key in response
            rows = [
                {"title": f"Analyst {offset + i} - Kuala Lumpur", "link": f"https://malaysia.indeed.com/viewjob?jk=auto-{offset}-{i}"}
                for i in range(10)
            ]
            return json.dumps({"organic_results": rows})

        controller = SearchRunController(discovery_fetcher=fetch, page_fetcher=lambda _: "", scorer=_score)
        controller.start(self.request())
        self.assertTrue(controller.wait(3))
        snapshot = controller.snapshot()
        events, _ = controller.drain()
        self.assertEqual(snapshot.state, "completed")
        self.assertEqual(snapshot.discovered, 50)
        self.assertEqual(snapshot.completed, 50)
        self.assertIn(
            "full page without pagination metadata",
            "\n".join(event.message for event in events),
        )
        # Verify offsets advanced across multiple pages (0, 10, 20, 30, 40)
        self.assertIn(0, calls)
        self.assertIn(10, calls)
        self.assertIn(20, calls)

    def test_auto_advance_stops_when_subsequent_page_empty(self):
        calls = []
        def fetch(url):
            params = parse_qs(urlparse(url).query)
            offset = int(params.get("start", ["0"])[0])
            calls.append(offset)
            if offset == 0:
                rows = [{"title": f"Analyst {i} - Kuala Lumpur", "link": f"https://malaysia.indeed.com/viewjob?jk=first-{i}"} for i in range(10)]
                return json.dumps({"organic_results": rows})
            # Later page has 0 results
            return json.dumps({"organic_results": []})

        controller = SearchRunController(discovery_fetcher=fetch, page_fetcher=lambda _: "", scorer=_score)
        controller.start(self.request())
        self.assertTrue(controller.wait(2))
        snapshot = controller.snapshot()
        self.assertEqual(snapshot.state, "completed")
        self.assertEqual(snapshot.discovered, 10)
        # Should not have attempted page 20, 30, etc.
        self.assertNotIn(20, calls)
        self.assertNotIn(30, calls)


if __name__ == "__main__":
    unittest.main()
