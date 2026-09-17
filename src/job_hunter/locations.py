"""City suggestions and evidence-based OR matching for geographic scopes."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any
import re
import unicodedata

import pycountry


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

# APAC is an app-defined hiring-market preset, not an official universal region.
REGION_COUNTRIES = {
    "Europe": ("AL", "AD", "AT", "BY", "BE", "BA", "BG", "HR", "CZ", "DK", "EE",
               "FO", "FI", "FR", "DE", "GI", "GR", "GG", "VA", "HU", "IS", "IE",
               "IM", "IT", "JE", "LV", "LI", "LT", "LU", "MT", "MD", "MC", "ME",
               "NL", "MK", "NO", "PL", "PT", "RO", "RU", "SM", "RS", "SK", "SI",
               "ES", "SJ", "SE", "CH", "UA", "GB", "AX"),
    "ASEAN": ("BN", "KH", "ID", "LA", "MY", "MM", "PH", "SG", "TH", "TL", "VN"),
    "APAC": ("BN", "KH", "ID", "LA", "MY", "MM", "PH", "SG", "TH", "TL", "VN",
             "CN", "HK", "MO", "TW", "JP", "KR", "KP", "MN", "IN", "BD", "PK",
             "LK", "NP", "BT", "MV", "AF", "AU", "NZ", "FJ", "PG", "SB", "VU",
             "WS", "TO", "KI", "TV", "NR", "FM", "MH", "PW", "CK", "NU", "NC",
             "PF", "GU", "MP", "AS", "TK", "WF", "PN"),
}
COUNTRY_LABELS = {
    "VN": "Vietnam", "LA": "Laos", "KR": "South Korea", "KP": "North Korea",
    "TW": "Taiwan", "BN": "Brunei", "MO": "Macao",
}
COUNTRY_ALIASES = {"uk": "GB", "south korea": "KR", "north korea": "KP",
                   "taiwan": "TW", "vietnam": "VN", "laos": "LA", "brunei": "BN",
                   "macau": "MO"}
CITY_COUNTRIES = {city.casefold(): "MY" for city in DEFAULT_MALAYSIA_CITIES}
CITY_COUNTRIES.update({"jakarta": "ID", "bangkok": "TH", "singapore": "SG",
                       "manila": "PH", "hanoi": "VN", "ho chi minh city": "VN",
                       "dili": "TL", "tokyo": "JP", "sydney": "AU"})
CITY_COUNTRIES.update({"johor bahru": "MY", "berlin": "DE", "paris": "FR",
                       "new york": "US", "london": "GB"})


def _normalized(value: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", value.casefold())
    return " ".join(re.sub(r"[^a-z0-9]+", " ", ascii_text).split())


def _country_code(value: str) -> str | None:
    alias = COUNTRY_ALIASES.get(value.strip().casefold())
    if alias:
        return alias
    try:
        return pycountry.countries.lookup(value.strip()).alpha_2
    except LookupError:
        return None


def _country_label(code: str) -> str:
    return COUNTRY_LABELS.get(code) or pycountry.countries.get(alpha_2=code).name


def _region(value: str) -> str | None:
    normalized = _normalized(value)
    return {"asean": "ASEAN", "southeast asia": "ASEAN", "south east asia": "ASEAN",
            "apac": "APAC", "asia pacific": "APAC", "europe": "Europe"}.get(normalized)


def is_global(scopes: Iterable[str]) -> bool:
    return any(_normalized(scope) in {"global", "worldwide", "whole world"} for scope in scopes)


def location_options(cities: Iterable[str]) -> tuple[str, ...]:
    countries = sorted((_country_label(country.alpha_2) for country in pycountry.countries),
                       key=str.casefold)
    return tuple(dict.fromkeys(["Kuala Lumpur", "Jakarta", "Malaysia", "Indonesia",
                               "ASEAN", "APAC", "Europe", "Global", *cities, *countries]))


def location_search_terms(scopes: Iterable[str]) -> tuple[str, ...]:
    scopes = tuple(scopes)
    if is_global(scopes):
        return ()
    terms = []
    for scope in scopes:
        region = _region(scope)
        if region:
            terms.extend(_country_label(code) for code in REGION_COUNTRIES[region])
            terms.append(region)
            if region in {"APAC", "ASEAN"}:
                terms.append("Asia Pacific" if region == "APAC" else "Southeast Asia")
        elif scope.strip():
            code = _country_code(scope)
            terms.append(_country_label(code) if code else scope.strip())
    return tuple({term.casefold(): term for term in reversed(terms)}.values())[::-1]


def company_region(scope: str) -> str:
    if is_global((scope,)):
        return "Global"
    region = _region(scope)
    if region:
        return "Asia Pacific" if region == "APAC" else region
    code = _country_code(scope) or CITY_COUNTRIES.get(scope.casefold().strip())
    return _country_label(code) if code else scope.strip()


def is_known_area(value: str) -> bool:
    return bool(_country_code(value) or value.casefold().strip() in CITY_COUNTRIES or _region(value))


def _observed_countries(observed: str) -> set[str]:
    codes = set()
    normalized = _normalized(observed)
    # Short ISO codes are evidence only as whole address components, not prose words.
    components = re.split(r"[,;/|]", observed)
    explicit_country = _country_code(components[-1].strip())
    if explicit_country:
        return {explicit_country}
    for component in components:
        code = _country_code(component.strip())
        if code:
            codes.add(code)
    for country in pycountry.countries:
        names = [country.name, _country_label(country.alpha_2)]
        names.extend(getattr(country, field, "") for field in ("official_name", "common_name"))
        if any(name and f" {_normalized(name)} " in f" {normalized} " for name in names):
            codes.add(country.alpha_2)
    if codes:
        return codes
    for city, code in CITY_COUNTRIES.items():
        if f" {_normalized(city)} " in f" {normalized} ":
            codes.add(code)
    return codes


def location_matches(observed: str, requested: Iterable[str] | str, *, locality: str | None = None) -> bool | None:
    """True for verified OR membership, False for a mismatch, None if unverified."""
    scopes = (requested,) if isinstance(requested, str) else tuple(requested)
    scopes = tuple(scope for scope in scopes if scope.strip())
    if not scopes:
        return True
    if not observed.strip():
        return None
    if is_global(scopes):
        return True
    results = []
    for place in observed.split(";"):
        normalized = _normalized(place)
        codes = _observed_countries(place)
        for scope in scopes:
            region = _region(scope)
            code = _country_code(scope)
            if region:
                if _region(place) == region:
                    results.append(True)
                else:
                    results.append(bool(codes.intersection(REGION_COUNTRIES[region])) if codes else None)
            elif code:
                results.append(code in codes if codes else None)
            elif locality is not None:
                requested_country = CITY_COUNTRIES.get(scope.casefold().strip())
                if locality.strip():
                    results.append(f" {_normalized(scope)} " in f" {_normalized(locality)} ")
                else:
                    results.append(False if requested_country and codes and requested_country not in codes else None)
            elif f" {_normalized(scope)} " in f" {normalized} ":
                results.append(True)
            elif codes:
                requested_country = CITY_COUNTRIES.get(scope.casefold().strip())
                known_city = any(f" {_normalized(city)} " in f" {normalized} " for city in CITY_COUNTRIES)
                results.append(False if known_city or
                               (requested_country and requested_country not in codes) else None)
            elif _region(place):
                results.append(None)
            else:
                results.append(None)
    return True if True in results else None if None in results else False


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
