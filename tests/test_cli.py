import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from job_hunter.cli import main


class CliTest(unittest.TestCase):
    def test_add_command_scores_and_prints_result(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "jobs.db"
            output = StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "--db",
                        str(db_path),
                        "add",
                        "--title",
                        "Data Engineer",
                        "--company",
                        "Acme",
                        "--location",
                        "Kuala Lumpur",
                        "--description",
                        "SQL Python Airflow BigQuery",
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertIn("created: job_id=1", output.getvalue())

    def test_list_command_accepts_empty_queue(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "jobs.db"
            output = StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "list"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(output.getvalue(), "No jobs in queue.\n")


if __name__ == "__main__":
    unittest.main()
