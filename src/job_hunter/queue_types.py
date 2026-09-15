"""Shared queue data types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JobInput:
    title: str
    company: str = ""
    location: str = ""
    description: str = ""
    source_url: str = ""
    posted_date: str = ""
    apply_url: str = ""
    description_kind: str = "snippet"
    description_source: str = "search result"
    description_limitation: str = ""
    posted_date_verified: bool = False
    posted_date_source: str = ""
    posted_date_reason: str = ""
    platform: str = ""
