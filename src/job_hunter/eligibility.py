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
LOCAL_MARKERS = {"local", "locals", "malaysia", "malaysian", "malaysians"}
PERSON_MARKERS = {
    "applicant",
    "applicants",
    "candidate",
    "candidates",
    "citizen",
    "citizens",
    "national",
    "nationals",
    "resident",
    "residents",
}
REQUIREMENT_MARKERS = {
    "compulsory",
    "essential",
    "exclusively",
    "mandatory",
    "must",
    "only",
    "required",
    "requirement",
}
OPTIONAL_MARKERS = (
    "advantage",
    "not mandatory",
    "not required",
    "optional",
    "plus",
    "preferred",
)


def hard_skip_matches(text: str, configured_keywords: Any) -> tuple[str, ...]:
    """Return configured rules whose normalized phrase or aliases match text."""
    normalized_text = _normalize(text)
    matches: list[str] = []
    for raw_keyword in configured_keywords or ():
        keyword = str(raw_keyword).strip()
        normalized_keyword = _normalize(keyword)
        direct_match = bool(normalized_keyword and normalized_keyword in normalized_text)
        semantic_rule = _is_semantic_rule(normalized_keyword)
        semantic_match = _matches_semantic_rule(text, normalized_keyword)
        fuzzy_match = not semantic_rule and _matches_normalized_terms(
            normalized_text, normalized_keyword
        )
        if (direct_match or semantic_match or fuzzy_match) and keyword not in matches:
            matches.append(keyword)
    return tuple(matches)


def _matches_semantic_rule(text: str, keyword: str) -> bool:
    return any(
        _matches_semantic_clause(_normalize(clause), keyword)
        for clause in re.split(r"[.!?;\n]+", text)
        if clause.strip()
    )


def _matches_semantic_clause(text: str, keyword: str) -> bool:
    keyword_words = set(keyword.split())
    if _is_local_restriction_rule(keyword_words):
        if any(alias in text for alias in LOCAL_ONLY_ALIASES):
            return True
        tokens = text.split()
        for index, token in enumerate(tokens):
            if token not in LOCAL_MARKERS:
                continue
            words = set(tokens[max(0, index - 6):index + 7])
            if words & PERSON_MARKERS and words & REQUIREMENT_MARKERS:
                return True
        return False
    if "mandarin" in keyword_words and keyword_words & REQUIREMENT_MARKERS:
        if "mandarin" not in text.split() or any(marker in text for marker in OPTIONAL_MARKERS):
            return False
        return bool(set(text.split()) & REQUIREMENT_MARKERS)
    return False


def _is_semantic_rule(keyword: str) -> bool:
    words = set(keyword.split())
    return _is_local_restriction_rule(words) or bool(
        "mandarin" in words and words & REQUIREMENT_MARKERS
    )


def _is_local_restriction_rule(words: set[str]) -> bool:
    return bool(
        words & LOCAL_MARKERS
        and (words & PERSON_MARKERS or "only" in words)
        and words & REQUIREMENT_MARKERS
    )


def _matches_normalized_terms(text: str, keyword: str) -> bool:
    keyword_terms = _significant_terms(keyword)
    return bool(len(keyword_terms) >= 2 and keyword_terms <= _significant_terms(text))


def _significant_terms(value: str) -> set[str]:
    ignored = {"a", "an", "be", "for", "in", "is", "of", "the", "to"}
    return {_singularize(word) for word in value.split() if word not in ignored}


def _singularize(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return f"{word[:-3]}y"
    if len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _normalize(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())
