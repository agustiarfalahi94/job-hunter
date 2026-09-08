import tempfile
import unittest
from pathlib import Path

from job_hunter.cv_store import CVStore, format_size


class CVStoreTest(unittest.TestCase):
    def test_saves_replaces_and_removes_current_cv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CVStore(Path(tmpdir) / "private" / "cv")

            self.assertFalse(store.status().exists)

            first = store.save_pdf(b"%PDF-first")
            self.assertTrue(first.exists)
            self.assertEqual(first.size_bytes, 10)

            second = store.save_pdf(b"%PDF-second-version")
            self.assertTrue(second.exists)
            self.assertEqual(store.path.read_bytes(), b"%PDF-second-version")

            store.remove()

            self.assertFalse(store.status().exists)

    def test_rejects_empty_cv_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CVStore(Path(tmpdir))

            with self.assertRaises(ValueError):
                store.save_pdf(b"")

    def test_formats_cv_file_size(self):
        self.assertEqual(format_size(512), "512 B")
        self.assertEqual(format_size(2048), "2.0 KB")


if __name__ == "__main__":
    unittest.main()
