import unittest
import json
from types import SimpleNamespace
from unittest.mock import patch

from job_hunter.matching import (
    GeminiServiceError,
    MatchContext,
    MatchingConfig,
    score_match,
    _classify_provider_error,
    GoogleGeminiClient,
)
from job_hunter.provider_check import check_gemini_connection
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
    def test_unavailable_model_recovers_once_and_reports_actual_model(self):
        error = RuntimeError("model not found")
        error.code = 404
        with patch("google.genai.Client") as factory:
            models = factory.return_value.models
            models.generate_content.side_effect = [
                error, SimpleNamespace(text=json.dumps(gemini_result()))
            ]
            models.list.return_value = [
                SimpleNamespace(name="models/gemini-3.1-flash-preview", supported_actions=["generateContent"]),
                SimpleNamespace(name="models/gemini-3.0-flash", supported_actions=["generateContent"]),
                SimpleNamespace(name="models/gemini-3.0-flash-image", supported_actions=["generateContent"]),
            ]
            result = score_match(JOB, MatchContext(mode="criteria", criteria=CRITERIA),
                                 MatchingConfig(api_key="test-key"), {}, sleep=lambda _: None)
            self.assertEqual(models.generate_content.call_count, 2)
            self.assertEqual(models.list.call_count, 1)
            self.assertEqual(models.generate_content.call_args.kwargs["model"], "gemini-3.0-flash")
        self.assertEqual(result.engine, "Gemini")
        self.assertEqual(result.model, "gemini-3.0-flash")

    def test_model_recovery_does_not_guess_when_no_supported_flash_exists(self):
        error = RuntimeError("model not found")
        error.code = 404
        with patch("google.genai.Client") as factory:
            models = factory.return_value.models
            models.generate_content.side_effect = error
            models.list.return_value = [
                SimpleNamespace(name="models/gemini-3.0-flash", supported_actions=["embedContent"])
            ]
            result = score_match(JOB, MatchContext(mode="criteria", criteria=CRITERIA),
                                 MatchingConfig(api_key="test-key"), {}, sleep=lambda _: None)
            self.assertEqual(models.generate_content.call_count, 1)
        self.assertEqual(result.engine, "Deterministic fallback")

    def test_authentication_failure_never_lists_models(self):
        error = RuntimeError("invalid key")
        error.code = 403
        with patch("google.genai.Client") as factory:
            factory.return_value.models.generate_content.side_effect = error
            score_match(JOB, MatchContext(mode="criteria", criteria=CRITERIA),
                        MatchingConfig(api_key="test-key"), {}, sleep=lambda _: None)
            factory.return_value.models.list.assert_not_called()

    def test_alternate_model_failure_stays_within_two_generations(self):
        error = RuntimeError("model not found")
        error.code = 404
        with patch("google.genai.Client") as factory:
            models = factory.return_value.models
            models.generate_content.side_effect = error
            models.list.return_value = [
                SimpleNamespace(name="models/gemini-3.0-flash", supported_actions=["generateContent"])
            ]
            result = score_match(JOB, MatchContext(mode="criteria", criteria=CRITERIA),
                                 MatchingConfig(api_key="test-key"), {}, sleep=lambda _: None)
            self.assertEqual(models.generate_content.call_count, 2)
            self.assertEqual(models.list.call_count, 1)
        self.assertEqual(result.engine, "Deterministic fallback")

    def test_quota_failure_never_lists_models(self):
        error = RuntimeError("quota exhausted")
        error.code = 429
        with patch("google.genai.Client") as factory:
            factory.return_value.models.generate_content.side_effect = error
            score_match(JOB, MatchContext(mode="criteria", criteria=CRITERIA),
                        MatchingConfig(api_key="test-key"), {}, sleep=lambda _: None)
            factory.return_value.models.list.assert_not_called()

    def test_connection_check_uses_only_synthetic_data(self):
        client = RecordingGeminiClient([gemini_result()])
        result = check_gemini_connection(MatchingConfig(api_key="test-key"), client=client)
        self.assertEqual(result.engine, "Gemini")
        self.assertNotIn("cv_text", client.last_payload["candidate"])
        self.assertEqual(client.last_payload["job"]["company"], "Synthetic test company")

    def test_invalid_key_bad_request_is_classified_as_authentication(self):
        error = RuntimeError("API_KEY_INVALID")
        error.code = 400
        self.assertEqual(_classify_provider_error(error).kind, "authentication")

    def test_unavailable_model_is_classified_explicitly(self):
        error = RuntimeError("model not found")
        error.code = 404
        self.assertEqual(_classify_provider_error(error).kind, "model")

    def test_sdk_adapter_reserves_output_for_json_instead_of_thinking(self):
        with patch("google.genai.Client") as factory:
            factory.return_value.models.generate_content.return_value = SimpleNamespace(
                text=json.dumps(gemini_result()), candidates=[]
            )
            client = GoogleGeminiClient(MatchingConfig(api_key="test-key"))
            value = client.generate({}, "Score this synthetic job")
            config = factory.return_value.models.generate_content.call_args.kwargs["config"]

        self.assertEqual(value["score"], 92)
        self.assertEqual(config.thinking_config.thinking_budget, 0)
        self.assertGreaterEqual(config.max_output_tokens, 2048)

    def test_gemini_three_flash_uses_minimal_thinking(self):
        with patch("google.genai.Client") as factory:
            factory.return_value.models.generate_content.return_value = SimpleNamespace(
                text=json.dumps(gemini_result())
            )
            client = GoogleGeminiClient(MatchingConfig(api_key="test-key", model="gemini-3-flash-preview"))
            client.generate({}, "Score this synthetic job")
            config = factory.return_value.models.generate_content.call_args.kwargs["config"]
        self.assertEqual(config.thinking_config.thinking_level, "MINIMAL")

    def test_recovery_accepts_provider_listed_major_only_versions(self):
        error = RuntimeError("model not found")
        error.code = 404
        with patch("google.genai.Client") as factory:
            models = factory.return_value.models
            models.generate_content.side_effect = [error, SimpleNamespace(text=json.dumps(gemini_result()))]
            models.list.return_value = [SimpleNamespace(
                name="models/gemini-3-flash-preview", supported_actions=["generateContent"]
            )]
            result = score_match(JOB, MatchContext(mode="criteria", criteria=CRITERIA),
                                 MatchingConfig(api_key="test-key"), {}, sleep=lambda _: None)
        self.assertEqual(result.model, "gemini-3-flash-preview")

    def test_sdk_invalid_json_is_classified_explicitly(self):
        with patch("google.genai.Client") as factory:
            factory.return_value.models.generate_content.return_value = SimpleNamespace(
                text='{"score":', candidates=[]
            )
            client = GoogleGeminiClient(MatchingConfig(api_key="test-key"))
            with self.assertRaises(GeminiServiceError) as error:
                client.generate({}, "Score this synthetic job")

        self.assertEqual(error.exception.kind, "invalid_response")

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
