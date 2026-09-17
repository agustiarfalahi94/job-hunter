import unittest

from job_hunter.source_validation import resolve_company_sources, validate_custom_sources


class SourceValidationTest(unittest.TestCase):
    def test_punctuated_company_names_are_not_mistaken_for_domains(self):
        from types import SimpleNamespace
        calls = []
        def lookup(name):
            calls.append(name)
            return SimpleNamespace(hostname="company.example.com", site_filter="site:company.example.com")
        _, errors = resolve_company_sources(["J.P. Morgan", "Company Inc."], has_api_search=True, lookup=lookup)
        self.assertEqual(errors, ())
        self.assertEqual(calls, ["J.P. Morgan", "Company Inc."])

    def test_unknown_company_name_can_resolve_to_verified_career_path(self):
        from types import SimpleNamespace
        sources, errors = resolve_company_sources(["deloitte"], has_api_search=True,
            lookup=lambda name: SimpleNamespace(hostname="jobs.deloitte.com", site_filter="site:jobs.deloitte.com/sea/go/Malaysia"))
        self.assertEqual(errors, ())
        self.assertEqual(sources[0].hostname, "jobs.deloitte.com")
        self.assertEqual(sources[0].site_filter, "site:jobs.deloitte.com/sea/go/Malaysia")

    def test_over_limit_company_names_never_trigger_provider_lookup(self):
        def unexpected_lookup(name):
            self.fail("Provider lookup must not run above the source limit")
        sources, errors = resolve_company_sources([f"Company {i}" for i in range(6)], has_api_search=True, lookup=unexpected_lookup)
        self.assertEqual(sources, ())
        self.assertEqual(errors, ("Select at most 5 company career sites.",))

    def test_company_named_url_still_undergoes_url_validation(self):
        sources, errors = resolve_company_sources(["http://accenture.com/jobs"], has_api_search=True)
        self.assertEqual(sources, ())
        self.assertEqual(len(errors), 1)

    def test_normalizes_https_url_and_domain_to_one_source(self):
        sources, errors = validate_custom_sources(
            ["careers.example.com", "https://careers.example.com/jobs"],
            has_api_search=True,
        )

        self.assertEqual(errors, ())
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].hostname, "careers.example.com")
        self.assertEqual(sources[0].site_filter, "site:careers.example.com")

    def test_rejects_unsafe_or_malformed_sources(self):
        sources, errors = validate_custom_sources(
            [
                "http://careers.example.com/jobs",
                "https://user:pass@careers.example.com/jobs",
                "localhost",
                "127.0.0.1",
                "10.0.0.8",
                "not a domain",
            ],
            has_api_search=True,
        )

        self.assertEqual(sources, ())
        self.assertEqual(len(errors), 6)

    def test_custom_sources_require_serpapi(self):
        sources, errors = validate_custom_sources(
            ["careers.example.com"], has_api_search=False
        )

        self.assertEqual(sources, ())
        self.assertEqual(
            errors, ("Additional platform domains require SerpAPI search.",)
        )

    def test_limits_custom_sources_to_five(self):
        values = [f"careers{i}.example.com" for i in range(6)]

        sources, errors = validate_custom_sources(values, has_api_search=True)

        self.assertEqual(len(sources), 5)
        self.assertIn("Only the first 5 additional domains are used.", errors)

    def test_company_source_names_resolve_without_exact_case(self):
        sources, errors = resolve_company_sources(
            ["accenture", "Prudential Malaysia"], has_api_search=True
        )

        self.assertEqual(errors, ())
        self.assertEqual(
            tuple(source.hostname for source in sources),
            ("careers.accenture.com", "prudential.com.my"),
        )

    def test_company_source_names_allow_friendly_variations(self):
        sources, errors = resolve_company_sources(
            ["Accenture Malaysia careers", "HCL Tech"], has_api_search=True
        )

        self.assertEqual(errors, ())
        self.assertEqual(
            tuple(source.hostname for source in sources),
            ("careers.accenture.com", "hcltech.com"),
        )

    def test_company_source_selector_also_accepts_public_domains(self):
        sources, errors = resolve_company_sources(
            ["jobs.example.com"], has_api_search=True
        )

        self.assertEqual(errors, ())
        self.assertEqual(tuple(source.hostname for source in sources), ("jobs.example.com",))


if __name__ == "__main__":
    unittest.main()
