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

    def test_load_search_provider_config_reads_gemini_settings(self):
        config = load_search_provider_config(
            secrets={
                "GEMINI_API_KEY": "gemini-secret",
                "GEMINI_MODEL": "gemini-test-model",
            },
            environ={},
        )

        self.assertEqual(config.gemini_api_key, "gemini-secret")
        self.assertEqual(config.gemini_model, "gemini-test-model")
        self.assertTrue(config.has_gemini)

    def test_load_search_provider_config_uses_safe_default_gemini_model(self):
        config = load_search_provider_config(secrets={}, environ={})

        self.assertEqual(config.gemini_model, "gemini-3.8-flash")
        self.assertFalse(config.has_gemini)


if __name__ == "__main__":
    unittest.main()
