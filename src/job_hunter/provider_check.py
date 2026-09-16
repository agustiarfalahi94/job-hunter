"""Non-sensitive Gemini connectivity check, independent of the user's CV."""

from job_hunter.matching import GeminiClient, MatchContext, MatchResult, MatchingConfig, score_match
from job_hunter.queue_types import JobInput


def check_gemini_connection(
    config: MatchingConfig, *, client: GeminiClient | None = None
) -> MatchResult:
    return score_match(
        JobInput(
            title="BI Analyst",
            company="Synthetic test company",
            location="Kuala Lumpur",
            description="Build Power BI dashboards.",
            source_url="",
            description_kind="full",
        ),
        MatchContext(mode="criteria", criteria={"primary_keywords": ["Power BI"]}),
        config,
        {},
        client=client,
    )
