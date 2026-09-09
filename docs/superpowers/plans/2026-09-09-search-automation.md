# Search Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-testable Streamlit workflow that reads an uploaded CV, searches public job-result pages for selected platforms, scores up to 50 jobs, deduplicates them, and inserts them into the local queue.

**Architecture:** Keep CV parsing, public search, and queue ingestion in separate modules. The Streamlit app orchestrates the workflow and shows progress/logs, while the core logic remains testable without launching a browser.

**Tech Stack:** Python 3.11+, Streamlit, SQLite, optional pypdf for CV PDF text extraction, requests for public HTTP search, BeautifulSoup for HTML parsing.

**Spec:** `docs/PROJECT_SPEC.md`

## Global Constraints

- Keep actual CV files, extracted CV text, queue data, secrets, and preferences.local.yaml out of Git.
- Do not automate job-board login, CAPTCHA handling, or final application submission.
- Respect public-access boundaries and record blocked/skipped platform reasons in user-visible logs.
- Score all imported search results with existing deterministic scoring rules.
- Keep the Streamlit app deployable with `src/app.py` as entry point.
- Update version, changelog, and docs with every user-visible release.

---

### Task 1: CV Parsing

**Files:**
- Create: `src/job_hunter/cv_parser.py`
- Modify: `src/job_hunter/cv_store.py`
- Test: `tests/test_cv_parser.py`

**Interfaces:**
- Produces: `extract_cv_text_from_pdf_bytes(content: bytes) -> str`
- Produces: `detect_cv_signals(text: str, preferences: dict[str, object]) -> CVSignals`
- Produces: `CVStore.save_text(text: str) -> None` and `CVStore.load_text() -> str`

- [ ] Write failing tests for text joining, keyword detection, and store text roundtrip.
- [ ] Run the tests and verify they fail because the new module/methods do not exist.
- [ ] Implement minimal parsing helpers and CV text persistence.
- [ ] Run the focused tests and then the full suite.

### Task 2: Public Search Provider

**Files:**
- Create: `src/job_hunter/search.py`
- Test: `tests/test_search.py`

**Interfaces:**
- Produces: `SearchCriteria(title_terms: tuple[str, ...], description_terms: tuple[str, ...], location: str, platforms: tuple[str, ...], max_results: int)`
- Produces: `SearchCandidate(title: str, company: str, location: str, description: str, source_url: str, platform: str)`
- Produces: `parse_duckduckgo_results(html: str, platform: str, location: str, limit: int) -> list[SearchCandidate]`
- Produces: `build_search_queries(criteria: SearchCriteria) -> list[PlatformQuery]`

- [ ] Write failing tests for query construction and fixture HTML parsing.
- [ ] Run focused tests and verify expected failure.
- [ ] Implement query builders and parsing with BeautifulSoup.
- [ ] Run focused tests and then the full suite.

### Task 3: Search Run Ingestion

**Files:**
- Modify: `src/job_hunter/search.py`
- Test: `tests/test_search.py`

**Interfaces:**
- Produces: `run_public_search(criteria: SearchCriteria, preferences: dict[str, object], queue: JobQueue, fetcher: Callable[[str], str] | None = None) -> SearchRunSummary`
- Produces logs with checked, added, duplicate, and skipped counts.

- [ ] Write failing tests using a fake fetcher and temporary queue.
- [ ] Run focused tests and verify expected failure.
- [ ] Implement search run orchestration and queue insertion.
- [ ] Run focused tests and then the full suite.

### Task 4: Streamlit Wiring

**Files:**
- Modify: `src/app.py`
- Test: `tests/test_app_ui.py`

**Interfaces:**
- Consumes: `CVStore`, `detect_cv_signals`, `SearchCriteria`, `run_public_search`
- Produces: visible CV analysis, real search button, progress/log output, and queue refresh instructions.

- [ ] Write failing UI-helper tests for run labels or summary formatting.
- [ ] Run focused tests and verify expected failure.
- [ ] Wire the Streamlit page to parse CV text and run public search.
- [ ] Run AppTest smoke test and full test suite.

### Task 5: Versioning And Documentation

**Files:**
- Create: `CHANGELOG.md`
- Modify: `README.md`
- Modify: `docs/PROJECT_SPEC.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/DEVELOPMENT_PLAN.md`
- Modify: `pyproject.toml`
- Modify: `src/job_hunter/__init__.py`

**Interfaces:**
- Produces: version `1.4.0` and user-facing docs for production Streamlit testing.

- [ ] Update version to `1.4.0`.
- [ ] Document Streamlit production limitations and safe search behavior.
- [ ] Run full verification.
- [ ] Commit and push.
