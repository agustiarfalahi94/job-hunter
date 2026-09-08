"""Public candidate profile facts supported by the provided CV."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateProfile:
    positioning: str
    strengths: tuple[str, ...]
    tools: tuple[str, ...]
    project_evidence: tuple[str, ...]


CANDIDATE_PROFILE = CandidateProfile(
    positioning=(
        "Data engineering, analytics engineering, BI development, data analysis, "
        "and SQL-heavy reporting roles."
    ),
    strengths=(
        "BigQuery to MaxCompute data migration with Python and Parquet transfer",
        "Airflow orchestration, Docker workflows, and CI/CD automation",
        "Greenplum-sourced reporting migration to BigQuery and Power BI",
        "PostgreSQL to BigQuery reporting-layer migration",
        "Operational reporting for claims, actuarial, reinsurance, member management, and accounting",
        "SQL development, report refresh monitoring, schema-change investigation, and query tuning",
        "Application support for billing/CRM corrections, MySQL OLTP updates, monitoring, QA, and 24/7 support",
        "System implementation, module testing, and UAT support",
    ),
    tools=(
        "SQL",
        "Python",
        "PostgreSQL",
        "MySQL",
        "T-SQL",
        "BigQuery",
        "MaxCompute",
        "Power BI",
        "SSRS",
        "Domo",
        "Airflow",
        "Docker",
        "GitHub",
        "GitLab",
        "CI/CD",
    ),
    project_evidence=(
        "Malaysian Real-Time Transit Tracker with Python, DuckDB, Streamlit, Plotly, Pandas, Protobuf, dbt-duckdb, and CI data-quality tests",
        "Random Recall mobile spaced repetition app with Flutter, Dart, Firebase, RevenueCat, PostHog, and bilingual support",
    ),
)


def public_profile_summary(profile: CandidateProfile = CANDIDATE_PROFILE) -> str:
    """Return a contact-free summary safe for a public repository."""

    lines = [
        f"Positioning: {profile.positioning}",
        "Strengths:",
        *[f"- {strength}" for strength in profile.strengths],
        "Tools:",
        *[f"- {tool}" for tool in profile.tools],
        "Project evidence:",
        *[f"- {project}" for project in profile.project_evidence],
    ]
    return "\n".join(lines)
