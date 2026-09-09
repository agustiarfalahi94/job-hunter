import unittest
from unittest.mock import patch

import app


class AppNavigationTest(unittest.TestCase):
    def test_open_automated_page_selects_job_queue(self):
        session_state = {"automated_page": "Search setup"}

        with patch.object(app.st, "session_state", session_state):
            app._open_automated_page("Job queue")

        self.assertEqual(session_state["automated_page"], "Job queue")


if __name__ == "__main__":
    unittest.main()
