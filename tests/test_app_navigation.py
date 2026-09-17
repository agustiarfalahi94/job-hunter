import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import app
from job_hunter.matching import MatchResult
from job_hunter.queue import JobRecord
from job_hunter.queue_types import JobInput
from job_hunter.search_runner import RunSnapshot, SearchRunController
from job_hunter.session_workspace import SessionWorkspace, WORKSPACE_KEY
from streamlit.testing.v1 import AppTest


class AppNavigationTest(unittest.TestCase):
    def test_terminal_fragment_refreshes_search_controls_once(self):
        controller = MagicMock()
        controller.drain.return_value = ((), ())
        controller.snapshot.return_value = RunSnapshot(run_id="finished-run", state="completed")
        with patch.object(app, "st") as st, patch.object(app, "_get_controller", return_value=controller):
            st.session_state = {}
            st.columns.return_value = (MagicMock(), MagicMock())
            st.button.return_value = False
            render = app._render_run_fragment.__wrapped__
            render(SessionWorkspace())
            render(SessionWorkspace())
            st.rerun.assert_called_once_with(scope="app")

    def test_new_session_starts_with_empty_selected_search_parameters(self):
        app_path = Path(__file__).resolve().parents[1] / "src" / "app.py"
        app_test = AppTest.from_file(str(app_path)).run(timeout=10)
        for widget in app_test.multiselect:
            self.assertEqual(widget.value, [], widget.label)
        self.assertEqual(next(widget for widget in app_test.multiselect if widget.label == "Location").value, [])

    def test_saved_cv_does_not_populate_fresh_search_criteria(self):
        app_path = Path(__file__).resolve().parents[1] / "src" / "app.py"
        app_test = AppTest.from_file(str(app_path))
        workspace = SessionWorkspace()
        workspace.save_cv("test.docx", b"synthetic", "Power BI SQL Azure experience")
        app_test.session_state[WORKSPACE_KEY] = workspace
        app_test.session_state["search_mode"] = "CV-based search"
        app_test.run(timeout=10)
        app_test.segmented_control[0].set_value("Search jobs").run(timeout=10)
        for widget in app_test.multiselect:
            self.assertEqual(widget.value, [], widget.label)
        self.assertIsNotNone(workspace.cv)

    def test_company_lookup_success_is_cached_by_company_and_region(self):
        from job_hunter.company_lookup import CompanySite
        from job_hunter.runtime_config import SearchProviderConfig
        found = CompanySite("Deloitte", "jobs.deloitte.com", "https://jobs.deloitte.com/sea/", "Malaysia", (), "", "test")
        state = {}
        with patch.object(app.st, "session_state", state), patch.object(app, "_company_region", return_value="Malaysia"), patch.object(app, "lookup_company_site", return_value=found) as lookup:
            first = app._lookup_company("Deloitte", "Kuala Lumpur", SearchProviderConfig(gemini_api_key="test"))
            second = app._lookup_company("deloitte", "Petaling Jaya", SearchProviderConfig(gemini_api_key="test"))
        self.assertEqual(first, second)
        self.assertEqual(lookup.call_count, 1)

    def test_company_lookup_failure_does_not_repeat_on_reruns(self):
        from job_hunter.company_lookup import CompanyLookupError
        from job_hunter.runtime_config import SearchProviderConfig
        state = {}
        with patch.object(app.st, "session_state", state), patch.object(app, "_company_region", return_value="Malaysia"), patch.object(app, "lookup_company_site", side_effect=CompanyLookupError("No grounded sources")) as lookup:
            for _ in range(2):
                with self.assertRaisesRegex(CompanyLookupError, "grounded"):
                    app._lookup_company("Deloitte", "Kuala Lumpur", SearchProviderConfig(gemini_api_key="test"))
        self.assertEqual(lookup.call_count, 1)

    def test_custom_search_parameters_survive_queue_navigation(self):
        app_path = Path(__file__).resolve().parents[1] / "src" / "app.py"
        app_test = AppTest.from_file(str(app_path)).run(timeout=10)
        values = {
            "Target job titles": ["Custom Reporting Specialist", "CUSTOM ANALYTICS ENGINEER"],
            "Required description keywords": ["custom reporting suite", "CUSTOM DATA PLATFORM"],
            "Bonus keywords": ["custom workflow", "CUSTOM COLLABORATION"],
            "Hard skip keywords": ["azure", "CUSTOM EXCLUSION"],
            "Platforms to search": ["LinkedIn"],
            "Company career sites": ["Razer"],
            "Location": ["Petaling Jaya", "Jakarta"],
            "Platform application filters": ["Indeed Apply"],
        }
        for label, selected in values.items():
            next(widget for widget in app_test.multiselect if widget.label == label).set_value(selected).run(timeout=10)
        next(widget for widget in app_test.selectbox if widget.label == "Date posted").set_value("Past week").run(timeout=10)
        next(widget for widget in app_test.multiselect if widget.label == "Company career sites").set_value([]).run(timeout=10)
        controller = SearchRunController(discovery_fetcher=lambda _: "", page_fetcher=lambda _: "")
        app_test.session_state["search_controller"] = controller
        next(button for button in app_test.button if button.label == "Run search and score jobs").click().run(timeout=10)
        self.assertTrue(controller.wait(2))
        self.assertEqual(controller.snapshot().state, "completed")
        app_test.run(timeout=10)
        next(widget for widget in app_test.multiselect if widget.label == "Company career sites").set_value(values["Company career sites"]).run(timeout=10)
        app_test.segmented_control[0].set_value("Job queue").run(timeout=10)
        app_test.segmented_control[0].set_value("Search jobs").run(timeout=10)
        for label, selected in values.items():
            self.assertEqual(next(widget for widget in app_test.multiselect if widget.label == label).value, selected, label)
        self.assertEqual(next(widget for widget in app_test.multiselect if widget.label == "Location").value, ["Petaling Jaya", "Jakarta"])
        self.assertEqual(next(widget for widget in app_test.selectbox if widget.label == "Date posted").value, "Past week")
        self.assertEqual(len(app_test.exception), 0)

    def test_criteria_suggestions_are_static_not_extracted_from_cv(self):
        app_path = Path(__file__).resolve().parents[1] / "src" / "app.py"
        app_test = AppTest.from_file(str(app_path)).run(timeout=10)
        labels = ("Target job titles", "Required description keywords", "Bonus keywords", "Hard skip keywords")
        before = {label: list(next(widget for widget in app_test.multiselect if widget.label == label).options) for label in labels}
        workspace = app_test.session_state[WORKSPACE_KEY]
        workspace.save_cv("synthetic.docx", b"synthetic", "Unique CV skill: CUSTOM-CV-ONLY-SKILL")
        next(radio for radio in app_test.radio if radio.key == "search_mode").set_value("CV-based search").run(timeout=10)
        for label in labels:
            widget = next(widget for widget in app_test.multiselect if widget.label == label)
            self.assertEqual(list(widget.options), before[label])
            self.assertEqual(widget.value, [])

    def test_application_job_options_are_ordered_by_numeric_id(self):
        jobs = [JobRecord(id=number, title="BI Analyst", company="Acme", location="KL",
                          description="Power BI", source_url="", score=90,
                          decision="shortlist", status="new") for number in (3, 1, 2)]
        self.assertEqual([job.id for job in app._application_job_options(jobs).values()], [1, 2, 3])

    def test_criteria_mode_hides_profile_without_clearing_saved_cv(self):
        app_path = Path(__file__).resolve().parents[1] / "src" / "app.py"
        app_test = AppTest.from_file(str(app_path))
        workspace = SessionWorkspace()
        workspace.save_cv("test.docx", b"synthetic", "Power BI experience")
        app_test.session_state[WORKSPACE_KEY] = workspace
        app_test.run(timeout=10)
        self.assertEqual(list(app_test.segmented_control[0].options), ["Search jobs", "Job queue"])
        next(radio for radio in app_test.radio if radio.key == "search_mode").set_value(
            "CV-based search"
        ).run(timeout=10)
        self.assertIn("Profile & CV", app_test.segmented_control[0].options)
        self.assertIsNotNone(workspace.cv)

    def test_open_page_selects_job_queue(self):
        session_state = {"page": "Search jobs"}

        with patch.object(app.st, "session_state", session_state):
            app._open_page("Job queue")

        self.assertEqual(session_state["page"], "Job queue")

    def test_posting_editor_saves_date_and_expiry_without_navigation_errors(self):
        from datetime import date
        app_path = Path(__file__).resolve().parents[1] / "src" / "app.py"
        app_test = AppTest.from_file(str(app_path))
        workspace = SessionWorkspace()
        workspace.add_scored_job(JobInput("BI Analyst", location="Kuala Lumpur", source_url="https://malaysia.indeed.com/viewjob?jk=123"),
                                 MatchResult(95, "shortlist", ("Relevant",), (), "Gemini", "test", False))
        app_test.session_state[WORKSPACE_KEY] = workspace
        app_test.session_state["page"] = "Job queue"
        app_test.run(timeout=10)
        app_test.date_input[0].set_value(date(2026, 9, 2))
        next(widget for widget in app_test.selectbox if widget.label == "Expiry").set_value("expired")
        next(button for button in app_test.button if button.label == "Save posting details").click().run(timeout=10)
        self.assertEqual(len(app_test.exception), 0)
        self.assertEqual(workspace.list_jobs()[0].posted_date, "2026-09-02")
        self.assertEqual(workspace.list_jobs()[0].availability, "expired")
        next(widget for widget in app_test.segmented_control if widget.label == "Applications").set_value("All").run(timeout=10)
        self.assertEqual(len(app_test.date_input), 1)
        app_test.segmented_control[0].set_value("Search jobs").run(timeout=10)
        app_test.segmented_control[0].set_value("Job queue").run(timeout=10)
        self.assertEqual(workspace.list_jobs()[0].posted_date, "2026-09-02")
        self.assertEqual(len(app_test.exception), 0)

    def test_streamlit_app_has_one_optional_cv_search_workflow(self):
        app_path = Path(__file__).resolve().parents[1] / "src" / "app.py"
        app_test = AppTest.from_file(str(app_path))

        app_test.run(timeout=10)

        self.assertEqual(list(app.PAGES), ["Profile & CV", "Search jobs", "Job queue"])
        self.assertEqual(len(app_test.exception), 0)
        self.assertEqual(len(app_test.segmented_control), 1)
        self.assertEqual(list(app_test.segmented_control[0].options), ["Search jobs", "Job queue"])

    def test_search_jobs_is_available_without_a_cv(self):
        app_path = Path(__file__).resolve().parents[1] / "src" / "app.py"
        app_test = AppTest.from_file(str(app_path)).run(timeout=10)

        app_test.segmented_control[0].set_value("Search jobs").run(timeout=10)

        self.assertEqual(len(app_test.exception), 0)
        search_button = next(
            button for button in app_test.button if button.label == "Run search and score jobs"
        )
        self.assertTrue(search_button.disabled)
        next(widget for widget in app_test.multiselect if widget.label == "Target job titles").set_value(["Data Analyst"]).run(timeout=10)
        next(widget for widget in app_test.multiselect if widget.label == "Platforms to search").set_value(["LinkedIn"]).run(timeout=10)
        next(widget for widget in app_test.multiselect if widget.label == "Location").set_value(["Kuala Lumpur"]).run(timeout=10)
        self.assertFalse(next(button for button in app_test.button if button.label == "Run search and score jobs").disabled)
        stop_button = next(button for button in app_test.button if button.label == "Stop search")
        self.assertTrue(stop_button.disabled)

    def test_profile_has_a_button_that_opens_search_jobs(self):
        app_path = Path(__file__).resolve().parents[1] / "src" / "app.py"
        source = app_path.read_text(encoding="utf-8")

        self.assertIn('"Continue to Search jobs"', source)
        self.assertIn('args=("Search jobs",)', source)

    def test_removing_cv_rotates_uploader_key_and_clears_widget_value(self):
        workspace = SessionWorkspace()
        workspace.save_cv("candidate.pdf", b"content", "Power BI experience")
        session_state = {
            "cv_upload_revision": 2,
            "cv_upload_2": object(),
        }

        with patch.object(app.st, "session_state", session_state):
            app._remove_saved_cv(workspace)

        self.assertIsNone(workspace.cv)
        self.assertEqual(session_state["cv_upload_revision"], 3)
        self.assertNotIn("cv_upload_2", session_state)
        self.assertEqual(app._cv_upload_key(session_state), "cv_upload_3")

    def test_completed_partial_search_renders_as_full_terminal_progress(self):
        snapshot = RunSnapshot(
            state="completed",
            discovered=16,
            checked=16,
            completed=7,
            skipped=9,
            message="Search complete.",
        )

        value, label = app._run_progress(snapshot)

        self.assertEqual(value, 100)
        self.assertEqual(
            label,
            "16 jobs checked - Search complete (50-job maximum).",
        )

    def test_review_queue_button_leaves_search_fragment(self):
        app_path = Path(__file__).resolve().parents[1] / "src" / "app.py"
        app_test = AppTest.from_file(str(app_path))
        workspace = SessionWorkspace()
        workspace.add_scored_job(
            JobInput(
                title="BI Developer",
                company="Acme",
                location="Kuala Lumpur",
                description="Power BI reporting role",
                source_url="https://example.com/jobs/1",
            ),
            MatchResult(
                score=95,
                decision="shortlist",
                reasons=("Relevant role",),
                remarks=(),
                engine="Gemini",
                model="gemini-test",
                limited=False,
            ),
        )
        app_test.session_state[WORKSPACE_KEY] = workspace
        app_test.run(timeout=10)
        app_test.segmented_control[0].set_value("Search jobs").run(timeout=10)

        review = next(button for button in app_test.button if button.label == "Review Job queue")
        review.click().run(timeout=10)

        self.assertEqual(app_test.segmented_control[0].value, "Job queue")
        self.assertEqual(len(app_test.exception), 0)

    def test_fragment_navigation_requests_full_app_rerun(self):
        session_state = {"page": "Search jobs"}

        with (
            patch.object(app.st, "session_state", session_state),
            patch.object(app.st, "rerun") as rerun,
        ):
            app._navigate_from_fragment("Job queue")

        self.assertEqual(session_state["page"], "Search jobs")
        self.assertEqual(session_state["requested_page"], "Job queue")
        rerun.assert_called_once_with()

    def test_pending_page_request_is_consumed_before_page_widget(self):
        session_state = {"page": "Search jobs", "requested_page": "Job queue"}

        with patch.object(app.st, "session_state", session_state):
            app._consume_page_request()

        self.assertEqual(session_state["page"], "Job queue")
        self.assertNotIn("requested_page", session_state)

    def test_search_jobs_uses_one_unified_criteria_panel(self):
        app_path = Path(__file__).resolve().parents[1] / "src" / "app.py"
        app_test = AppTest.from_file(str(app_path)).run(timeout=10)

        app_test.segmented_control[0].set_value("Search jobs").run(timeout=10)

        labels = [widget.label for widget in app_test.multiselect]
        self.assertEqual(labels.count("Target job titles"), 1)
        self.assertEqual(labels.count("Required description keywords"), 1)
        self.assertEqual(labels.count("Bonus keywords"), 1)
        self.assertEqual(labels.count("Hard skip keywords"), 1)
        self.assertEqual(labels.count("Company career sites"), 1)
        self.assertFalse(
            any(widget.label == "Additional career-site domains" for widget in app_test.text_area)
        )
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
            patch.object(app, "_render_posting_editor"),
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
