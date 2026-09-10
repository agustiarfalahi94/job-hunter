# Streamlined Search and Apply Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a single optional-CV search workflow with trustworthy posting dates and working, safe application links.

**Architecture:** Extend the existing search candidates and SQLite queue with normalized posting dates and discovered application URLs. Keep the Streamlit app server-rendered and local-first, but simplify its navigation to Profile, Search, and Queue; application actions use safe HTTPS links rather than pretending that a hosted server can control third-party logged-in sessions.

**Tech Stack:** Python 3.11+, Streamlit, SQLite, BeautifulSoup, requests, pytest

**Spec:** `docs/superpowers/specs/2026-09-10-search-queue-apply-design.md`

## Global Constraints

- CV upload is optional; keyword-only search and scoring must work without it.
- Posting freshness must use a real parsed date or display `Unknown`, never application status.
- The Streamlit interface must not expose draft export, packet export, or application status controls.
- Apply destinations must use HTTPS and open in a new browser tab.
- LinkedIn automation, CAPTCHA bypass, credential storage, and false submission claims are prohibited.
- Existing SQLite data must be migrated additively without deletion.
- Release version is `1.11.0`.

---

### Task 1: Posting Date and Apply Destination Domain Model

**Files:**
- Modify: `src/job_hunter/queue_types.py`
- Modify: `src/job_hunter/queue.py`
- Modify: `src/job_hunter/search.py`
- Test: `tests/test_queue.py`
- Test: `tests/test_search.py`

**Interfaces:**
- Produces: `JobInput.posted_date: str`, `JobInput.apply_url: str`
- Produces: `JobRecord.posted_date: str`, `JobRecord.apply_url: str`
- Produces: `normalize_posted_date(value: str, today: date | None = None) -> str`
- Produces: `extract_job_metadata(html: str, source_url: str) -> JobPageMetadata`

- [ ] **Step 1: Write failing queue tests**

Add tests proving a fresh database stores `posted_date` and `apply_url`, and an old database gains both columns without losing its existing row.

- [ ] **Step 2: Run queue tests to verify RED**

Run: `pytest -q tests/test_queue.py`

Expected: failures because queue inputs, records, and schema do not expose the new fields.

- [ ] **Step 3: Implement the additive queue migration**

Add default-empty fields to `JobInput` and `JobRecord`, extend insert/select mapping, and call `_ensure_column` for:

```python
_ensure_column(conn, "jobs", "posted_date", "TEXT NOT NULL DEFAULT ''")
_ensure_column(conn, "jobs", "apply_url", "TEXT NOT NULL DEFAULT ''")
```

- [ ] **Step 4: Run queue tests to verify GREEN**

Run: `pytest -q tests/test_queue.py`

Expected: all queue tests pass.

- [ ] **Step 5: Write failing search metadata tests**

Cover ISO dates, relative dates, LinkedIn `<time datetime>`, JSON-LD `datePosted`, safe relative Apply links, unsafe non-HTTPS links, SerpAPI `date`, and skipping a known date older than the selected age.

- [ ] **Step 6: Run search tests to verify RED**

Run: `pytest -q tests/test_search.py`

Expected: failures because normalized metadata and recency enforcement are missing.

- [ ] **Step 7: Implement search metadata extraction**

Use `datetime`, JSON-LD parsing, `urljoin`, and BeautifulSoup. Preserve search-card dates unless structured destination metadata provides a more precise value. Add the parsed fields to `JobInput`, reject known stale results, and retain unknown dates for user review.

- [ ] **Step 8: Run focused tests to verify GREEN**

Run: `pytest -q tests/test_search.py tests/test_queue.py`

Expected: all focused tests pass.

- [ ] **Step 9: Commit the domain change**

```bash
git add src/job_hunter/queue_types.py src/job_hunter/queue.py src/job_hunter/search.py tests/test_queue.py tests/test_search.py
git commit -m "Add trustworthy job dates and apply destinations"
```

### Task 2: Simplify the Streamlit Workflow

**Files:**
- Modify: `src/app.py`
- Modify: `src/job_hunter/app_ui.py`
- Test: `tests/test_app_ui.py`
- Test: `tests/test_app_navigation.py`

**Interfaces:**
- Consumes: `JobRecord.posted_date`, `JobRecord.apply_url`
- Produces: `jobs_to_rows()` rows with `Posted` and without `Status`
- Produces: one navigation control containing `Profile & CV`, `Search jobs`, and `Job queue`

- [ ] **Step 1: Write failing UI helper tests**

Assert queue rows contain `Posted`, omit `Status`, and decision filtering works without a required status argument.

- [ ] **Step 2: Run UI tests to verify RED**

Run: `pytest -q tests/test_app_ui.py`

Expected: failures because rows still expose application status.

- [ ] **Step 3: Implement UI row changes**

Render an ISO date or `Unknown`; retain legacy status helpers only where old CLI compatibility requires them.

- [ ] **Step 4: Write failing AppTest navigation tests**

Assert the app presents exactly the three active pages, search copy says CV is optional, and the queue no longer shows Status, Export draft, Export packet, or Set status.

- [ ] **Step 5: Run AppTest to verify RED**

Run: `pytest -q tests/test_app_navigation.py`

Expected: failures because the app still contains automated/manual branches.

- [ ] **Step 6: Implement the single workflow**

Remove the sidebar workflow switch and manual pages from routing. Rename Search setup to Search jobs, revise empty states, keep criteria editable, and make no-CV mode explicit.

- [ ] **Step 7: Add a functional Apply link**

For the selected queue item, choose `apply_url` when it is valid HTTPS, otherwise use a valid HTTPS `source_url`. Render `st.link_button("Apply", destination, ...)` so the browser opens a new tab. Disable it with a clear explanation when neither URL is safe.

- [ ] **Step 8: Run UI tests to verify GREEN**

Run: `pytest -q tests/test_app_ui.py tests/test_app_navigation.py`

Expected: all UI tests pass.

- [ ] **Step 9: Commit the interface change**

```bash
git add src/app.py src/job_hunter/app_ui.py tests/test_app_ui.py tests/test_app_navigation.py
git commit -m "Streamline search queue and apply workflow"
```

### Task 3: Release Documentation and Versioning

**Files:**
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/PROJECT_SPEC.md`
- Modify: `docs/APPLICATION_PIPELINE.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/DEVELOPMENT_PLAN.md`
- Modify: `docs/JOB_SCORING.md`

**Interfaces:**
- Consumes: implemented v1.11 behavior
- Produces: user-facing setup and usage instructions that match production

- [ ] **Step 1: Update version to 1.11.0**

Set `[project].version = "1.11.0"`.

- [ ] **Step 2: Rewrite active workflow documentation**

Document optional CV search, posting-age semantics, `Unknown` dates, duplicate handling, working Apply links, and the honest platform/login/CAPTCHA boundary. Remove active instructions for manual scoring, drafts, packets, and status updates.

- [ ] **Step 3: Add the 1.11.0 changelog entry**

List the new search flow, date migration, application destination discovery, UI removals, and compatibility behavior.

- [ ] **Step 4: Validate documentation references**

Run: `rg -n "Manual scoring|Export draft|Export packet|Set status|Status.*new" README.md docs src/app.py`

Expected: no stale active-workflow copy remains.

- [ ] **Step 5: Commit documentation**

```bash
git add pyproject.toml README.md CHANGELOG.md docs
git commit -m "Document Job Hunter 1.11 workflow"
```

### Task 4: Full Review, Production Smoke Test, and Delivery

**Files:**
- Review: all changed files
- Test: complete suite

**Interfaces:**
- Consumes: Tasks 1-3
- Produces: reviewed, pushed release branch and production-ready main

- [ ] **Step 1: Run the complete automated checks**

Run: `pytest -q`

Run: `python -m py_compile src/app.py src/job_hunter/*.py`

Run: `python -m pip check`

Run: `git diff --check`

Expected: every command exits successfully.

- [ ] **Step 2: Review the feature diff**

Inspect for data loss, unsafe URLs, stale status copy, private information, test gaps, and Streamlit import/runtime errors. Fix findings with a failing regression test first.

- [ ] **Step 3: Run Streamlit AppTest**

Open Profile, Search jobs, and Job queue; verify no exceptions and that keyword-only search setup is available without a CV.

- [ ] **Step 4: Run a local browser smoke test**

Start Streamlit, inspect desktop and narrow layouts, verify text wrapping and navigation, and confirm Apply is a real link that targets a new tab.

- [ ] **Step 5: Push the feature branch**

```bash
git push -u origin codex/streamlined-search-apply-v1-11
```

- [ ] **Step 6: Merge only after the feature branch is green**

Merge non-destructively into `main`, rerun the complete checks from `main`, and push `main` so Streamlit Cloud redeploys.
