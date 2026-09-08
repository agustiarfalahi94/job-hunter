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

    def test_today_command_prints_progress_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "jobs.db"
            output = StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "today", "--target", "100"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Daily target: 100", output.getvalue())
        self.assertIn("Remaining today: 100", output.getvalue())

    def test_add_command_can_load_preferences_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "jobs.db"
            prefs_path = Path(tmpdir) / "prefs.yaml"
            prefs_path.write_text(
                """
target_roles:
  - Reporting Analyst
primary_keywords:
  - Power BI
minimum_score_to_apply: 90
""",
                encoding="utf-8",
            )
            output = StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "--db",
                        str(db_path),
                        "--preferences",
                        str(prefs_path),
                        "add",
                        "--title",
                        "Reporting Analyst",
                        "--company",
                        "Acme",
                        "--location",
                        "Kuala Lumpur",
                        "--description",
                        "Power BI dashboards",
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertIn("decision=shortlist", output.getvalue())

    def test_list_command_prints_remarks_when_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "jobs.db"
            prefs_path = Path(tmpdir) / "prefs.yaml"
            prefs_path.write_text(
                """
target_roles:
  - Data Engineer
primary_keywords:
  - Power BI
minimum_score_to_apply: 90
""",
                encoding="utf-8",
            )
            with redirect_stdout(StringIO()):
                main(
                    [
                        "--db",
                        str(db_path),
                        "--preferences",
                        str(prefs_path),
                        "add",
                        "--title",
                        "Customer Support",
                        "--company",
                        "Acme",
                        "--location",
                        "Kuala Lumpur",
                        "--description",
                        "General support tickets",
                    ]
                )
            output = StringIO()
            with redirect_stdout(output):
                exit_code = main(["--db", str(db_path), "list"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Missing primary keyword", output.getvalue())


if __name__ == "__main__":
    unittest.main()
