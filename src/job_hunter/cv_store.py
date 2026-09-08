"""Local storage for private CV uploads."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


CV_FILENAME = "current_cv.pdf"


@dataclass(frozen=True)
class CVStatus:
    exists: bool
    path: Path
    size_bytes: int = 0


class CVStore:
    def __init__(self, storage_dir: Path | str) -> None:
        self.storage_dir = Path(storage_dir)
        self.path = self.storage_dir / CV_FILENAME

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


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"
