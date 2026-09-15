# Session-Safe Gemini Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Job Hunter v1.14.0 with session-isolated public data, two Gemini matching modes, full-description enrichment, OR discovery, conservative deduplication, manual applied-job handling, and responsive cancellation.

**Architecture:** The hosted Streamlit app owns a `SessionWorkspace` and never opens shared CV or SQLite files. A shared search pipeline emits plain Python events from a bounded worker into a Streamlit fragment; deterministic exclusions run before a pluggable Gemini scorer with a session cache and labelled fallback.

**Tech Stack:** Python 3.11+, Streamlit 1.63.0, `google-genai`, requests, BeautifulSoup, pypdf, python-docx, dataclasses, SQLite for legacy local CLI only, unittest, Streamlit AppTest.

**Spec:** `docs/superpowers/specs/2026-09-15-session-gemini-search-design.md`

## Global Constraints

- Hosted CVs, queue data, application records, and score caches are session-only.
- Criteria mode must never load or send CV text.
- Gemini output is structured and evidence-based; missing or failed Gemini calls use a visible deterministic fallback.
- Search discovery is title OR description, with a hard limit of 50 unique candidates.
- Search has at most 12 discovery requests, 50 page fetches, 50 Gemini attempts, two job workers, and a five-minute scheduling deadline.
- No worker calls Streamlit or mutates `st.session_state`.
- Apply opens an external page and never changes application status.
- No CV text, private records, API keys, credential-bearing URLs, or model prompts are logged or committed.
- Every commit is preceded by `PYTHON_BIN=/Users/lilianyoctoria/Documents/job-hunter/.venv/bin/python ./tool/check.sh`.

---

## File Map

- Create `src/job_hunter/session_workspace.py`: session CV, queue, cache, application records, and queue-compatible operations.
- Create `src/job_hunter/job_identity.py`: canonical URLs, stable IDs, fingerprints, and source consolidation.
- Create `src/job_hunter/descriptions.py`: full/snippet/unavailable description extraction.
- Create `src/job_hunter/matching.py`: mode contexts, Gemini client adapter, cache keys, fallback orchestration.
- Create `src/job_hunter/search_runner.py`: cancellable background controller and event/result contracts.
- Modify `src/job_hunter/search.py`: OR discovery, custom domains, metadata provenance, and pure candidate-processing helpers.
- Modify `src/job_hunter/runtime_config.py`: Gemini model/key and hosted session configuration.
- Modify `src/job_hunter/queue_types.py`: enriched job input fields shared by session and local queues.
- Modify `src/job_hunter/queue.py`: compatible identity/application metadata for local CLI without making it the hosted store.
- Modify `src/job_hunter/app_ui.py`: actionable/applied filtering and enriched table rows.
- Modify `src/app.py`: session workspace, two modes, simplified controls, fragment polling, and Stop UI.
- Modify tests and fixtures under `tests/`: unit, integration, slow-mock cancellation, and Streamlit AppTest coverage.
- Modify public docs, secrets example, requirements, changelog, and version metadata for v1.14.0.

---

### Task 1: Session-Isolated Hosted Workspace

**Files:**
- Create: `src/job_hunter/session_workspace.py`
- Modify: `src/job_hunter/queue_types.py`
- Modify: `src/app.py`
- Test: `tests/test_session_workspace.py`
- Test: `tests/test_app_storage_boundary.py`

**Interfaces:**
- Produces: `SessionCV(filename: str, content: bytes, text: str)`.
- Produces: `SessionWorkspace(cv: SessionCV | None = None)`.
- Produces: `SessionWorkspace.save_cv(filename: str, content: bytes, text: str) -> None`.
- Produces: `SessionWorkspace.remove_cv() -> None`.
- Produces: `SessionWorkspace.add_scored_job(job: JobInput, score: ScoreResult) -> AddResult`.
- Produces: `SessionWorkspace.list_jobs() -> list[JobRecord]`.
- Produces: `SessionWorkspace.update_application_status(job_id: int, applied: bool) -> None`.
- Produces: `get_session_workspace(state: MutableMapping[str, object]) -> SessionWorkspace`.

- [x] **Step 1: Write session isolation and CV lifecycle tests**

```python
def test_workspaces_do_not_share_private_state():
    first = SessionWorkspace()
    second = SessionWorkspace()
    first.save_cv("cv.docx", b"doc", "Power BI")
    first.add_scored_job(
        JobInput(title="BI Analyst", description="Power BI", source_url="https://example.com/jobs/1"),
        ScoreResult(90, "shortlist", ("Power BI",), (), DEFAULT_WEIGHTS),
    )
    assert first.cv is not None
    assert second.cv is None
    assert second.list_jobs() == []


def test_replacing_and_removing_cv_clear_cv_cache_entries():
    workspace = SessionWorkspace()
    result = ScoreResult(90, "shortlist", ("Power BI",), (), DEFAULT_WEIGHTS)
    workspace.score_cache["cv:old"] = result
    workspace.score_cache["criteria:keep"] = result
    workspace.save_cv("cv.pdf", b"pdf", "SSRS")
    assert "cv:old" not in workspace.score_cache
    assert "criteria:keep" in workspace.score_cache
    workspace.remove_cv()
    assert workspace.cv is None
```

- [x] **Step 2: Write the hosted storage boundary test**

```python
def test_streamlit_entrypoint_does_not_construct_disk_stores():
    source = Path("src/app.py").read_text(encoding="utf-8")
    assert "JobQueue(DB_PATH)" not in source
    assert "CVStore(CV_STORAGE_DIR)" not in source
    assert "get_session_workspace(st.session_state)" in source
```

- [x] **Step 3: Run the new tests and verify failure**

Run:

```bash
PYTHONPATH=src /Users/lilianyoctoria/Documents/job-hunter/.venv/bin/python -m unittest tests.test_session_workspace tests.test_app_storage_boundary -v
```

Expected: FAIL because `session_workspace` and `get_session_workspace` do not exist.

- [x] **Step 4: Implement the session workspace and hosted wiring**

Use dataclasses and in-memory collections only. Generate monotonically
increasing session job IDs, preserve queue ordering by score then ID, and expose
the subset of queue methods consumed by Streamlit. Replace the hosted
`JobQueue(DB_PATH)` and `CVStore(CV_STORAGE_DIR)` construction in `main()` with:

```python
workspace = get_session_workspace(st.session_state)
```

Keep `JobQueue` and `CVStore` unchanged for local CLI compatibility.

- [x] **Step 5: Run focused and complete tests**

Run the focused command from Step 3, then the global check. Expected: PASS.

- [x] **Step 6: Commit the storage boundary**

```bash
git add src/app.py src/job_hunter/session_workspace.py src/job_hunter/queue_types.py tests/test_session_workspace.py tests/test_app_storage_boundary.py
git commit -m "Protect hosted job data with session storage"
```

---

### Task 2: Description Quality And Posting-Date Provenance

**Files:**
- Create: `src/job_hunter/descriptions.py`
- Modify: `src/job_hunter/search.py`
- Modify: `src/job_hunter/queue_types.py`
- Test: `tests/test_descriptions.py`
- Test: `tests/test_search_dates.py`
- Create: `tests/fixtures/jobs/linkedin_inconsistent_dates.html`
- Create: `tests/fixtures/jobs/linkedin_structured_description.html`
- Create: `tests/fixtures/jobs/generic_updated_page.html`

**Interfaces:**
- Produces: `DescriptionKind = Literal["full", "snippet", "unavailable"]`.
- Produces: `JobDescription(text: str, kind: str, source: str, limitation: str)`.
- Produces: `extract_job_description(html: str, snippet: str = "") -> JobDescription`.
- Extends: `JobPageMetadata(posted_date: str, posted_date_verified: bool, posted_date_source: str, posted_date_reason: str, apply_url: str, description: JobDescription)`.

- [x] **Step 1: Write description extraction acceptance tests**

```python
def test_structured_jobposting_description_replaces_snippet():
    html = fixture("linkedin_structured_description.html")
    result = extract_job_description(html, snippet="Short search text")
    assert result.kind == "full"
    assert "Power BI" in result.text
    assert result.source == "JobPosting.description"


def test_blocked_or_content_free_page_retains_snippet_limit():
    result = extract_job_description("<html><title>Access denied</title></html>", "BI role")
    assert result.kind == "snippet"
    assert result.text == "BI role"
    assert result.limitation
```

- [x] **Step 2: Write date provenance regression tests**

```python
def test_jobposting_date_wins_over_updated_and_application_dates():
    metadata = extract_job_metadata(fixture("linkedin_inconsistent_dates.html"), SOURCE, today=date(2026, 9, 15))
    assert metadata.posted_date == "2026-09-10"
    assert metadata.posted_date_verified is True
    assert metadata.posted_date_source == "JobPosting.datePosted"


def test_generic_updated_page_does_not_become_posting_date():
    metadata = extract_job_metadata(fixture("generic_updated_page.html"), SOURCE)
    assert metadata.posted_date == ""
    assert metadata.posted_date_verified is False
    assert metadata.posted_date_reason == "No job-specific posting date found"
```

- [x] **Step 3: Run focused tests and verify failure**

Run the two new test modules. Expected: FAIL on missing module and provenance fields.

- [x] **Step 4: Implement structured/container description extraction**

Walk JSON-LD objects for `@type: JobPosting`, strip HTML in
`description`, then inspect known job-description selectors. Remove script,
style, nav, footer, form, and cookie/banner nodes. Require meaningful length and
job-language signals before labelling container text `full`; otherwise retain
the supplied snippet or return `unavailable`.

- [x] **Step 5: Narrow posting-date sources and attach reasons**

Prefer `JobPosting.datePosted`, known provider posting fields, job-specific time
nodes, and posting-labelled text. Remove generic article publish/update metadata
from accepted sources. Keep absolute and relative normalization. Record an
explicit reason for blocked, missing, malformed, or ambiguous dates.

- [x] **Step 6: Run focused and complete tests, then commit**

```bash
git add src/job_hunter/descriptions.py src/job_hunter/search.py src/job_hunter/queue_types.py tests/test_descriptions.py tests/test_search_dates.py tests/fixtures/jobs
git commit -m "Use full job descriptions and verified dates"
```

---

### Task 3: Mode-Specific Gemini Matching And Cache

**Files:**
- Create: `src/job_hunter/matching.py`
- Modify: `src/job_hunter/runtime_config.py`
- Modify: `src/job_hunter/scoring.py`
- Modify: `src/job_hunter/session_workspace.py`
- Modify: `requirements.txt`
- Modify: `.streamlit/secrets.example.toml`
- Test: `tests/test_matching.py`
- Test: `tests/test_runtime_config.py`

**Interfaces:**
- Produces: `MatchMode = Literal["cv", "criteria"]`.
- Produces: `MatchContext(mode: str, criteria: dict[str, object], cv_text: str = "")` with validation that criteria mode has empty CV text.
- Produces: `MatchingConfig(api_key: str = "", model: str = "gemini-2.5-flash", prompt_version: str = "v1.14")`.
- Produces: `MatchResult(score: int, decision: str, reasons: tuple[str, ...], remarks: tuple[str, ...], engine: str, model: str, limited: bool, cache_hit: bool)`.
- Produces: `score_match(job: JobInput, context: MatchContext, config: MatchingConfig, cache: MutableMapping[str, MatchResult], client: GeminiClient | None = None, cancel: Callable[[], bool] | None = None) -> MatchResult`.

- [x] **Step 1: Write mode isolation tests**

```python
def test_criteria_mode_payload_never_contains_cv_text():
    criteria = {"target_roles": ["BI Analyst"], "primary_keywords": ["Power BI"]}
    client = RecordingGeminiClient(
        {"score": 92, "decision": "shortlist", "reasons": ["Power BI"], "remarks": []}
    )
    context = MatchContext(mode="criteria", criteria=criteria, cv_text="")
    score_match(
        JobInput(title="BI Analyst", description="Power BI"),
        context,
        MatchingConfig(api_key="test-key"),
        {},
        client=client,
    )
    assert "private cv phrase" not in client.last_prompt
    assert client.last_payload["candidate"] == {"criteria": criteria}


def test_cv_mode_requires_nonempty_readable_text():
    with self.assertRaisesRegex(ValueError, "readable CV"):
        MatchContext(mode="cv", criteria={}, cv_text="")
```

Define `RecordingGeminiClient` in the test module with one `generate(payload,
prompt)` method that stores both arguments and returns the constructor result.
The production `GeminiClient` protocol uses that same signature so no live API
is involved in these tests.

- [x] **Step 2: Write Gemini, fallback, retry, and cache tests**

Cover structured success, missing key, 429 then success, two 429 failures,
authentication failure, timeout, malformed JSON, cancellation before retry, and
cache invalidation after job text, mode input, model, or prompt version changes.
Assert every fallback result has `engine == "Deterministic fallback"` and
`limited is True`.

- [x] **Step 3: Run matching tests and verify failure**

Expected: FAIL because `matching.py` and Gemini configuration do not exist.

- [x] **Step 4: Add the official SDK and runtime configuration**

Add `google-genai>=1.33.0,<2` to requirements. Load `GEMINI_API_KEY` and optional
`GEMINI_MODEL` from Streamlit secrets or environment without ever including
their values in reprs, logs, URLs, or exceptions.

- [x] **Step 5: Implement the scorer**

Build structured JSON output with score, decision, reasons, and remarks. The
prompt must state that only supplied candidate evidence is valid and missing
requirements remain unsupported. Configure low temperature, bounded output,
short HTTP timeout, and two total attempts. Classify auth, quota/rate-limit,
timeout, invalid-response, and cancellation outcomes into sanitized errors.
Use deterministic `score_job` for a clearly labelled fallback.

- [x] **Step 6: Implement content-addressed session cache**

Hash canonical JSON containing job title/company/location/description and kind,
mode-specific candidate input, model, and prompt version. Never expose raw cache
input. Return a copied result with `cache_hit=True` on hits.

- [x] **Step 7: Install dependency, run tests, and commit**

```bash
/Users/lilianyoctoria/Documents/job-hunter/.venv/bin/python -m pip install -r requirements.txt
git add requirements.txt .streamlit/secrets.example.toml src/job_hunter/matching.py src/job_hunter/runtime_config.py src/job_hunter/scoring.py src/job_hunter/session_workspace.py tests/test_matching.py tests/test_runtime_config.py
git commit -m "Add mode-specific Gemini job matching"
```

---

### Task 4: OR Discovery And Custom Source Validation

**Files:**
- Modify: `src/job_hunter/search.py`
- Create: `src/job_hunter/source_validation.py`
- Test: `tests/test_search_discovery.py`
- Test: `tests/test_source_validation.py`

**Interfaces:**
- Produces: `CustomSource(hostname: str, site_filter: str)`.
- Produces: `validate_custom_sources(values: Iterable[str], has_api_search: bool) -> tuple[tuple[CustomSource, ...], tuple[str, ...]]`.
- Changes: `build_serpapi_queries(criteria, api_key) -> list[PlatformQuery]` emits distinct `signal="title"` and `signal="description"` queries.
- Changes: the UI never sets `SearchCriteria.max_results`; pipeline constant `MAX_UNIQUE_RESULTS = 50` is authoritative while the field may remain for compatibility tests.

- [x] **Step 1: Write OR discovery tests**

```python
def test_queries_discover_by_title_or_description_separately():
    criteria = SearchCriteria(
        title_terms=("Data Analyst",),
        description_terms=("Power BI",),
        location="Kuala Lumpur",
        platforms=("LinkedIn",),
        posted_within_days=30,
    )
    queries = build_serpapi_queries(criteria, "secret")
    linkedin = [query for query in queries if query.platform == "LinkedIn"]
    assert {query.signal for query in linkedin} == {"title", "description"}
    assert '"Data Analyst"' in next(q.query for q in linkedin if q.signal == "title")
    assert '"Power BI"' in next(q.query for q in linkedin if q.signal == "description")
```

- [x] **Step 2: Write custom-source security tests**

Accept `careers.example.com` and `https://careers.example.com/jobs`; normalize
both to one host. Reject HTTP, credentials, paths that do not resolve to a host,
localhost, loopback/private IPs, more than five unique hosts, and all custom
sources when SerpAPI is unavailable. Assert API keys are absent from validation
messages.

- [x] **Step 3: Run focused tests and verify failure**

Expected: FAIL because queries have no signal split and validation module is missing.

- [x] **Step 4: Implement bounded query planning**

Emit title and description query families, then deterministically cap the plan
at 12 requests while giving each selected predefined source one query before
second-signal queries. Add custom site filters only when SerpAPI is active.
Retain location and posting-age filters on all planned queries.

- [x] **Step 5: Implement source validation and run tests**

Parse with `urllib.parse`, resolve literal IPs with `ipaddress`, normalize IDNA
hostnames, strip `www.`, and return concise user-facing errors. Do not perform
DNS lookups or claim native platform integration.

- [x] **Step 6: Run complete check and commit**

```bash
git add src/job_hunter/search.py src/job_hunter/source_validation.py tests/test_search_discovery.py tests/test_source_validation.py
git commit -m "Broaden discovery with validated custom sources"
```

---

### Task 5: Stable Identity, Alternate Sources, And Applied Records

**Files:**
- Create: `src/job_hunter/job_identity.py`
- Modify: `src/job_hunter/queue_types.py`
- Modify: `src/job_hunter/session_workspace.py`
- Modify: `src/job_hunter/queue.py`
- Modify: `src/job_hunter/app_ui.py`
- Test: `tests/test_job_identity.py`
- Modify: `tests/test_session_workspace.py`
- Modify: `tests/test_queue.py`
- Modify: `tests/test_app_ui.py`

**Interfaces:**
- Produces: `JobSource(platform: str, original_url: str, canonical_url: str, stable_id: str = "")`.
- Produces: `canonicalize_job_url(url: str) -> str`.
- Produces: `stable_job_id(platform: str, url: str) -> str`.
- Produces: `vacancy_fingerprint(title: str, company: str, location: str) -> str`.
- Extends: `JobRecord.sources: tuple[JobSource, ...]`.
- Extends: `JobRecord.application_recorded_at: str` and `application_evidence: str`.
- Produces: `filter_jobs(..., application_view: str = "actionable")` where values are `actionable`, `all`, and `applied`.

- [x] **Step 1: Write URL and stable-ID tests**

```python
def test_tracking_variants_have_one_canonical_url():
    first = "https://www.linkedin.com/jobs/view/123/?trk=feed&utm_source=x"
    second = "https://linkedin.com/jobs/view/123#details"
    assert canonicalize_job_url(first) == canonicalize_job_url(second)
    assert stable_job_id("LinkedIn", first) == "123"


def test_generic_apply_url_is_not_a_vacancy_identity():
    first = JobInput(
        title="BI Analyst",
        company="Acme",
        location="Kuala Lumpur",
        source_url="https://example.com/jobs/1",
        apply_url="https://boards.greenhouse.io/acme",
    )
    second = JobInput(
        title="Data Engineer",
        company="Acme",
        location="Kuala Lumpur",
        source_url="https://example.com/jobs/2",
        apply_url="https://boards.greenhouse.io/acme",
    )
    result = MatchResult(80, "review", ("Relevant role",), (), "Gemini", "gemini-2.5-flash", False, False)
    workspace = SessionWorkspace()
    assert workspace.add_scored_job(first, result).created
    assert workspace.add_scored_job(second, result).created
```

- [x] **Step 2: Write cross-source and application-record tests**

Add a same-vacancy Foundit/LinkedIn pair with matching specific title, employer,
and location. Assert one record contains both source links. Add a Foundit record
whose Apply URL points to LinkedIn but whose vacancy fields differ; assert two
records. Mark the consolidated record applied, add another confident source,
and assert status and evidence remain attached.

- [x] **Step 3: Write queue presentation tests**

Assert the default `actionable` view excludes applied jobs, `applied` shows
them, row decision is `Already applied`, and remarks include
`Marked manually by the user; not verified with the job platform`. Assert Apply
link selection never calls the status updater.

- [x] **Step 4: Run focused tests and verify failure**

Expected: FAIL on missing identity module, sources, and application views.

- [x] **Step 5: Implement identity resolution and source consolidation**

Strip only known tracking query keys. Parse LinkedIn numeric view/currentJobId,
Indeed `jk`, JobStreet path IDs, and Foundit path IDs. Use stable source identity,
then canonical URL, then a nonempty normalized title/company/location
fingerprint. Never use `apply_url` for identity. Preserve all safe source links.

- [x] **Step 6: Implement applied-record semantics**

Record UTC timestamp and fixed manual evidence only on the explicit status
control. Present computed decision `Already applied` without overwriting the
original match decision. Keep additive local SQLite columns for CLI
compatibility, but do not route hosted state through SQLite.

- [x] **Step 7: Run complete tests and commit**

```bash
git add src/job_hunter/job_identity.py src/job_hunter/queue_types.py src/job_hunter/session_workspace.py src/job_hunter/queue.py src/job_hunter/app_ui.py tests/test_job_identity.py tests/test_session_workspace.py tests/test_queue.py tests/test_app_ui.py
git commit -m "Consolidate job sources and applied records"
```

---

### Task 6: Shared Cancellable Search Pipeline

**Files:**
- Create: `src/job_hunter/search_runner.py`
- Modify: `src/job_hunter/search.py`
- Modify: `src/job_hunter/session_workspace.py`
- Test: `tests/test_search_runner.py`
- Modify: `tests/test_search.py`

**Interfaces:**
- Produces: `RunState = Literal["idle", "running", "completed", "cancelled", "failed"]`.
- Produces: `RunEvent(run_id: str, stage: str, checked: int, total: int, message: str)`.
- Produces: `CompletedMatch(run_id: str, job: JobInput, result: MatchResult)`.
- Produces: `SearchRunController.start(request: SearchRequest) -> None`.
- Produces: `SearchRunController.cancel() -> None`.
- Produces: `SearchRunController.drain() -> tuple[tuple[RunEvent, ...], tuple[CompletedMatch, ...]]`.
- Produces: `SearchRunController.snapshot() -> RunSnapshot`.
- Produces: `SessionWorkspace.accept_completed(match: CompletedMatch) -> bool` returning false for stale run IDs.

- [x] **Step 1: Write slow-mock cancellation tests**

```python
def test_cancel_stops_new_work_and_preserves_completed_results():
    first_result_ready = Event()
    release = Event()
    fetcher = BlockingFetcher(first_result_ready, release)
    controller = SearchRunController(fetcher=fetcher, scorer=StaticScorer(), max_workers=2)
    controller.start(
        SearchRequest(
            criteria=SearchCriteria(
                title_terms=("BI Analyst",),
                description_terms=("Power BI",),
                location="Kuala Lumpur",
                platforms=("LinkedIn",),
                posted_within_days=30,
            ),
            match_context=MatchContext(
                mode="criteria",
                criteria={"target_roles": ["BI Analyst"]},
            ),
        )
    )
    assert first_result_ready.wait(1)
    controller.cancel()
    fetcher.release.set()
    controller.wait(timeout=2)
    snapshot = controller.snapshot()
    assert snapshot.state == "cancelled"
    assert snapshot.completed >= 1
    assert fetcher.calls < snapshot.discovered
```

Define `BlockingFetcher` with a thread-safe `calls` counter and ten discovered
`JobInput` values. Its first page fetch sets `first_result_ready` and waits on
`release` for at most one second. Define `StaticScorer.score(...)` to return a
fixed `MatchResult` immediately. These exact fakes make scheduling counts and
cancellation timing deterministic.

- [x] **Step 2: Write stale-run and retry cancellation tests**

Start run A, cancel it, start run B, then release A's blocked result. Assert
`accept_completed` rejects A and accepts B. Mock a retryable Gemini error, cancel
before the retry delay, and assert only one Gemini call. Assert no new page fetch
begins after cancellation.

- [x] **Step 3: Write ceiling tests**

Provide unlimited duplicate and failure generators. Assert at most 12 discovery
requests, 50 page fetches, 50 Gemini attempts, 50 accepted unique results, two
concurrent tasks, and no scheduling after the deadline clock reaches 300 seconds.

- [x] **Step 4: Run focused tests and verify failure**

Expected: FAIL because `search_runner.py` does not exist.

- [x] **Step 5: Extract pure candidate processing from synchronous search**

Separate query discovery, cheap identity check, page enrichment, deterministic
exclusions, Gemini scoring, and completion publication. Insert cancellation
checks before and after each stage. Keep `run_public_search` as a compatibility
wrapper used by CLI/tests until callers are migrated.

- [x] **Step 6: Implement the controller**

Use one coordinator thread and `ThreadPoolExecutor(max_workers=2)`. Use
`threading.Event`, `queue.Queue`, UUID run IDs, injected monotonic clock, and
bounded request/scoring counters. Workers publish immutable data only. Controller
shutdown must be nonblocking for the Streamlit rerun path and bounded in tests.

- [x] **Step 7: Run focused and complete tests, then commit**

```bash
git add src/job_hunter/search_runner.py src/job_hunter/search.py src/job_hunter/session_workspace.py tests/test_search_runner.py tests/test_search.py
git commit -m "Add cancellable shared search pipeline"
```

---

### Task 7: Streamlit Modes, Progress, Stop, And Queue UX

**Files:**
- Modify: `src/app.py`
- Modify: `src/job_hunter/app_ui.py`
- Modify: `tests/test_app_navigation.py`
- Modify: `tests/test_app_ui.py`
- Create: `tests/test_streamlit_app.py`

**Interfaces:**
- Consumes: `SessionWorkspace`, `MatchContext`, validated custom sources, and `SearchRunController`.
- Produces: `_render_run_fragment(workspace: SessionWorkspace) -> None` decorated with `@st.fragment(run_every=...)`.
- Produces: `_search_is_ready(mode: str, workspace: SessionWorkspace, criteria: SearchCriteria) -> tuple[bool, str]`.

- [x] **Step 1: Write Streamlit acceptance tests**

Use `streamlit.testing.v1.AppTest` with mocked provider/model adapters to assert:

```python
def test_stop_button_state_tracks_run():
    app = AppTest.from_file("src/app.py").run()
    assert app.button(key="stop_search").disabled
    app.button(key="run_search").click().run()
    assert not app.button(key="stop_search").disabled


def test_cv_mode_requires_cv_and_offers_upload_navigation():
    app = AppTest.from_file("src/app.py").run()
    app.radio(key="search_mode").set_value("CV-based search").run()
    assert app.button(key="run_search").disabled
    assert app.button(key="open_profile").label == "Upload CV"
```

Also verify criteria mode runs without CV, `CV Saved` wording, Replace/Remove,
free-text location, custom-source errors, no strong-target/max-jobs widgets,
progress/log updates, Cancelled terminal label, and Review Job queue navigation.

- [x] **Step 2: Write queue interaction tests**

Assert default Actionable excludes applied records, Already applied filter shows
them, manual status control updates evidence, descriptions and date limitations
wrap visibly, alternate source links render, and Apply does not change status.

- [x] **Step 3: Run Streamlit tests and verify failure**

Expected: FAIL because current app uses disk stores, one implicit criteria mode,
synchronous search, and obsolete controls.

- [x] **Step 4: Rebuild only the affected Streamlit flow**

Keep Profile, Search, and Queue navigation and current visual theme. Add the
sidebar mode selector, accurate session privacy copy, unified criteria panel,
free-text/suggested location, validated custom-source input, fixed 50-result
caption, and no strong-target/max control. Do not create new pages.

- [x] **Step 5: Add fragment polling and Stop control**

Start the controller once, render recent events and progress from immutable
snapshots, drain completed matches into the active workspace, and rerun the
fragment while state is running. Stop sets cancellation and immediately changes
the visible state to Cancelling; terminal state becomes Cancelled after workers
settle. Ignore every result whose run ID is no longer active.

- [x] **Step 6: Update the queue UX**

Default to Actionable, offer All and Already applied, display scoring engine,
description quality, posting-date reason, application evidence, and alternate
source links. Keep the explicit external Apply boundary.

- [x] **Step 7: Run Streamlit, focused, and complete tests; commit**

```bash
git add src/app.py src/job_hunter/app_ui.py tests/test_app_navigation.py tests/test_app_ui.py tests/test_streamlit_app.py
git commit -m "Expose session-safe search modes and cancellation"
```

---

### Task 8: Release Documentation And Verification

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/PROJECT_SPEC.md`
- Modify: `docs/JOB_SCORING.md`
- Modify: `docs/APPLICATION_PIPELINE.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/DEVELOPMENT_PLAN.md`
- Create or Modify: `CHANGELOG.md`
- Modify: `src/job_hunter/__init__.py`
- Modify: tests that assert deployment/version contracts.

**Interfaces:**
- Documents: v1.14.0 behavior, session privacy, Gemini secret, labelled fallback,
  two modes, 50-job ceiling, cancellation guarantees, applied records, and
  deployment limitations.

- [ ] **Step 1: Write documentation/version contract tests**

Assert README contains `v1.14.0`, `GEMINI_API_KEY`, session-only privacy,
Criteria-based and CV-based mode instructions, and cancellation limitations.
Assert obsolete Strong-match goal and maximum-jobs instructions are absent.
Assert secrets examples contain blank example values only.

- [ ] **Step 2: Run contract tests and verify failure**

Expected: FAIL because docs still describe v1.13 deterministic shared storage and obsolete controls.

- [ ] **Step 3: Update documentation and changelog**

Describe exactly what is implemented. Include local setup, Streamlit secrets,
search/API limits, full/snippet/unavailable labels, cache behavior, manual
application evidence, and session reset behavior. Do not claim live Gemini or
production behavior until separately verified.

- [ ] **Step 4: Run all automated verification**

```bash
PYTHON_BIN=/Users/lilianyoctoria/Documents/job-hunter/.venv/bin/python ./tool/check.sh
/Users/lilianyoctoria/Documents/job-hunter/.venv/bin/python -m compileall -q src tests
/Users/lilianyoctoria/Documents/job-hunter/.venv/bin/python -m pip check
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 5: Run local Streamlit browser smoke tests**

Start the app on an unused localhost port. Verify desktop and narrow viewport:
Profile CV lifecycle with a generated non-private test DOCX, both search modes
with mocked adapters, running/Stop/Cancelled states, actionable/applied filters,
wrapped queue content, and no console/server exceptions. Remove generated test
artifacts after verification.

- [ ] **Step 6: Perform code and privacy review**

Review `git diff 3e03e90...HEAD` for correctness, unsafe URL handling,
cross-session state, late worker writes, secret/CV leakage, unbounded calls,
misleading copy, and unrelated refactors. Resolve every blocking finding and
rerun Step 4.

- [ ] **Step 7: Commit the release**

```bash
git add README.md AGENTS.md CHANGELOG.md docs src/job_hunter/__init__.py tests
git commit -m "Release Job Hunter 1.14.0"
```

- [ ] **Step 8: Push feature branch and verify CI**

```bash
git push -u origin codex/session-gemini-pipeline-v1-14
gh run list --repo agustiarfalahi94/job-hunter --branch codex/session-gemini-pipeline-v1-14 --limit 1
```

Wait for the exact feature-branch CI run to complete successfully.

- [ ] **Step 9: Merge to main and verify CI**

Fast-forward or merge only after the feature CI succeeds and the worktree is
clean. Push `main`, then wait for the exact main CI run to complete successfully.

- [ ] **Step 10: Verify production separately**

Open `https://jobs-hunter.streamlit.app/` only after Streamlit redeploys the
main commit. Confirm v1.14 controls and session privacy copy without uploading a
real CV or consuming search/Gemini quota. Run one permitted minimal live search
only when both configured secrets are available and record exactly what was and
was not verified.
