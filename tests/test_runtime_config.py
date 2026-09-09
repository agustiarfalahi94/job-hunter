import unittest

from job_hunter.runtime_config import load_search_provider_config


class RuntimeConfigTest(unittest.TestCase):
    def test_load_search_provider_config_reads_environment_key(self):
        config = load_search_provider_config(environ={"SERPAPI_API_KEY": "env-key"})

        self.assertEqual(config.serpapi_key, "env-key")

    def test_load_search_provider_config_prefers_streamlit_secret_key(self):
        config = load_search_provider_config(
            secrets={"SERPAPI_API_KEY": "secret-key"},
            environ={"SERPAPI_API_KEY": "env-key"},
        )

        self.assertEqual(config.serpapi_key, "secret-key")

    def test_load_search_provider_config_accepts_nested_search_secret(self):
        config = load_search_provider_config(secrets={"search": {"serpapi_api_key": "nested-key"}})

        self.assertEqual(config.serpapi_key, "nested-key")


if __name__ == "__main__":
    unittest.main()
