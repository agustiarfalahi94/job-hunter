import tempfile
import unittest
from pathlib import Path

from job_hunter.cv_parser import CVPage, detect_cv_signals, extract_text_from_pages
from job_hunter.cv_store import CVStore


class CVParserTest(unittest.TestCase):
    def test_extract_text_from_pages_joins_non_empty_pdf_page_text(self):
        text = extract_text_from_pages(
            [
                CVPage("Muhamad Agustiar Falahi"),
                CVPage("Power BI, SSRS, BigQuery"),
                CVPage(None),
            ]
        )

        self.assertEqual(text, "Muhamad Agustiar Falahi\n\nPower BI, SSRS, BigQuery")

    def test_detect_cv_signals_returns_primary_and_bonus_matches(self):
        preferences = {
            "primary_keywords": ["Power BI", "SSRS", "BigQuery"],
            "bonus_keywords": ["Python", "Docker", "Airflow"],
        }

        signals = detect_cv_signals("Built Power BI dashboards with Python scripts.", preferences)

        self.assertEqual(signals.primary_matches, ("Power BI",))
        self.assertEqual(signals.bonus_matches, ("Python",))
        self.assertEqual(signals.total_matches, 2)

    def test_cv_store_saves_and_loads_extracted_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CVStore(Path(tmpdir))

            store.save_text("Power BI and BigQuery")

            self.assertEqual(store.load_text(), "Power BI and BigQuery")


if __name__ == "__main__":
    unittest.main()
