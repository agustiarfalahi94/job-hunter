import unittest
from pathlib import Path


class AppStorageBoundaryTest(unittest.TestCase):
    def test_streamlit_entrypoint_uses_session_workspace_not_disk_stores(self):
        source = (Path(__file__).resolve().parents[1] / "src" / "app.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("JobQueue(DB_PATH)", source)
        self.assertNotIn("CVStore(CV_STORAGE_DIR)", source)
        self.assertIn("get_session_workspace(st.session_state)", source)


if __name__ == "__main__":
    unittest.main()
