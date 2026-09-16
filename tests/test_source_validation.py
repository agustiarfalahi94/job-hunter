import unittest

from job_hunter.source_validation import resolve_company_sources, validate_custom_sources


class SourceValidationTest(unittest.TestCase):
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
