import ast
import unittest
from pathlib import Path


class AppImportContractTest(unittest.TestCase):
    def test_streamlit_entrypoint_only_imports_stable_app_ui_names(self):
        tree = ast.parse(Path("src/app.py").read_text(encoding="utf-8"))
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "job_hunter.app_ui":
                imported_names.update(alias.name for alias in node.names)

        stable_names = {
            "filter_jobs",
            "jobs_to_rows",
            "provider_status_label",
            "search_summary_to_rows",
            "status_counts",
        }
        self.assertLessEqual(imported_names, stable_names)


if __name__ == "__main__":
    unittest.main()
