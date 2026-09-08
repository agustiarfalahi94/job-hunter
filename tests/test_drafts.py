import tempfile
import unittest
from pathlib import Path

from job_hunter.drafts import build_application_draft, unsupported_claim_warnings
from job_hunter.queue import JobInput, JobQueue


class DraftsTest(unittest.TestCase):
    def test_builds_draft_from_supported_profile_evidence(self):
        job = JobInput(
            title="Data Engineer",
            company="Example Analytics",
            location="Kuala Lumpur",
            description="Need SQL, Python, Airflow, Docker, BigQuery, and migration validation.",
        )

        draft = build_application_draft(job)

        self.assertIn("Example Analytics", draft.cover_letter)
        self.assertIn("Data Engineer", draft.cover_letter)
        self.assertIn("BigQuery to MaxCompute data migration", draft.cover_letter)
        self.assertIn("Airflow orchestration", draft.cover_letter)
        self.assertEqual(draft.warnings, ())

    def test_flags_unsupported_claims_in_job_description(self):
        warnings = unsupported_claim_warnings(
            "Must have Kubernetes production ownership and dedicated Linux system administration."
        )

        self.assertIn("Job mentions Kubernetes, which is not supported by the public profile.", warnings)
        self.assertIn(
            "Job mentions dedicated Linux administration, which is not supported by the public profile.",
            warnings,
        )

    def test_exports_draft_for_queued_job(self):
        preferences = {
            "target_roles": ["Data Engineer"],
            "preferred_keywords": ["SQL", "Python", "Airflow", "BigQuery"],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            queue = JobQueue(Path(tmpdir) / "jobs.db")
            created = queue.add_job(
                JobInput(
                    title="Data Engineer",
                    company="Example Analytics",
                    location="Remote",
                    description="SQL Python Airflow BigQuery pipelines",
                ),
                preferences,
            )
            draft_path = queue.export_draft(created.job_id, Path(tmpdir) / "drafts")

            text = draft_path.read_text(encoding="utf-8")

        self.assertTrue(draft_path.name.startswith("job-1-data-engineer"))
        self.assertIn("# Application Draft - Data Engineer", text)
        self.assertIn("Example Analytics", text)


if __name__ == "__main__":
    unittest.main()
