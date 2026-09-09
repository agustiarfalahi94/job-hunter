"""Local storage for private CV uploads."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


CV_FILENAME = "current_cv.pdf"
CV_TEXT_FILENAME = "current_cv.txt"
SUPPORTED_CV_EXTENSIONS = (".pdf", ".docx", ".doc")


@dataclass(frozen=True)
class CVStatus:
    exists: bool
    path: Path
    size_bytes: int = 0


class CVStore:
    def __init__(self, storage_dir: Path | str) -> None:
        self.storage_dir = Path(storage_dir)
        self.path = self.storage_dir / CV_FILENAME
        self.text_path = self.storage_dir / CV_TEXT_FILENAME

    def status(self) -> CVStatus:
        path = self._current_file_path()
        if path is None:
            return CVStatus(exists=False, path=self.path)
        return CVStatus(exists=True, path=path, size_bytes=path.stat().st_size)

    def save_pdf(self, content: bytes) -> CVStatus:
        return self.save_file(content, CV_FILENAME)

    def save_file(self, content: bytes, filename: str) -> CVStatus:
        if not content:
            raise ValueError("CV file is empty.")
        extension = Path(filename).suffix.casefold()
        if extension not in SUPPORTED_CV_EXTENSIONS:
            raise ValueError(f"Unsupported CV file type: {extension or 'unknown'}")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._remove_saved_files()
        if self.text_path.exists():
            self.text_path.unlink()
        path = self.storage_dir / f"current_cv{extension}"
        path.write_bytes(content)
        return self.status()

    def remove(self) -> None:
        self._remove_saved_files()
        if self.text_path.exists():
            self.text_path.unlink()

    def save_text(self, text: str) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.text_path.write_text(text.strip(), encoding="utf-8")

    def load_text(self) -> str:
        if not self.text_path.exists():
            return ""
        return self.text_path.read_text(encoding="utf-8")

    def _current_file_path(self) -> Path | None:
        for extension in SUPPORTED_CV_EXTENSIONS:
            path = self.storage_dir / f"current_cv{extension}"
            if path.exists():
                return path
        return None

    def _remove_saved_files(self) -> None:
        for extension in SUPPORTED_CV_EXTENSIONS:
            path = self.storage_dir / f"current_cv{extension}"
            if path.exists():
                path.unlink()


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"
