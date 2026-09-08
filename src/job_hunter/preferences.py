"""Preference loading for the local workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any


DEFAULT_PREFERENCES: dict[str, Any] = {
    "target_roles": [
        "Data Analyst",
        "Data Engineer",
        "BI Developer",
        "Reporting Analyst",
        "Reporting Engineer",
        "Business Intelligence Analyst",
        "BI Analyst",
        "BI Engineer",
    ],
    "target_locations": ["Kuala Lumpur"],
    "primary_keywords": ["Power BI", "SSRS", "Google BigQuery", "BigQuery"],
    "bonus_keywords": [
        "PostgreSQL",
        "Alibaba MaxCompute",
        "MaxCompute",
        "Domo",
        "MySQL",
        "T-SQL",
        "MSSQL",
        "data migration",
        "Apache Airflow",
        "Airflow",
        "Docker",
        "Python",
        "Python scripts",
        "PySpark",
        "Git",
        "GitHub",
        "GitLab",
        "CI/CD pipeline variables",
        "CI/CD",
        "Agile",
        "Scrum",
        "CAB deployment",
    ],
    "avoid_keywords": [],
    "hard_skip_keywords": ["locals/malaysian only", "mandarin speaker is mandatory"],
    "allow_managerial_if_description_matches": True,
    "minimum_score_to_apply": 90,
    "daily_targets": {"strong_matches": 20, "suitable_matches": 50},
}


def load_preferences(path: Path | str = Path("config/preferences.local.yaml")) -> dict[str, Any]:
    preferences = dict(DEFAULT_PREFERENCES)
    preferences["daily_targets"] = dict(DEFAULT_PREFERENCES["daily_targets"])
    path = Path(path)
    if not path.exists():
        return preferences
    _deep_update(preferences, _parse_simple_yaml(path.read_text(encoding="utf-8")))
    return preferences


def _deep_update(base: dict[str, Any], updates: dict[str, Any]) -> None:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key].update(value)
        else:
            base[key] = value


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.startswith("  - ") and current_key:
            result.setdefault(current_key, []).append(_parse_scalar(line[4:]))
            continue
        if line.startswith("  ") and current_key:
            child_key, child_value = line.strip().split(":", 1)
            if result.get(current_key) == []:
                result[current_key] = {}
            result.setdefault(current_key, {})[child_key.strip()] = _parse_scalar(child_value.strip())
            continue
        key, value = line.split(":", 1)
        current_key = key.strip()
        value = value.strip()
        result[current_key] = [] if value == "" else _parse_scalar(value)
    return result


def _parse_scalar(value: str) -> Any:
    value = value.strip().strip("\"'")
    if value.casefold() == "true":
        return True
    if value.casefold() == "false":
        return False
    try:
        return int(value)
    except ValueError:
        return value
