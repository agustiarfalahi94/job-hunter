import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import app
from job_hunter.locations import location_matches, location_search_terms, location_options
from job_hunter.search import SearchCriteria, build_search_queries, build_direct_platform_queries
from job_hunter.scoring import score_job


class LocationScopesTest(unittest.TestCase):
    def test_multiple_cities_match_either_case_insensitively(self):
        targets = ("Kuala Lumpur", "Jakarta")
        self.assertIs(location_matches("JAKARTA, ID", targets), True)
        self.assertIs(location_matches("Kuala Lumpur, MY", targets), True)
        self.assertIs(location_matches("Bangkok, Thailand", targets), False)
        self.assertIs(location_matches("Malaysia", targets), None)

    def test_country_and_regional_scope_use_observed_geography(self):
        for observed in ("Johor Bahru, Malaysia", "Petaling Jaya", "MY", "MYS"):
            self.assertIs(location_matches(observed, ("Malaysia",)), True, observed)
        self.assertIs(location_matches("Jakarta, Indonesia", ("Malaysia",)), False)
        self.assertIs(location_matches("Dili, Timor-Leste", ("ASEAN",)), True)
        self.assertIs(location_matches("Tokyo, JP", ("APAC",)), True)
        self.assertIs(location_matches("Paris, France", ("APAC",)), False)
        self.assertIs(location_matches("Unlisted City", ("Malaysia",)), None)
        self.assertIs(location_matches("", ("ASEAN",)), None)
        self.assertIs(location_matches("Hybrid role in Unlisted City", ("APAC",)), None)

    def test_europe_or_apac_and_global(self):
        self.assertIs(location_matches("Berlin, Germany", ("Europe", "APAC")), True)
        self.assertIs(location_matches("Jakarta, Indonesia", ("Europe", "APAC")), True)
        self.assertIs(location_matches("Lagos, Nigeria", ("Europe", "APAC")), False)
        self.assertIs(location_matches("Lagos, Nigeria", ("Global",)), True)
        self.assertEqual(location_search_terms(("Global", "Jakarta")), ())
        criteria = SearchCriteria(("Analyst",), (), "", ("Indeed",), locations=("Global",))
        self.assertNotIn('"Global"', build_search_queries(criteria)[0].query)

    def test_explicit_country_overrides_ambiguous_city(self):
        self.assertIs(location_matches("Sydney, Nova Scotia, CA", ("APAC",)), False)
        self.assertIs(location_matches("Sydney, Nova Scotia, CA", ("Canada",)), True)
        self.assertIs(location_matches("Selangor, MY", ("Petaling Jaya",)), None)

    def test_legacy_search_shares_discovery_ceiling(self):
        from job_hunter.search import run_public_search
        from unittest.mock import MagicMock
        calls = []
        criteria = SearchCriteria(("Analyst",), ("SQL",), "", ("LinkedIn", "Indeed"), locations=("APAC",))
        run_public_search(criteria, {}, MagicMock(), fetcher=lambda url: calls.append(url) or "")
        self.assertLessEqual(len(calls), 12)

    def test_regions_expand_and_dedupe_without_extra_search_requests(self):
        terms = location_search_terms(("ASEAN", "Malaysia", "malaysia"))
        self.assertIn("Indonesia", terms)
        self.assertIn("Timor-Leste", terms)
        self.assertEqual(terms.count("Malaysia"), 1)
        self.assertIn("APAC", location_options(()))
        self.assertIn("Malaysia", location_options(()))
        criteria = SearchCriteria(("Analyst", "Engineer"), ("Power BI",), "", ("Indeed",), locations=("ASEAN",))
        queries = build_search_queries(criteria)
        self.assertLessEqual(len(queries), 12)
        self.assertIn('("Analyst" OR "Engineer")', queries[0].query)
        self.assertIn('(site:my.indeed.com OR site:indeed.com)', queries[0].query)
        self.assertIn('"Indonesia"', queries[0].query)

    def test_direct_linkedin_uses_individual_locations(self):
        criteria = SearchCriteria(("Analyst",), (), "", ("LinkedIn",), locations=("Kuala Lumpur", "Jakarta"))
        queries = build_direct_platform_queries(criteria)
        self.assertEqual([parse_qs(urlparse(q.url).query)["location"][0] for q in queries], ["Kuala Lumpur", "Jakarta"])
        broad = SearchCriteria(("Analyst",), ("SQL",), "", ("LinkedIn",), locations=("APAC",))
        self.assertLessEqual(len(build_direct_platform_queries(broad)), 12)

    def test_regional_sources_include_non_malaysian_foundit_jobs(self):
        from job_hunter.search import parse_serpapi_results
        import json
        criteria = SearchCriteria(("Analyst",), (), "", ("Foundit",), locations=("Jakarta",))
        self.assertIn("site:foundit.id", build_search_queries(criteria)[0].query)
        candidates = parse_serpapi_results(json.dumps({"organic_results": [{"title": "Analyst", "link": "https://www.foundit.id/job/analyst-example-123"}]}), "Foundit", "", 50)
        self.assertEqual(len(candidates), 1)

    def test_country_and_region_receive_location_score(self):
        for targets in (("Malaysia",), ("ASEAN",), ("Jakarta", "Malaysia")):
            result = score_job({"title": "Other", "location": "Johor Bahru, MY"}, {"target_locations": targets, "remote_policy": []})
            self.assertEqual(result.score, 15)

    def test_old_single_location_settings_migrate_without_data_loss(self):
        state = {"search_settings": {"search_location": "Kuala Lumpur"}}
        with patch.object(app.st, "session_state", state):
            self.assertEqual(app._search_settings()["search_location"], ["Kuala Lumpur"])

    def test_company_regions_dedupe_cities_and_verify_each_country(self):
        from job_hunter.runtime_config import SearchProviderConfig
        with patch.object(app, "_cached_malaysia_cities", return_value=("Kuala Lumpur", "Petaling Jaya")), patch.object(app, "_lookup_company", return_value="found") as lookup:
            results = app._lookup_company_for_locations("Deloitte", ("Kuala Lumpur", "Malaysia", "Jakarta"), SearchProviderConfig(gemini_api_key="test"))
        self.assertEqual(results, ("found", "found"))
        self.assertEqual([call.args[1] for call in lookup.call_args_list], ["Malaysia", "Indonesia"])

    def test_company_lookup_budget_prevents_calls_before_validation(self):
        from job_hunter.source_validation import resolve_company_sources
        calls = []
        _, errors = resolve_company_sources(["Deloitte", "Other", "Another"], has_api_search=True,
                                            lookup=lambda name: calls.append(name), lookup_regions=2)
        self.assertTrue(errors)
        self.assertEqual(calls, [])

    def test_company_lookup_combines_verified_regional_hosts(self):
        from types import SimpleNamespace
        from job_hunter.source_validation import resolve_company_sources
        found = [SimpleNamespace(hostname="jobs.example.com", site_filter="site:jobs.example.com"),
                 SimpleNamespace(hostname="careers.example.id", site_filter="site:careers.example.id")]
        sources, errors = resolve_company_sources(["Example"], has_api_search=True, lookup=lambda _: found, lookup_regions=2)
        self.assertFalse(errors)
        self.assertEqual(len(sources), 2)


if __name__ == "__main__":
    unittest.main()
