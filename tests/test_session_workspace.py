import unittest

from job_hunter.queue_types import JobInput
from job_hunter.matching import MatchResult
from job_hunter.scoring import DEFAULT_WEIGHTS, ScoreResult
from job_hunter.session_workspace import SessionWorkspace, get_session_workspace


class SessionWorkspaceTest(unittest.TestCase):
    def test_accept_completed_rejects_stale_run_and_accepts_active_run(self):
        from job_hunter.search_runner import CompletedMatch

        workspace = SessionWorkspace()
        score = MatchResult(90, "shortlist", ("Power BI",), (), "Gemini", "test", False)
        job = JobInput(title="BI Analyst", company="Acme", location="Kuala Lumpur")
        workspace.activate_run("run-b")

        self.assertFalse(workspace.accept_completed(CompletedMatch("run-a", job, score)))
        self.assertTrue(workspace.accept_completed(CompletedMatch("run-b", job, score)))
        self.assertEqual(len(workspace.list_jobs()), 1)

    def test_workspaces_do_not_share_private_state(self):
        first = SessionWorkspace()
        second = SessionWorkspace()
        first.save_cv("cv.docx", b"doc", "Power BI")
        first.add_scored_job(
            JobInput(
                title="BI Analyst",
                company="Acme",
                location="Kuala Lumpur",
                description="Power BI",
                source_url="https://example.com/jobs/1",
            ),
            ScoreResult(90, "shortlist", ("Power BI",), (), DEFAULT_WEIGHTS),
        )

        self.assertIsNotNone(first.cv)
        self.assertIsNone(second.cv)
        self.assertEqual(second.list_jobs(), [])

    def test_replacing_and_removing_cv_clear_only_cv_cache_entries(self):
        workspace = SessionWorkspace()
        result = ScoreResult(90, "shortlist", ("Power BI",), (), DEFAULT_WEIGHTS)
        workspace.score_cache["cv:old"] = result
        workspace.score_cache["criteria:keep"] = result

        workspace.save_cv("cv.pdf", b"pdf", "SSRS")

        self.assertNotIn("cv:old", workspace.score_cache)
        self.assertIn("criteria:keep", workspace.score_cache)
        workspace.remove_cv()
        self.assertIsNone(workspace.cv)

    def test_get_session_workspace_reuses_only_the_given_state(self):
        first_state: dict[str, object] = {}
        second_state: dict[str, object] = {}

        first = get_session_workspace(first_state)
        again = get_session_workspace(first_state)
        second = get_session_workspace(second_state)

        self.assertIs(first, again)
        self.assertIsNot(first, second)

    def test_confident_cross_source_duplicate_retains_only_primary_url(self):
        workspace = SessionWorkspace()
        score = MatchResult(
            91,
            "shortlist",
            ("Power BI experience matches",),
            (),
            "Gemini",
            "gemini-2.5-flash",
            False,
        )
        foundit = JobInput(
            title="Senior BI Analyst",
            company="Example Bank",
            location="Kuala Lumpur",
            description="Power BI reporting",
            source_url="https://www.foundit.my/job/senior-bi-analyst-456789",
            platform="Foundit",
        )
        linkedin = JobInput(
            title="Senior BI Analyst",
            company="Example Bank",
            location="Kuala Lumpur",
            description="Power BI reporting",
            source_url="https://www.linkedin.com/jobs/view/123456",
            platform="LinkedIn",
        )

        first = workspace.add_scored_job(foundit, score)
        second = workspace.add_scored_job(linkedin, score)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        job = workspace.list_jobs()[0]
        self.assertEqual(job.source_url, foundit.source_url)
        self.assertFalse(hasattr(job, "sources"))

    def test_apply_redirect_alone_does_not_merge_distinct_vacancies(self):
        workspace = SessionWorkspace()
        score = ScoreResult(80, "review", ("Relevant role",), (), DEFAULT_WEIGHTS)
        shared_apply = "https://www.linkedin.com/jobs/view/123456"
        workspace.add_scored_job(
            JobInput(
                title="BI Analyst",
                company="Acme",
                location="Kuala Lumpur",
                source_url="https://www.foundit.my/job/bi-analyst-111",
                apply_url=shared_apply,
                platform="Foundit",
            ),
            score,
        )
        second = workspace.add_scored_job(
            JobInput(
                title="Data Engineer",
                company="Acme",
                location="Kuala Lumpur",
                source_url="https://www.foundit.my/job/data-engineer-222",
                apply_url=shared_apply,
                platform="Foundit",
            ),
            score,
        )

        self.assertTrue(second.created)
        self.assertEqual(len(workspace.list_jobs()), 2)

    def test_manual_application_record_survives_source_consolidation(self):
        workspace = SessionWorkspace()
        score = ScoreResult(90, "shortlist", ("Power BI",), (), DEFAULT_WEIGHTS)
        first = JobInput(
            title="BI Analyst",
            company="Example Bank",
            location="Kuala Lumpur",
            source_url="https://www.foundit.my/job/bi-analyst-111",
            platform="Foundit",
        )
        second = JobInput(
            title="BI Analyst",
            company="Example Bank",
            location="Kuala Lumpur",
            source_url="https://www.linkedin.com/jobs/view/222",
            platform="LinkedIn",
        )
        job_id = workspace.add_scored_job(first, score).job_id
        workspace.update_application_status(job_id, "applied")

        workspace.add_scored_job(second, score)

        job = workspace.list_jobs()[0]
        self.assertEqual(job.application_status, "applied")
        self.assertTrue(job.application_recorded_at)
        self.assertEqual(
            job.application_evidence,
            "Marked manually by the user; not verified with the job platform.",
        )
        self.assertEqual(job.source_url, first.source_url)


if __name__ == "__main__":
    unittest.main()
