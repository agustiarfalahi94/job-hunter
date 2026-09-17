"""Bounded, cancellable job discovery and matching for Streamlit sessions."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, wait, FIRST_COMPLETED
from dataclasses import dataclass, replace
from queue import Empty, Queue
import threading
import time
from typing import Callable, Literal, MutableMapping
from uuid import uuid4

from bs4 import BeautifulSoup

from job_hunter.descriptions import JobDescription
from job_hunter.job_identity import canonicalize_job_url, job_source, vacancy_fingerprint
from job_hunter.matching import MatchContext, MatchResult, MatchingConfig, score_match
from job_hunter.queue_types import JobInput
from job_hunter.runtime_config import SearchProviderConfig
from job_hunter.search import (
    MAX_SEARCH_REQUESTS,
    APPLICATION_FILTERS,
    PlatformQuery,
    SearchCandidate,
    SearchCriteria,
    _closed_job_reason,
    _eligibility_skip_reason,
    _is_blocked_search_page,
    _posting_is_too_old,
    _job_location_matches,
    build_public_fallback_queries,
    build_serpapi_queries,
    extract_job_metadata,
    match_job_locations,
    fetch_job_html,
    fetch_public_html,
    parse_duckduckgo_results,
    parse_linkedin_jobs,
    parse_serpapi_results,
    serpapi_web_result_count,
    SearchProviderError,
)


RunState = Literal["idle", "running", "completed", "cancelled", "failed"]
MAX_UNIQUE_RESULTS = 50
MAX_PAGE_FETCHES = 50
MAX_GEMINI_ATTEMPTS = 50
DEFAULT_DEADLINE_SECONDS = 300.0


@dataclass(frozen=True)
class SearchRequest:
    criteria: SearchCriteria
    match_context: MatchContext
    provider_config: SearchProviderConfig = SearchProviderConfig()
    matching_config: MatchingConfig = MatchingConfig()


@dataclass(frozen=True)
class RunEvent:
    run_id: str
    stage: str
    checked: int
    total: int
    message: str


@dataclass(frozen=True)
class CompletedMatch:
    run_id: str
    job: JobInput
    result: MatchResult


@dataclass(frozen=True)
class RunSnapshot:
    run_id: str = ""
    state: RunState = "idle"
    discovered: int = 0
    checked: int = 0
    completed: int = 0
    skipped: int = 0
    discovery_requests: int = 0
    discovery_failures: int = 0
    page_fetches: int = 0
    scoring_attempts: int = 0
    message: str = "Ready"


@dataclass(frozen=True)
class _ProcessedCandidate:
    job: JobInput | None
    result: MatchResult | None
    skip_reason: str = ""


Scorer = Callable[..., MatchResult]


class SearchRunController:
    """Runs one search at a time and publishes immutable session-safe results."""

    def __init__(
        self,
        *,
        discovery_fetcher: Callable[[str], str] | None = None,
        page_fetcher: Callable[[str], str] | None = None,
        scorer: Scorer = score_match,
        max_workers: int = 2,
        clock: Callable[[], float] = time.monotonic,
        deadline_seconds: float = DEFAULT_DEADLINE_SECONDS,
    ) -> None:
        self._discovery_fetcher = discovery_fetcher or fetch_public_html
        self._page_fetcher = page_fetcher or fetch_job_html
        self._uses_default_page_fetcher = page_fetcher is None
        self._scorer = scorer
        self._max_workers = max(1, min(2, max_workers))
        self._clock = clock
        self._deadline_seconds = min(DEFAULT_DEADLINE_SECONDS, deadline_seconds)
        self._events: Queue[RunEvent] = Queue()
        self._matches: Queue[CompletedMatch] = Queue()
        self._lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._snapshot = RunSnapshot()
        self._score_cache: MutableMapping[str, MatchResult] = {}

    def start(self, request: SearchRequest) -> str:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("A search is already running.")
            run_id = uuid4().hex
            self._cancel_event = threading.Event()
            self._snapshot = RunSnapshot(run_id=run_id, state="running", message="Starting search")
            self._drain_queue(self._events)
            self._drain_queue(self._matches)
            self._thread = threading.Thread(
                target=self._coordinate,
                args=(run_id, request),
                name=f"job-hunter-{run_id[:8]}",
                daemon=True,
            )
            self._thread.start()
            return run_id

    def cancel(self) -> None:
        self._cancel_event.set()
        with self._lock:
            if self._snapshot.state == "running":
                self._snapshot = replace(
                    self._snapshot,
                    message="Cancelling after the current bounded request",
                )

    def wait(self, timeout: float | None = None) -> bool:
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout)
        return not thread.is_alive()

    def drain(self) -> tuple[tuple[RunEvent, ...], tuple[CompletedMatch, ...]]:
        return tuple(self._drain_queue(self._events)), tuple(self._drain_queue(self._matches))

    def snapshot(self) -> RunSnapshot:
        with self._lock:
            return self._snapshot

    def _coordinate(self, run_id: str, request: SearchRequest) -> None:
        started = self._clock()
        futures: dict[Future[_ProcessedCandidate], tuple[str, SearchCandidate]] = {}
        unique_candidates: list[tuple[str, SearchCandidate]] = []
        unique_keys: set[str] = set()
        executor = ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix=f"job-match-{run_id[:6]}",
        )
        try:
            queries = _planned_queries(request.criteria, request.provider_config)
            for query in queries[:MAX_SEARCH_REQUESTS]:
                if self._should_stop(started):
                    break
                self._increment(discovery_requests=1)
                self._emit(run_id, "searching", f"Searching {query.platform}: {query.query}")
                try:
                    payload = self._discovery_fetcher(query.url)
                except Exception as exc:
                    self._increment(skipped=1, discovery_failures=1)
                    status = getattr(getattr(exc, "response", None), "status_code", None)
                    detail = {401: "Provider authentication failed; check the search API key.",
                              403: "Provider denied access; check its dashboard.",
                              429: "Provider allowance or rate limit reached; check its dashboard."}.get(
                                  status, "Search request failed or timed out.")
                    self._emit(run_id, "skipped", f"Skipped {query.platform}: {detail}")
                    continue
                if self._should_stop(started):
                    break
                if _is_blocked_search_page(payload):
                    self._increment(skipped=1, discovery_failures=1)
                    self._emit(
                        run_id,
                        "skipped",
                        f"Skipped {query.platform}: search provider returned a challenge page.",
                    )
                    continue
                try:
                    candidates = _parse_results(query, payload, request.criteria.location)
                    if query.parser == "serpapi":
                        count = serpapi_web_result_count(payload)
                        self._emit(run_id, "discovered", f"{query.platform}: {count} web results; "
                                   f"{len(candidates)} eligible job links; {max(0, count - len(candidates))} "
                                   "links excluded by source/path/content checks.")
                except (SearchProviderError, ValueError, TypeError, AttributeError):
                    self._increment(skipped=1, discovery_failures=1)
                    try:
                        serpapi_web_result_count(payload)
                    except SearchProviderError as exc:
                        detail = str(exc)
                    except (ValueError, TypeError, AttributeError):
                        detail = "Search provider returned an unreadable response."
                    else:
                        detail = "Search provider returned invalid result records."
                    self._emit(run_id, "skipped", f"Skipped {query.platform}: {detail}")
                    continue
                for candidate in candidates:
                    if self._should_stop(started) or len(unique_keys) >= MAX_UNIQUE_RESULTS:
                        break
                    identity = _candidate_identity(candidate)
                    if identity in unique_keys:
                        continue
                    unique_keys.add(identity)
                    self._increment(discovered=1)
                    unique_candidates.append((identity, candidate))
                if len(unique_keys) >= MAX_UNIQUE_RESULTS:
                    break

            candidate_index = 0
            while (
                candidate_index < len(unique_candidates)
                and len(futures) < self._max_workers
                and not self._should_stop(started)
            ):
                identity, candidate = unique_candidates[candidate_index]
                candidate_index += 1
                future = executor.submit(
                    self._process_candidate, request, candidate, started
                )
                futures[future] = (identity, candidate)

            pending = set(futures)
            while pending:
                done_now = {future for future in pending if future.done()}
                if not done_now and not self._should_stop(started):
                    done_now, _ = wait(pending, timeout=0.1, return_when=FIRST_COMPLETED)
                for future in done_now:
                    pending.discard(future)
                    identity, original = futures[future]
                    self._publish_processed(run_id, future, original)
                if self._should_stop(started):
                    for future in pending:
                        future.cancel()
                    settled, _ = wait(pending, timeout=1.0)
                    for future in settled:
                        identity, original = futures[future]
                        self._publish_processed(
                            run_id, future, original
                        )
                    break
                while (
                    candidate_index < len(unique_candidates)
                    and len(pending) < self._max_workers
                    and not self._should_stop(started)
                ):
                    identity, candidate = unique_candidates[candidate_index]
                    candidate_index += 1
                    future = executor.submit(
                        self._process_candidate, request, candidate, started
                    )
                    futures[future] = (identity, candidate)
                    pending.add(future)

            if self._cancel_event.is_set() or self._clock() - started >= self._deadline_seconds:
                state: RunState = "cancelled"
                message = "Search cancelled. Completed results were kept."
                stage = "cancelled"
            else:
                snapshot = self.snapshot()
                if not snapshot.discovered and snapshot.discovery_failures == snapshot.discovery_requests:
                    state, stage = "failed", "failed"
                    message = "No jobs discovered: every discovery request failed. Check the activity log for provider errors."
                elif not snapshot.discovered:
                    state, stage = "completed", "complete"
                    message = "No jobs discovered. Check the web-result counts in the activity log; no jobs were scored."
                elif not snapshot.completed:
                    state, stage = "completed", "complete"
                    message = "Search finished with no scored jobs. Check the activity log for skipped candidates."
                else:
                    state, stage = "completed", "complete"
                    message = "Search complete. Review the scored jobs in the queue."
            self._set_state(state, message)
            self._emit(run_id, stage, message)
        except Exception:
            message = "Search stopped because an unexpected internal error occurred."
            self._set_state("failed", message)
            self._emit(run_id, "failed", message)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _process_candidate(
        self,
        request: SearchRequest,
        candidate: SearchCandidate,
        started: float,
    ) -> _ProcessedCandidate:
        if self._should_stop(started):
            return _ProcessedCandidate(None, None, "Search was cancelled.")
        if candidate.closed_reason:
            return _ProcessedCandidate(None, None, candidate.closed_reason)
        hard_skip_keywords = request.match_context.criteria.get("hard_skip_keywords", ())
        eligibility_reason = _eligibility_skip_reason(candidate, hard_skip_keywords)
        if eligibility_reason:
            return _ProcessedCandidate(None, None, eligibility_reason)
        if _posting_is_too_old(candidate.posted_date, request.criteria.posted_within_days):
            return _ProcessedCandidate(None, None, _stale_reason(candidate, request.criteria))

        if self._should_stop(started):
            return _ProcessedCandidate(None, None, "Search was cancelled.")
        self._increment(page_fetches=1)
        description = _snippet_description(candidate.description)
        posted_date = candidate.posted_date
        posted_date_verified = bool(posted_date)
        posted_date_source = "search provider" if posted_date else ""
        posted_date_reason = "" if posted_date else "Job page was not checked"
        apply_url = candidate.apply_url
        job_location = candidate.location
        quick_apply = ""
        availability = "unknown"
        availability_evidence = ""
        try:
            if self._uses_default_page_fetcher:
                page = fetch_job_html(
                    candidate.source_url,
                    allowed_domains=request.criteria.custom_domains,
                )
            else:
                page = self._page_fetcher(candidate.source_url)
        except Exception:
            page = ""
            if not posted_date:
                posted_date_reason = "Job page could not be loaded"

        if page and not _is_blocked_search_page(page):
            metadata = extract_job_metadata(page, candidate.source_url, snippet=candidate.description)
            quick_apply = metadata.quick_apply
            availability = metadata.availability
            availability_evidence = metadata.availability_evidence
            if availability == "expired":
                return _ProcessedCandidate(None, None, availability_evidence)
            if metadata.locations:
                job_location, geographic_match = match_job_locations(metadata, request.criteria.location_targets)
                if geographic_match is False:
                    return _ProcessedCandidate(None, None, f"Job location {', '.join(metadata.locations)} does not match {request.criteria.location_label}.")
            description = metadata.description
            posted_date = metadata.posted_date or posted_date
            apply_url = metadata.apply_url or apply_url
            if metadata.posted_date:
                posted_date_verified = metadata.posted_date_verified
                posted_date_source = metadata.posted_date_source
                posted_date_reason = metadata.posted_date_reason
            elif not posted_date:
                posted_date_verified = False
                posted_date_source = ""
                posted_date_reason = metadata.posted_date_reason
            page_text = BeautifulSoup(page, "html.parser").get_text(" ", strip=True)
            eligibility_reason = _eligibility_skip_reason(
                candidate, hard_skip_keywords, page_text=page_text
            )
            if eligibility_reason:
                return _ProcessedCandidate(None, None, eligibility_reason)
            closed_reason = _closed_job_reason(page_text)
            if closed_reason:
                return _ProcessedCandidate(None, None, closed_reason)
        elif page and not posted_date:
            posted_date_reason = "Job page was blocked"

        if _posting_is_too_old(posted_date, request.criteria.posted_within_days):
            return _ProcessedCandidate(
                None,
                None,
                _stale_reason(replace(candidate, posted_date=posted_date), request.criteria),
            )
        if job_location and _job_location_matches(job_location, request.criteria.location_targets) is False:
            return _ProcessedCandidate(None, None, f"Job location {job_location} does not match {request.criteria.location_label}.")
        if job_location and _job_location_matches(job_location, request.criteria.location_targets) is None:
            job_location = ""
        required_apply = APPLICATION_FILTERS.get(candidate.platform)
        if required_apply in request.criteria.application_filters and quick_apply != required_apply:
            return _ProcessedCandidate(None, None, f"{required_apply} could not be verified on this posting; strict platform filter.")
        job = JobInput(
            title=candidate.title,
            company=candidate.company,
            location=job_location,
            description=description.text or candidate.description,
            source_url=candidate.source_url,
            posted_date=posted_date,
            apply_url=apply_url,
            description_kind=description.kind,
            description_source=description.source,
            description_limitation=description.limitation,
            posted_date_verified=posted_date_verified,
            posted_date_source=posted_date_source,
            posted_date_reason=posted_date_reason,
            platform=candidate.platform,
            quick_apply=quick_apply,
            availability=availability,
            availability_evidence=availability_evidence,
        )
        if self._should_stop(started):
            return _ProcessedCandidate(None, None, "Search was cancelled.")
        self._increment(scoring_attempts=1)
        result = self._scorer(
            job,
            request.match_context,
            request.matching_config,
            self._score_cache,
            cancel=lambda: self._should_stop(started),
        )
        if not job_location:
            result = replace(result, remarks=(*result.remarks,
                "Job location was not exposed. The selected location is a search hint, not verified posting evidence."))
        return _ProcessedCandidate(job, result)

    def _publish_processed(
        self,
        run_id: str,
        future: Future[_ProcessedCandidate],
        original: SearchCandidate,
    ) -> None:
        try:
            processed = future.result()
        except Exception:
            processed = _ProcessedCandidate(None, None, "Job processing failed.")
        if processed.job is None or processed.result is None:
            if processed.skip_reason != "Search was cancelled.":
                self._increment(skipped=1, checked=1)
                self._emit(
                    run_id,
                    "skipped",
                    f"Skipped {original.title} at {original.company or 'unknown company'}: "
                    f"{processed.skip_reason}",
                )
            return
        self._matches.put(CompletedMatch(run_id, processed.job, processed.result))
        self._increment(completed=1, checked=1)
        self._emit(
            run_id,
            "matched",
            f"Scored {processed.job.title} at {processed.job.company or 'unknown company'} "
            f"({processed.result.score}/100, {processed.result.engine})."
            + (f" {processed.result.remarks[-1]}"
               if processed.result.engine == "Deterministic fallback" and processed.result.remarks
               else ""),
        )

    def _should_stop(self, started: float) -> bool:
        return self._cancel_event.is_set() or self._clock() - started >= self._deadline_seconds

    def _increment(self, **changes: int) -> None:
        with self._lock:
            values = self._snapshot.__dict__.copy()
            for key, amount in changes.items():
                values[key] = int(values[key]) + amount
            self._snapshot = RunSnapshot(**values)

    def _set_state(self, state: RunState, message: str) -> None:
        with self._lock:
            self._snapshot = replace(self._snapshot, state=state, message=message)

    def _emit(self, run_id: str, stage: str, message: str) -> None:
        snapshot = self.snapshot()
        self._events.put(
            RunEvent(
                run_id=run_id,
                stage=stage,
                checked=snapshot.checked,
                total=MAX_UNIQUE_RESULTS,
                message=message,
            )
        )

    @staticmethod
    def _drain_queue(queue: Queue) -> list:
        values = []
        while True:
            try:
                values.append(queue.get_nowait())
            except Empty:
                return values


def _planned_queries(
    criteria: SearchCriteria, provider: SearchProviderConfig
) -> list[PlatformQuery]:
    bounded = replace(criteria, max_results=MAX_UNIQUE_RESULTS)
    if provider.has_api_search:
        return build_serpapi_queries(bounded, provider.serpapi_key)[:MAX_SEARCH_REQUESTS]
    return build_public_fallback_queries(bounded)


def _parse_results(
    query: PlatformQuery, payload: str, location: str
) -> list[SearchCandidate]:
    if query.parser == "linkedin":
        return parse_linkedin_jobs(payload, location, MAX_UNIQUE_RESULTS)
    if query.parser == "serpapi":
        return parse_serpapi_results(payload, query.platform, location, MAX_UNIQUE_RESULTS)
    return parse_duckduckgo_results(payload, query.platform, location, MAX_UNIQUE_RESULTS)


def _candidate_identity(candidate: SearchCandidate) -> str:
    fingerprint = vacancy_fingerprint(candidate.title, candidate.company, candidate.location)
    if fingerprint:
        return f"vacancy:{fingerprint}"
    source = job_source(candidate.platform, candidate.source_url)
    if source.stable_id:
        return f"source:{source.platform.casefold()}:{source.stable_id}"
    canonical = canonicalize_job_url(candidate.source_url)
    return f"url:{canonical or candidate.source_url.casefold()}"


def _snippet_description(text: str) -> JobDescription:
    if text.strip():
        return JobDescription(
            text=text.strip(),
            kind="snippet",
            source="search result",
            limitation="Full job description was unavailable; score uses a search snippet.",
        )
    return JobDescription(
        text="",
        kind="unavailable",
        source="",
        limitation="No readable job description was available.",
    )


def _stale_reason(candidate: SearchCandidate, criteria: SearchCriteria) -> str:
    return (
        f"posted {candidate.posted_date}, older than {criteria.posted_within_days} days"
    )
