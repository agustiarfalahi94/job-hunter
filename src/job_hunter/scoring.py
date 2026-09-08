"""Deterministic v0.1 job scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DEFAULT_WEIGHTS: dict[str, int] = {
    "role": 30,
    "keywords": 40,
    "location": 15,
    "remote_policy": 10,
    "avoid_penalty": 30,
}


@dataclass(frozen=True)
class ScoreResult:
    score: int
    decision: str
    reasons: tuple[str, ...]
    weights: dict[str, int]


def score_job(job: dict[str, Any], preferences: dict[str, Any]) -> ScoreResult:
    text = _job_text(job)
    title = str(job.get("title", ""))
    location = str(job.get("location", ""))
    remote_policy = str(job.get("remote_policy", ""))
    weights = dict(DEFAULT_WEIGHTS)
    score = 0
    reasons: list[str] = []

    matched_role = _first_contains(title, preferences.get("target_roles", ()))
    if matched_role:
        score += weights["role"]
        reasons.append(f"Role title matches target role: {matched_role}")

    preferred_matches = _all_contains(text, preferences.get("preferred_keywords", ()))
    if preferred_matches:
        keyword_total = _count(preferences.get("preferred_keywords", ()))
        keyword_score = round(weights["keywords"] * len(preferred_matches) / keyword_total)
        score += keyword_score
        reasons.append(f"Matched preferred keywords: {', '.join(preferred_matches)}")

    matched_location = _first_contains(location, preferences.get("target_locations", ()))
    if matched_location:
        score += weights["location"]
        reasons.append(f"Location matches preference: {matched_location}")

    remote_preferences = preferences.get("remote_policy", ("Remote", "Hybrid"))
    if remote_policy and _first_contains(remote_policy, remote_preferences):
        score += weights["remote_policy"]
        reasons.append(f"Remote policy is compatible: {remote_policy}")

    avoid_matches = _all_contains(text, preferences.get("avoid_keywords", ()))
    if avoid_matches:
        score -= weights["avoid_penalty"] * len(avoid_matches)
        reasons.append(f"Avoid keywords found: {', '.join(avoid_matches)}")

    final_score = max(0, min(100, score))
    return ScoreResult(
        score=final_score,
        decision=_decision(final_score),
        reasons=tuple(reasons or ["No strong match signals found"]),
        weights=weights,
    )


def _job_text(job: dict[str, Any]) -> str:
    parts = [
        str(job.get("title", "")),
        str(job.get("description", "")),
        str(job.get("location", "")),
        str(job.get("employment_type", "")),
        str(job.get("remote_policy", "")),
    ]
    return " ".join(parts)


def _first_contains(text: str, needles: Any) -> str | None:
    normalized = text.casefold()
    for needle in needles or ():
        candidate = str(needle)
        if candidate.casefold() in normalized:
            return candidate
    return None


def _all_contains(text: str, needles: Any) -> tuple[str, ...]:
    normalized = text.casefold()
    matches = [str(needle) for needle in needles or () if str(needle).casefold() in normalized]
    return tuple(matches)


def _count(items: Any) -> int:
    return max(1, len(tuple(items or ())))


def _decision(score: int) -> str:
    if score >= 70:
        return "shortlist"
    if score >= 50:
        return "review"
    return "reject"
