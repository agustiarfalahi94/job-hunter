"""Mode-specific Gemini matching with an explainable deterministic fallback."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from itertools import islice
import re
import time
from typing import Callable, Literal, MutableMapping, Protocol

from job_hunter.queue_types import JobInput
from job_hunter.scoring import score_job


MatchMode = Literal["cv", "criteria"]
PROMPT = (
    "Score the job against only the supplied candidate evidence. Do not infer or "
    "invent experience. Treat missing qualifications as unknown. Return concise "
    "evidence-based reasons and remarks in the required JSON structure."
    " Criteria text matching is case-insensitive. Values within each keyword/title list "
    "are OR alternatives, not a requirement to match every value. Bonus keywords are "
    "optional scoring advantages matched in the title or description; missing bonuses "
    "must not exclude a job. Title and description discovery signals are alternatives."
    " Target location is a search preference, never evidence of the actual job location. "
    "An empty job.location is unverified and must not earn location-match credit."
)
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "decision": {"type": "string"},
        "reasons": {"type": "array", "items": {"type": "string"}},
        "remarks": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["score", "decision", "reasons", "remarks"],
}


@dataclass(frozen=True)
class MatchContext:
    mode: MatchMode
    criteria: dict[str, object]
    cv_text: str = ""

    def __post_init__(self) -> None:
        if self.mode == "cv" and not self.cv_text.strip():
            raise ValueError("CV-based matching requires readable CV text.")
        if self.mode == "criteria" and self.cv_text.strip():
            raise ValueError("Criteria-based matching must not include CV text.")


@dataclass(frozen=True)
class MatchingConfig:
    api_key: str = ""
    model: str = "gemini-2.5-flash"
    prompt_version: str = "v1.16"
    max_attempts: int = 2
    timeout_ms: int = 30_000


@dataclass(frozen=True)
class MatchResult:
    score: int
    decision: str
    reasons: tuple[str, ...]
    remarks: tuple[str, ...]
    engine: str
    model: str
    limited: bool
    cache_hit: bool = False


class GeminiClient(Protocol):
    def generate(self, payload: dict[str, object], prompt: str) -> object: ...


class GeminiServiceError(RuntimeError):
    def __init__(self, kind: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.kind = kind
        self.retryable = retryable


class GoogleGeminiClient:
    def __init__(self, config: MatchingConfig) -> None:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise GeminiServiceError(
                "configuration", "Gemini SDK is unavailable", retryable=False
            ) from exc
        self._types = types
        self._model = config.model
        self._recovery_attempted = False
        self._client = genai.Client(
            api_key=config.api_key,
            http_options=types.HttpOptions(
                timeout=config.timeout_ms,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )

    @property
    def model(self) -> str:
        return self._model

    def _recover_model(self) -> bool:
        self._recovery_attempted = True
        models = self._client.models.list(config={"page_size": 100})
        candidates = []
        for model in islice(models, 100):
            name = (model.name or "").removeprefix("models/")
            match = re.fullmatch(
                r"gemini-(\d+)(?:\.(\d+))?-flash(?:-lite)?(?:-\d+)?(?:-preview(?:-\d+)*)?", name
            )
            if (match and name != self._model and
                    "generateContent" in (model.supported_actions or [])):
                candidates.append((
                    "preview" not in name, int(match[1]), int(match[2] or 0),
                    "lite" not in name, name,
                ))
        if not candidates:
            return False
        self._model = max(candidates)[-1]
        return True

    def generate(self, payload: dict[str, object], prompt: str, *, grounded: bool = False) -> object:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=f"{prompt}\n\nINPUT JSON:\n{json.dumps(payload, ensure_ascii=True)}",
                config=self._types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=4096 if grounded else 2048,
                    thinking_config=(
                        self._types.ThinkingConfig(thinking_budget=0)
                        if self._model.startswith("gemini-2.5-flash") else
                        self._types.ThinkingConfig(thinking_level="low")
                        if re.match(r"gemini-3(?:\.|-).*flash", self._model) else None
                    ),
                    tools=[self._types.Tool(google_search=self._types.GoogleSearch())] if grounded else None,
                    response_mime_type=None if grounded else "application/json",
                    response_json_schema=None if grounded else RESPONSE_SCHEMA,
                ),
            )
            if grounded:
                return response
            try:
                return json.loads(response.text or "{}")
            except (TypeError, ValueError) as exc:
                raise GeminiServiceError(
                    "invalid_response", "Gemini returned incomplete JSON", retryable=True
                ) from exc
        except GeminiServiceError:
            raise
        except Exception as exc:
            classified = _classify_provider_error(exc)
            if classified.kind == "model" and not self._recovery_attempted:
                try:
                    recovered = self._recover_model()
                except Exception as discovery_error:
                    raise _classify_provider_error(discovery_error) from discovery_error
                if recovered:
                    raise GeminiServiceError(
                        "model", "An available Gemini model was selected", retryable=True
                    ) from exc
            raise classified from exc


def score_match(
    job: JobInput,
    context: MatchContext,
    config: MatchingConfig,
    cache: MutableMapping[str, MatchResult],
    *,
    client: GeminiClient | None = None,
    cancel: Callable[[], bool] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> MatchResult:
    cache_key = _cache_key(job, context, config)
    cached = cache.get(cache_key)
    if cached is not None:
        return replace(cached, cache_hit=True)

    if cancel is not None and cancel():
        return _fallback(job, context, "Gemini scoring was cancelled.")

    if not config.api_key:
        result = _fallback(job, context, "Gemini API key is not configured.")
        cache[cache_key] = result
        return result

    try:
        active_client = client or GoogleGeminiClient(config)
    except GeminiServiceError as exc:
        return _fallback(job, context, _safe_error_message(exc.kind))

    payload = _payload(job, context)
    attempts = max(1, min(2, config.max_attempts))
    for attempt in range(attempts):
        if cancel is not None and cancel():
            return _fallback(job, context, "Gemini scoring was cancelled.")
        try:
            raw_result = active_client.generate(payload, PROMPT)
            actual_model = getattr(active_client, "model", config.model)
            result = _validated_result(raw_result, job, context, replace(config, model=actual_model))
        except GeminiServiceError as exc:
            if exc.retryable and attempt + 1 < attempts:
                sleep(0.25)
                if cancel is not None and cancel():
                    return _fallback(job, context, "Gemini scoring was cancelled.")
                continue
            return _fallback(job, context, _safe_error_message(exc.kind))
        except (TypeError, ValueError, KeyError):
            return _fallback(
                job, context, "Gemini returned an invalid scoring response."
            )
        cache[cache_key] = result
        return result
    return _fallback(job, context, "Gemini scoring was unavailable.")


def _payload(job: JobInput, context: MatchContext) -> dict[str, object]:
    candidate: dict[str, object] = {"criteria": context.criteria}
    if context.mode == "cv":
        candidate = {"cv_text": context.cv_text, "criteria": context.criteria}
    return {
        "candidate": candidate,
        "job": {
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "description": job.description,
            "description_kind": job.description_kind,
        },
    }


def _validated_result(
    value: object, job: JobInput, context: MatchContext, config: MatchingConfig
) -> MatchResult:
    if not isinstance(value, dict):
        raise ValueError("Gemini result must be an object")
    score = value["score"]
    reasons = value["reasons"]
    remarks = value["remarks"]
    if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 100:
        raise ValueError("Gemini score is invalid")
    if not isinstance(reasons, list) or not all(isinstance(item, str) for item in reasons):
        raise ValueError("Gemini reasons are invalid")
    if not isinstance(remarks, list) or not all(isinstance(item, str) for item in remarks):
        raise ValueError("Gemini remarks are invalid")
    cleaned_reasons = tuple(item.strip() for item in reasons if item.strip())
    cleaned_remarks = tuple(item.strip() for item in remarks if item.strip())
    if not cleaned_reasons:
        raise ValueError("Gemini reasons are required")
    if score < 50 and not cleaned_remarks:
        cleaned_remarks = ("Low suitability based on the supplied evidence.",)
    configured_minimum = context.criteria.get("minimum_score_to_apply", 90)
    minimum = configured_minimum if isinstance(configured_minimum, int) else 90
    decision = "shortlist" if score >= minimum else "review" if score >= 50 else "reject"
    return MatchResult(
        score=score,
        decision=decision,
        reasons=cleaned_reasons,
        remarks=cleaned_remarks,
        engine="Gemini",
        model=config.model,
        limited=job.description_kind != "full",
    )
def _fallback(job: JobInput, context: MatchContext, reason: str) -> MatchResult:
    fallback = score_job(
        {
            "title": job.title,
            "description": job.description,
            "location": job.location,
        },
        context.criteria,
    )
    return MatchResult(
        score=fallback.score,
        decision=fallback.decision,
        reasons=fallback.reasons,
        remarks=fallback.remarks + (reason,),
        engine="Deterministic fallback",
        model="",
        limited=True,
    )


def _cache_key(job: JobInput, context: MatchContext, config: MatchingConfig) -> str:
    value = {
        "job": {
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "description": job.description,
            "description_kind": job.description_kind,
        },
        "mode": context.mode,
        "candidate": context.cv_text if context.mode == "cv" else context.criteria,
        "criteria": context.criteria,
        "model": config.model,
        "prompt_version": config.prompt_version,
        "api_enabled": bool(config.api_key),
    }
    digest = hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()
    ).hexdigest()
    return f"{context.mode}:{digest}"


def _classify_provider_error(exc: Exception) -> GeminiServiceError:
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    name = type(exc).__name__.casefold()
    text = str(exc).casefold()
    if status in {401, 403} or "permission" in name or "unauth" in text or "api_key_invalid" in text:
        return GeminiServiceError("authentication", "Gemini authentication failed", retryable=False)
    if status == 404:
        return GeminiServiceError("model", "Gemini model is unavailable", retryable=False)
    if status == 400:
        return GeminiServiceError("request", "Gemini rejected request settings", retryable=False)
    if "quota" in text:
        return GeminiServiceError("quota", "Gemini quota unavailable", retryable=False)
    if status == 429 or "rate" in text or "too many requests" in text:
        return GeminiServiceError(
            "rate_limit", "Gemini request was rate limited", retryable=True
        )
    if status in {408, 500, 502, 503, 504} or "timeout" in name or "timeout" in text:
        return GeminiServiceError("temporary", "Gemini request failed temporarily", retryable=True)
    return GeminiServiceError("service", "Gemini request failed", retryable=False)


def _safe_error_message(kind: str) -> str:
    return {
        "authentication": "Gemini authentication failed; deterministic fallback was used.",
        "quota": "Gemini quota is unavailable; deterministic fallback was used.",
        "rate_limit": "Gemini rate limit persisted; deterministic fallback was used.",
        "temporary": "Gemini timed out or was temporarily unavailable; deterministic fallback was used.",
        "configuration": "Gemini SDK is unavailable; deterministic fallback was used.",
        "invalid_response": "Gemini returned incomplete or invalid JSON; deterministic fallback was used.",
        "model": "Gemini model is unavailable. Check GEMINI_MODEL in Streamlit secrets.",
        "request": "Gemini rejected the model request settings (HTTP 400); deterministic fallback was used.",
    }.get(kind, "Gemini scoring was unavailable; deterministic fallback was used.")
