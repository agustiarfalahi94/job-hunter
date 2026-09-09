"""Runtime configuration loaded from environment or Streamlit secrets."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SearchProviderConfig:
    serpapi_key: str = ""

    @property
    def has_api_search(self) -> bool:
        return bool(self.serpapi_key)


def load_search_provider_config(
    secrets: object | None = None,
    environ: Mapping[str, str] | None = None,
) -> SearchProviderConfig:
    env = environ if environ is not None else os.environ
    return SearchProviderConfig(
        serpapi_key=_secret_value(secrets, "SERPAPI_API_KEY")
        or _nested_secret_value(secrets, "search", "serpapi_api_key")
        or env.get("SERPAPI_API_KEY", "")
    )


def _secret_value(secrets: object | None, key: str) -> str:
    if secrets is None:
        return ""
    try:
        value = secrets.get(key, "")
    except Exception:
        return ""
    return str(value).strip() if value else ""


def _nested_secret_value(secrets: object | None, section: str, key: str) -> str:
    if secrets is None:
        return ""
    try:
        section_value: Any = secrets.get(section, {})
        value = section_value.get(key, "") if isinstance(section_value, Mapping) else ""
    except Exception:
        return ""
    return str(value).strip() if value else ""
