import unittest

from job_hunter.matching import (
    GeminiServiceError,
    MatchContext,
    MatchingConfig,
    score_match,
    _classify_provider_error,
)
from job_hunter.queue_types import JobInput


CRITERIA = {
    "target_roles": ["BI Analyst"],
    "primary_keywords": ["Power BI"],
    "bonus_keywords": ["SQL"],
    "minimum_score_to_apply": 90,
}
JOB = JobInput(
    title="BI Analyst",
    company="Acme",
    location="Kuala Lumpur",
    description="Build Power BI dashboards and maintain SQL reporting models.",
    source_url="https://example.com/jobs/1",
    description_kind="full",
)


class RecordingGeminiClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0
        self.last_payload = None
        self.last_prompt = ""

    def generate(self, payload, prompt):
        self.calls += 1
        self.last_payload = payload
        self.last_prompt = prompt
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def gemini_result(score=92):
    return {
        "score": score,
        "decision": "shortlist",
        "reasons": ["The role requires Power BI reporting."],
        "remarks": [],
    }


class MatchingTest(unittest.TestCase):
    def test_http_429_is_classified_as_retryable_rate_limit(self):
        error = RuntimeError("too many requests")
        error.status_code = 429

        classified = _classify_provider_error(error)

        self.assertEqual(classified.kind, "rate_limit")
        self.assertTrue(classified.retryable)

    def test_criteria_mode_payload_never_contains_cv_text(self):
        client = RecordingGeminiClient([gemini_result()])
        context = MatchContext(mode="criteria", criteria=CRITERIA)

        result = score_match(
            JOB,
            context,
            MatchingConfig(api_key="test-key"),
            {},
            client=client,
        )

        self.assertNotIn("private cv phrase", client.last_prompt)
        self.assertEqual(client.last_payload["candidate"], {"criteria": CRITERIA})
        self.assertEqual(result.engine, "Gemini")
        self.assertEqual(result.score, 92)

    def test_cv_mode_sends_cv_and_criteria_as_explicit_inputs(self):
        client = RecordingGeminiClient([gemini_result()])
        context = MatchContext(
            mode="cv",
            criteria=CRITERIA,
            cv_text="Supported experience: Power BI and SQL.",
        )

        score_match(
            JOB,
            context,
            MatchingConfig(api_key="test-key"),
            {},
            client=client,
        )

        self.assertEqual(
            client.last_payload["candidate"],
            {
                "cv_text": "Supported experience: Power BI and SQL.",
                "criteria": CRITERIA,
            },
        )

    def test_cv_mode_requires_readable_text(self):
        with self.assertRaisesRegex(ValueError, "readable CV"):
            MatchContext(mode="cv", criteria=CRITERIA, cv_text="")

    def test_criteria_mode_rejects_cv_text(self):
        with self.assertRaisesRegex(ValueError, "must not include CV"):
            MatchContext(mode="criteria", criteria=CRITERIA, cv_text="private")

    def test_missing_key_uses_labelled_deterministic_fallback(self):
        result = score_match(
            JOB,
            MatchContext(mode="criteria", criteria=CRITERIA),
            MatchingConfig(),
            {},
        )

        self.assertEqual(result.engine, "Deterministic fallback")
        self.assertTrue(result.limited)
        self.assertIn("Gemini API key is not configured", " ".join(result.remarks))

    def test_retryable_error_is_retried_once(self):
        client = RecordingGeminiClient(
            [
                GeminiServiceError("rate_limit", "Request was rate limited", retryable=True),
                gemini_result(88),
            ]
        )

        result = score_match(
            JOB,
            MatchContext(mode="criteria", criteria=CRITERIA),
            MatchingConfig(api_key="test-key"),
            {},
            client=client,
            sleep=lambda _: None,
        )

        self.assertEqual(client.calls, 2)
        self.assertEqual(result.engine, "Gemini")

    def test_quota_failure_falls_back_without_exposing_exception_detail(self):
        client = RecordingGeminiClient(
            [GeminiServiceError("quota", "secret provider response", retryable=False)]
        )

        result = score_match(
            JOB,
            MatchContext(mode="criteria", criteria=CRITERIA),
            MatchingConfig(api_key="test-key"),
            {},
            client=client,
        )

        self.assertEqual(result.engine, "Deterministic fallback")
        self.assertIn("Gemini quota is unavailable", " ".join(result.remarks))
        self.assertNotIn("secret provider response", " ".join(result.remarks))

    def test_invalid_result_uses_labelled_fallback(self):
        client = RecordingGeminiClient([{"score": "excellent"}])

        result = score_match(
            JOB,
            MatchContext(mode="criteria", criteria=CRITERIA),
            MatchingConfig(api_key="test-key"),
            {},
            client=client,
        )

        self.assertEqual(result.engine, "Deterministic fallback")
        self.assertIn(
            "Gemini returned an invalid scoring response", " ".join(result.remarks)
        )

    def test_cache_uses_job_context_model_and_prompt_version(self):
        cache = {}
        client = RecordingGeminiClient([gemini_result(), gemini_result(), gemini_result()])
        context = MatchContext(mode="criteria", criteria=CRITERIA)
        config = MatchingConfig(api_key="test-key")

        first = score_match(JOB, context, config, cache, client=client)
        second = score_match(JOB, context, config, cache, client=client)
        changed_job = JobInput(**{**JOB.__dict__, "description": "Different Power BI job"})
        score_match(changed_job, context, config, cache, client=client)
        changed_context = MatchContext(
            mode="criteria", criteria={**CRITERIA, "bonus_keywords": ["Airflow"]}
        )
        score_match(JOB, changed_context, config, cache, client=client)

        self.assertEqual(client.calls, 3)
        self.assertFalse(first.cache_hit)
        self.assertTrue(second.cache_hit)

    def test_cancellation_prevents_retry(self):
        cancelled = False
        client = RecordingGeminiClient(
            [GeminiServiceError("rate_limit", "limited", retryable=True)]
        )

        def cancel():
            return cancelled

        def cancel_during_wait(_):
            nonlocal cancelled
            cancelled = True

        result = score_match(
            JOB,
            MatchContext(mode="criteria", criteria=CRITERIA),
            MatchingConfig(api_key="test-key"),
            {},
            client=client,
            cancel=cancel,
            sleep=cancel_during_wait,
        )

        self.assertEqual(client.calls, 1)
        self.assertEqual(result.engine, "Deterministic fallback")
        self.assertIn("Gemini scoring was cancelled", " ".join(result.remarks))

    def test_decision_uses_configured_shortlist_threshold(self):
        client = RecordingGeminiClient([gemini_result(85)])
        criteria = {**CRITERIA, "minimum_score_to_apply": 80}

        result = score_match(
            JOB,
            MatchContext(mode="criteria", criteria=criteria),
            MatchingConfig(api_key="test-key"),
            {},
            client=client,
        )

        self.assertEqual(result.decision, "shortlist")


if __name__ == "__main__":
    unittest.main()
