"""Malaysia city lookup for search location selection."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any


COUNTRIES_NOW_CITIES_URL = "https://countriesnow.space/api/v0.1/countries/cities"
DEFAULT_MALAYSIA_CITIES = (
    "Kuala Lumpur",
    "Petaling Jaya",
    "Subang Jaya",
    "Shah Alam",
    "Cyberjaya",
    "Putrajaya",
    "Ampang",
    "Bangsar",
    "Klang",
    "Kajang",
)


def fetch_malaysia_cities(fetcher: Callable[..., Any] | None = None) -> tuple[str, ...]:
    if fetcher is None:
        import requests

        fetcher = requests.post
    try:
        response = fetcher(
            COUNTRIES_NOW_CITIES_URL,
            json={"country": "Malaysia"},
            timeout=(5, 15),
        )
        response.raise_for_status()
        data = response.json()
        if data.get("error"):
            return DEFAULT_MALAYSIA_CITIES
        cities = tuple(str(city).strip() for city in data.get("data", []) if str(city).strip())
        return cities or DEFAULT_MALAYSIA_CITIES
    except Exception:
        return DEFAULT_MALAYSIA_CITIES


def city_options(query: str, cities: Iterable[str] | None = None, limit: int = 25) -> tuple[str, ...]:
    source = tuple(cities or DEFAULT_MALAYSIA_CITIES)
    normalized = query.casefold().strip()
    if not normalized:
        return source[:limit]
    matches = [city for city in source if normalized in city.casefold()]
    return tuple(matches[:limit])
