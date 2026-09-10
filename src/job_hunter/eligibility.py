"""Shared hard-skip eligibility matching."""

from __future__ import annotations

import re
from typing import Any


LOCAL_ONLY_ALIASES = (
    "local applicant only",
    "local applicants only",
    "local candidate only",
    "local candidates only",
    "locals only",
    "malaysian only",
    "malaysians only",
)


def hard_skip_matches(text: str, configured_keywords: Any) -> tuple[str, ...]:
    """Return configured rules whose normalized phrase or aliases match text."""
    normalized_text = _normalize(text)
    matches: list[str] = []
    for raw_keyword in configured_keywords or ():
        keyword = str(raw_keyword).strip()
        normalized_keyword = _normalize(keyword)
        direct_match = bool(normalized_keyword and normalized_keyword in normalized_text)
        keyword_words = set(normalized_keyword.split())
        local_rule = "only" in keyword_words and any(
            marker in keyword_words
            for marker in ("local", "locals", "malaysian", "malaysians")
        )
        alias_match = local_rule and any(alias in normalized_text for alias in LOCAL_ONLY_ALIASES)
        if (direct_match or alias_match) and keyword not in matches:
            matches.append(keyword)
    return tuple(matches)


def _normalize(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())
