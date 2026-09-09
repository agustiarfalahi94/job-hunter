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

        self.assertNotIn("editable_criteria_defaults", imported_names)
        self.assertNotIn("queue_column_widths", imported_names)


if __name__ == "__main__":
    unittest.main()
