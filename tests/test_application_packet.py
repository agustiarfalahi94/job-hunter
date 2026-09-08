import tempfile
import unittest
from pathlib import Path

from job_hunter.application_packet import build_application_packet
from job_hunter.queue import JobQueue
from job_hunter.queue_types import JobInput


class ApplicationPacketTest(unittest.TestCase):
    def test_packet_requires_human_confirmation_by_default(self):
        job = JobInput(
            title="Data Engineer",
            company="Example Analytics",
            location="Remote",
            description="SQL Python Airflow BigQuery plus Kubernetes",
            source_url="https://example.com/jobs/packet",
        )

        packet = build_application_packet(job)

        self.assertFalse(packet.submit_allowed)
        self.assertEqual(packet.mode, "dry-run")
        self.assertIn("Human review required before submission.", packet.review_notes)
        self.assertIn("Job mentions Kubernetes, which is not supported by the public profile.", packet.warnings)

    def test_queue_exports_application_packet_for_job(self):
        preferences = {"target_roles": ["Data Engineer"], "preferred_keywords": ["SQL", "Python"]}
        with tempfile.TemporaryDirectory() as tmpdir:
            queue = JobQueue(Path(tmpdir) / "jobs.db")
            created = queue.add_job(
                JobInput(
                    title="Data Engineer",
                    company="Example Analytics",
                    location="Remote",
                    description="SQL Python pipelines",
                    source_url="https://example.com/jobs/packet",
                ),
                preferences,
            )

            packet_path = queue.export_application_packet(created.job_id, Path(tmpdir) / "packets")
            text = packet_path.read_text(encoding="utf-8")

        self.assertTrue(packet_path.name.startswith("job-1-application-packet"))
        self.assertIn("# Application Packet - Data Engineer", text)
        self.assertIn("Submit allowed: no", text)
        self.assertIn("Source URL: https://example.com/jobs/packet", text)


if __name__ == "__main__":
    unittest.main()
