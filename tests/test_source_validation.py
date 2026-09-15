import unittest

from job_hunter.source_validation import validate_custom_sources


class SourceValidationTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
