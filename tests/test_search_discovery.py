import unittest

from job_hunter.search import (
    SearchCriteria,
    build_direct_platform_queries,
    build_search_queries,
    build_serpapi_queries,
    parse_serpapi_results,
)


class SearchDiscoveryTest(unittest.TestCase):
    def test_custom_source_results_must_stay_on_the_selected_host(self):
        payload = """
        {"organic_results": [
          {"title": "BI Analyst - Acme", "link": "https://unrelated.example/jobs/1"},
          {"title": "BI Analyst - Acme", "link": "https://careers.acme.example/jobs/1"}
        ]}
        """

        candidates = parse_serpapi_results(
            payload, "careers.acme.example", "Kuala Lumpur", 10
        )

        self.assertEqual(
            [job.source_url for job in candidates],
            ["https://careers.acme.example/jobs/1"],
        )

    def test_serpapi_queries_discover_by_title_or_description_separately(self):
        criteria = SearchCriteria(
            title_terms=("Data Analyst",),
            description_terms=("Power BI",),
            location="Kuala Lumpur",
            platforms=("LinkedIn",),
            posted_within_days=30,
        )

        queries = build_serpapi_queries(criteria, "secret")

        self.assertEqual({query.signal for query in queries}, {"title", "description"})
        title_query = next(query for query in queries if query.signal == "title")
        description_query = next(
            query for query in queries if query.signal == "description"
        )
        self.assertIn('"Data Analyst"', title_query.query)
        self.assertNotIn('"Power BI"', title_query.query)
        self.assertIn('"Power BI"', description_query.query)
        self.assertNotIn('"Data Analyst"', description_query.query)
        self.assertIn('"Kuala Lumpur"', title_query.query)
        self.assertIn("tbs=qdr%3Am", description_query.url)

    def test_public_fallback_also_splits_title_and_description_signals(self):
        criteria = SearchCriteria(
            title_terms=("BI Developer",),
            description_terms=("SSRS",),
            location="Kuala Lumpur",
            platforms=("LinkedIn", "Indeed"),
        )

        web_queries = build_search_queries(criteria)
        direct_queries = build_direct_platform_queries(criteria)

        self.assertEqual(
            {(query.platform, query.signal) for query in web_queries},
            {
                ("LinkedIn", "title"),
                ("LinkedIn", "description"),
                ("Indeed", "title"),
                ("Indeed", "description"),
            },
        )
        self.assertEqual(
            {query.signal for query in direct_queries}, {"title", "description"}
        )

    def test_query_plan_is_bounded_and_gives_each_source_a_first_signal(self):
        criteria = SearchCriteria(
            title_terms=("Data Analyst",),
            description_terms=("Power BI",),
            location="Kuala Lumpur",
            platforms=("LinkedIn", "JobStreet", "Indeed", "Foundit"),
            custom_domains=(
                "careers.one.example",
                "careers.two.example",
                "careers.three.example",
                "careers.four.example",
                "careers.five.example",
            ),
        )

        queries = build_serpapi_queries(criteria, "secret")

        self.assertLessEqual(len(queries), 12)
        first_signal_sources = {
            query.platform for query in queries if query.signal == "title"
        }
        self.assertEqual(len(first_signal_sources), 9)

    def test_parse_serpapi_google_jobs_payload(self):
        payload = """
        {
          "jobs_results": [
            {
              "title": "Data Engineer",
              "company_name": "Tech Corp",
              "location": "Kuala Lumpur, Malaysia",
              "description": "We are seeking a Data Engineer proficient in SQL and Python. Full description text goes here.",
              "via": "via Indeed",
              "apply_options": [
                {"title": "Apply on Indeed", "link": "https://malaysia.indeed.com/viewjob?jk=9e3ad6434cb74fde"}
              ],
              "detected_extensions": {"posted_at": "3 days ago"}
            }
          ]
        }
        """
        candidates = parse_serpapi_results(payload, "Indeed", "Kuala Lumpur", 10)
        self.assertEqual(len(candidates), 1)
        job = candidates[0]
        self.assertEqual(job.title, "Data Engineer")
        self.assertEqual(job.company, "Tech Corp")
        self.assertEqual(job.location, "Kuala Lumpur, Malaysia")
        self.assertEqual(job.source_url, "https://malaysia.indeed.com/viewjob?jk=9e3ad6434cb74fde")
        self.assertEqual(job.description_kind, "full")
        self.assertIn("SQL and Python", job.description)


if __name__ == "__main__":
    unittest.main()
