import tempfile
import unittest
from pathlib import Path

from job_hunter.cv_store import CVStore, format_size


class CVStoreTest(unittest.TestCase):
    def test_saves_replaces_and_removes_current_cv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CVStore(Path(tmpdir) / "private" / "cv")

            self.assertFalse(store.status().exists)

    def test_saves_file_with_original_supported_extension(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CVStore(Path(tmpdir) / "private" / "cv")

            status = store.save_file(b"docx-content", "Resume.DOCX")

            self.assertTrue(status.exists)
            self.assertEqual(status.path.name, "current_cv.docx")
            self.assertEqual(status.size_bytes, 12)

    def test_save_file_clears_previous_extracted_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CVStore(Path(tmpdir) / "private" / "cv")
            store.save_text("old extracted text")

            store.save_file(b"new-doc", "resume.doc")

            self.assertEqual(store.load_text(), "")

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
