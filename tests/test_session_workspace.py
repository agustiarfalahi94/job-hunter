import unittest

from job_hunter.queue_types import JobInput
from job_hunter.scoring import DEFAULT_WEIGHTS, ScoreResult
from job_hunter.session_workspace import SessionWorkspace, get_session_workspace


class SessionWorkspaceTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
