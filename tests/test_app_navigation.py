import unittest
from pathlib import Path
from unittest.mock import patch

import app
from streamlit.testing.v1 import AppTest


class AppNavigationTest(unittest.TestCase):
    def test_open_page_selects_job_queue(self):
        session_state = {"page": "Search jobs"}

        with patch.object(app.st, "session_state", session_state):
            app._open_page("Job queue")

        self.assertEqual(session_state["page"], "Job queue")

    def test_streamlit_app_has_one_optional_cv_search_workflow(self):
        app_path = Path(__file__).resolve().parents[1] / "src" / "app.py"
        app_test = AppTest.from_file(str(app_path))

        app_test.run(timeout=10)

        self.assertEqual(list(app.PAGES), ["Profile & CV", "Search jobs", "Job queue"])
        self.assertEqual(len(app_test.exception), 0)
        self.assertEqual(len(app_test.segmented_control), 1)
        self.assertEqual(
            list(app_test.segmented_control[0].options),
            ["Profile & CV", "Search jobs", "Job queue"],
        )

    def test_search_jobs_is_available_without_a_cv(self):
        app_path = Path(__file__).resolve().parents[1] / "src" / "app.py"
        app_test = AppTest.from_file(str(app_path)).run(timeout=10)

        app_test.segmented_control[0].set_value("Search jobs").run(timeout=10)

        self.assertEqual(len(app_test.exception), 0)
        self.assertTrue(any("No CV is saved" in item.value for item in app_test.info))
        search_button = next(
            button for button in app_test.button if button.label == "Run search and score jobs"
        )
        self.assertFalse(search_button.disabled)

    def test_removed_workflow_actions_are_not_in_streamlit_entrypoint(self):
        app_path = Path(__file__).resolve().parents[1] / "src" / "app.py"
        source = app_path.read_text(encoding="utf-8")

        self.assertNotIn('"Manual scoring"', source)
        self.assertNotIn('"Export draft"', source)
        self.assertNotIn('"Export packet"', source)
        self.assertNotIn('"Set status"', source)
        self.assertNotIn("use_container_width", source)


if __name__ == "__main__":
    unittest.main()
