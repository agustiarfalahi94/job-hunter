import unittest

from job_hunter.search import (
    SearchCriteria,
    build_direct_platform_queries,
    build_search_queries,
    build_serpapi_queries,
)


class SearchDiscoveryTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
