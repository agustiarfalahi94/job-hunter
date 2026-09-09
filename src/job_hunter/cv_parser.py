"""CV text extraction and signal detection."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any


@dataclass(frozen=True)
class CVPage:
    text: str | None

    def extract_text(self) -> str | None:
        return self.text


@dataclass(frozen=True)
class CVSignals:
    primary_matches: tuple[str, ...]
    bonus_matches: tuple[str, ...]

    @property
    def total_matches(self) -> int:
        return len(self.primary_matches) + len(self.bonus_matches)


def extract_cv_text_from_pdf_bytes(content: bytes) -> str:
    if not content:
        return ""
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(content))
    return extract_text_from_pages(reader.pages)


def extract_text_from_pages(pages: Any) -> str:
    chunks = []
    for page in pages:
        text = page.extract_text()
        if text and text.strip():
            chunks.append(text.strip())
    return "\n\n".join(chunks)


def detect_cv_signals(text: str, preferences: dict[str, object]) -> CVSignals:
    return CVSignals(
        primary_matches=_matches(text, preferences.get("primary_keywords", ())),
        bonus_matches=_matches(text, preferences.get("bonus_keywords", ())),
    )


def _matches(text: str, keywords: object) -> tuple[str, ...]:
    normalized = text.casefold()
    return tuple(str(keyword) for keyword in keywords or () if str(keyword).casefold() in normalized)
