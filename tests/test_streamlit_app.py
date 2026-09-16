import unittest
from pathlib import Path

import app
from job_hunter.search import SearchCriteria
from job_hunter.session_workspace import SessionWorkspace


class StreamlitSearchContractTest(unittest.TestCase):
    def test_search_readiness_allows_title_or_description_discovery(self):
        workspace = SessionWorkspace()
        title_only = SearchCriteria(("BI Analyst",), (), "Kuala Lumpur", ("LinkedIn",))
        description_only = SearchCriteria((), ("Power BI",), "Kuala Lumpur", ("LinkedIn",))

        self.assertTrue(app._search_is_ready("Criteria-based search", workspace, title_only)[0])
        self.assertTrue(
            app._search_is_ready("Criteria-based search", workspace, description_only)[0]
        )

    def test_cv_mode_requires_readable_session_cv(self):
        workspace = SessionWorkspace()
        criteria = SearchCriteria(("BI Analyst",), (), "Kuala Lumpur", ("LinkedIn",))

        ready, reason = app._search_is_ready("CV-based search", workspace, criteria)

        self.assertFalse(ready)
        self.assertIn("CV", reason)

    def test_entrypoint_has_fixed_limit_and_no_obsolete_controls(self):
        source = (Path(__file__).resolve().parents[1] / "src" / "app.py").read_text()

        self.assertIn("MAX_UNIQUE_RESULTS", source)
        self.assertNotIn('"Strong-match goal"', source)
        self.assertNotIn('"Maximum jobs in one session"', source)
        self.assertIn('key="stop_search"', source)
        self.assertIn("resolve_company_sources", source)


if __name__ == "__main__":
    unittest.main()
