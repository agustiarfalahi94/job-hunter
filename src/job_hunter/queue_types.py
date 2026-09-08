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
