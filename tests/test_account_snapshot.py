import json
import unittest

from job_hunter.account_snapshot import SnapshotError, decode_snapshot, encode_snapshot
from job_hunter.matching import MatchResult
from job_hunter.queue_types import JobInput
from job_hunter.session_workspace import SessionWorkspace


OWNER = "a" * 64
SETTINGS = {
    "target_roles": ["Custom analyst"], "primary_keywords": ["Power BI"],
    "bonus_keywords": ["Scrum"], "hard_skip_keywords": ["AZURE"],
    "search_location": ["Kuala Lumpur", "Jakarta"], "search_platforms": ["Indeed"],
    "company_sources": ["Deloitte"], "posting_age": "Any time", "application_filters": [],
    "cv_profile_digest": "a" * 64,
}


def private_workspace():
    workspace = SessionWorkspace()
    workspace.save_cv("synthetic.docx", b"synthetic CV bytes", "Synthetic experience in Power BI")
    workspace.add_scored_job(JobInput("Reporting Analyst", "Synthetic Company", "Kuala Lumpur", "Power BI", "https://malaysia.indeed.com/viewjob?jk=synthetic"),
        MatchResult(95, "shortlist", ("Power BI matches",), (), "Gemini", "synthetic-model", False))
    workspace.update_application_status(1, True)
    workspace.score_cache["do-not-save"] = "private-cache"
    workspace.activate_run("do-not-save-run")
    return workspace


class AccountSnapshotTest(unittest.TestCase):
    def test_cv_settings_and_application_evidence_survive_restart(self):
        original = private_workspace()
        restored = decode_snapshot(OWNER, encode_snapshot(OWNER, original, SETTINGS, "Criteria-based search"))
        self.assertEqual(restored.workspace.cv, original.cv)
        self.assertEqual(restored.workspace.list_jobs(), original.list_jobs())
        self.assertEqual(restored.settings, SETTINGS)
        self.assertEqual(restored.mode, "Criteria-based search")
        self.assertEqual(restored.workspace.score_cache, {})
        self.assertEqual(restored.workspace._active_run_id, "")
        restored.settings["hard_skip_keywords"].append("new")
        self.assertEqual(SETTINGS["hard_skip_keywords"], ["AZURE"])

    def test_duplicate_rediscovery_retains_saved_applied_status(self):
        restored = decode_snapshot(OWNER, encode_snapshot(OWNER, private_workspace(), SETTINGS, "CV-based search"))
        result = restored.workspace.add_scored_job(JobInput("Reporting Analyst", "Synthetic Company", "Kuala Lumpur", "Power BI", "https://malaysia.indeed.com/viewjob?jk=synthetic"), MatchResult(90, "shortlist", (), (), "Gemini", "model", False))
        self.assertFalse(result.created)
        self.assertEqual(restored.workspace.list_jobs()[0].application_status, "applied")
        added = restored.workspace.add_scored_job(JobInput("Another analyst", "Another company", "Jakarta", "SQL", "https://www.linkedin.com/jobs/view/999"), MatchResult(30, "review", (), (), "Deterministic", "", False))
        self.assertEqual(added.job_id, 2)

    def test_removing_cv_persists_without_deleting_history(self):
        workspace = private_workspace()
        workspace.remove_cv()
        restored = decode_snapshot(OWNER, encode_snapshot(OWNER, workspace, SETTINGS, "Criteria-based search"))
        self.assertIsNone(restored.workspace.cv)
        self.assertEqual(restored.workspace.list_jobs()[0].application_status, "applied")

    def test_cache_keys_and_unrelated_settings_are_not_serialized(self):
        payload = encode_snapshot(OWNER, private_workspace(), {**SETTINGS, "api_key": "never-save-key"}, "Criteria-based search")
        for private in ("private-cache", "do-not-save-run", "never-save-key", "api_key"):
            self.assertNotIn(private, payload)

    def test_owner_mismatch_and_unknown_version_fail_closed(self):
        raw = json.loads(encode_snapshot(OWNER, private_workspace(), SETTINGS, "Criteria-based search"))
        for field, value in (("owner_id", "b" * 64), ("version", 999), ("mode", "arbitrary")):
            changed = dict(raw, **{field: value})
            with self.subTest(field=field), self.assertRaises(SnapshotError):
                decode_snapshot(OWNER, json.dumps(changed))

    def test_malformed_records_and_cv_do_not_partially_restore(self):
        for mutate in (
            lambda raw: raw["jobs"][0].update(id=True),
            lambda raw: raw["jobs"][0].update(score=1000),
            lambda raw: raw["jobs"][0].update(application_status="submitted-by-platform"),
            lambda raw: raw["jobs"].append(raw["jobs"][0]),
            lambda raw: raw["cv"].update(content="not-base64"),
            lambda raw: raw["settings"].update(hard_skip_keywords="azure"),
            lambda raw: raw["settings"].update(cv_profile_digest="not-a-digest"),
        ):
            raw = json.loads(encode_snapshot(OWNER, private_workspace(), SETTINGS, "CV-based search"))
            mutate(raw)
            with self.assertRaises(SnapshotError):
                decode_snapshot(OWNER, json.dumps(raw))

    def test_empty_account_round_trip_and_payload_limit(self):
        restored = decode_snapshot(OWNER, encode_snapshot(OWNER, SessionWorkspace(), {}, "Criteria-based search"))
        self.assertIsNone(restored.workspace.cv)
        self.assertEqual(restored.workspace.list_jobs(), [])
        self.assertEqual(restored.settings["target_roles"], [])
        self.assertEqual(restored.settings["cv_profile_digest"], "")
        with self.assertRaises(SnapshotError):
            decode_snapshot(OWNER, "x" * (12 * 1024 * 1024 + 1))

    def test_oversized_cv_is_rejected_for_durable_storage(self):
        workspace = SessionWorkspace()
        workspace.save_cv("synthetic.pdf", b"x" * (5 * 1024 * 1024 + 1), "synthetic")
        with self.assertRaises(SnapshotError):
            encode_snapshot(OWNER, workspace, SETTINGS, "CV-based search")


if __name__ == "__main__":
    unittest.main()
