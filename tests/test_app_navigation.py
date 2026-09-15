import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import app
from job_hunter.queue import JobRecord
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
        search_button = next(
            button for button in app_test.button if button.label == "Run search and score jobs"
        )
        self.assertFalse(search_button.disabled)
        stop_button = next(button for button in app_test.button if button.label == "Stop search")
        self.assertTrue(stop_button.disabled)

    def test_profile_has_a_button_that_opens_search_jobs(self):
        app_path = Path(__file__).resolve().parents[1] / "src" / "app.py"
        source = app_path.read_text(encoding="utf-8")

        self.assertIn('"Continue to Search jobs"', source)
        self.assertIn('args=("Search jobs",)', source)

    def test_search_jobs_uses_one_unified_criteria_panel(self):
        app_path = Path(__file__).resolve().parents[1] / "src" / "app.py"
        app_test = AppTest.from_file(str(app_path)).run(timeout=10)

        app_test.segmented_control[0].set_value("Search jobs").run(timeout=10)

        labels = [widget.label for widget in app_test.multiselect]
        self.assertEqual(labels.count("Target job titles"), 1)
        self.assertEqual(labels.count("Required description keywords"), 1)
        self.assertEqual(labels.count("Bonus keywords"), 1)
        self.assertEqual(labels.count("Hard skip keywords"), 1)
        self.assertNotIn("Job title contains", labels)
        self.assertNotIn("Primary strengths / description keywords", labels)
        self.assertFalse(
            any(widget.label == "Maximum jobs in one session" for widget in app_test.slider)
        )
        self.assertFalse(any(widget.label == "Strong-match goal" for widget in app_test.number_input))
        self.assertFalse(any(widget.label == "Session cap" for widget in app_test.number_input))

    def test_cv_mode_requires_a_saved_cv_and_offers_profile_navigation(self):
        app_path = Path(__file__).resolve().parents[1] / "src" / "app.py"
        app_test = AppTest.from_file(str(app_path)).run(timeout=10)

        mode = next(radio for radio in app_test.radio if radio.key == "search_mode")
        mode.set_value("CV-based search").run(timeout=10)
        app_test.segmented_control[0].set_value("Search jobs").run(timeout=10)

        search_button = next(
            button for button in app_test.button if button.label == "Run search and score jobs"
        )
        upload_button = next(button for button in app_test.button if button.label == "Upload CV")
        self.assertTrue(search_button.disabled)
        self.assertFalse(upload_button.disabled)

    def test_removed_workflow_actions_are_not_in_streamlit_entrypoint(self):
        app_path = Path(__file__).resolve().parents[1] / "src" / "app.py"
        source = app_path.read_text(encoding="utf-8")

        self.assertNotIn('"Manual scoring"', source)
        self.assertNotIn('"Export draft"', source)
        self.assertNotIn('"Export packet"', source)
        self.assertNotIn('"Set status"', source)
        self.assertNotIn("use_container_width", source)

    def test_queue_apply_panel_persists_applied_checkbox(self):
        job = JobRecord(
            id=7,
            title="BI Developer",
            company="Acme",
            location="Kuala Lumpur",
            description="Power BI role",
            source_url="https://example.com/jobs/7",
            score=95,
            decision="shortlist",
            status="new",
        )
        queue = MagicMock()
        selected_label = "#7 - BI Developer - Acme"

        with (
            patch.object(app.st, "subheader"),
            patch.object(app.st, "selectbox", return_value=selected_label),
            patch.object(app.st, "checkbox", return_value=True),
            patch.object(app.st, "caption"),
            patch.object(app.st, "link_button"),
            patch.object(app.st, "info"),
            patch.object(app.st, "toast"),
            patch.object(app.st, "rerun") as rerun,
        ):
            app._render_queue_actions(queue, [job])

        queue.update_application_status.assert_called_once_with(7, "applied")
        rerun.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
