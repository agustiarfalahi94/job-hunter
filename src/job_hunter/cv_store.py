"""Local storage for private CV uploads."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


CV_FILENAME = "current_cv.pdf"
CV_TEXT_FILENAME = "current_cv.txt"


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
        if not self.path.exists():
            return CVStatus(exists=False, path=self.path)
        return CVStatus(exists=True, path=self.path, size_bytes=self.path.stat().st_size)

    def save_pdf(self, content: bytes) -> CVStatus:
        if not content:
            raise ValueError("CV file is empty.")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(content)
        return self.status()

    def remove(self) -> None:
        if self.path.exists():
            self.path.unlink()
        if self.text_path.exists():
            self.text_path.unlink()

    def save_text(self, text: str) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.text_path.write_text(text.strip(), encoding="utf-8")

    def load_text(self) -> str:
        if not self.text_path.exists():
            return ""
        return self.text_path.read_text(encoding="utf-8")


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"
