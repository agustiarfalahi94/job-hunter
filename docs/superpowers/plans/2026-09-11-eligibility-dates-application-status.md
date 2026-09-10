# Eligibility, Posting Dates, and Application Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exclude local-only roles from the active queue, recover trustworthy visible posting dates, and persist whether each retained job has been applied to.

**Architecture:** Add one focused eligibility matcher shared by scoring, search ingestion, and queue visibility. Extend the existing layered HTML metadata parser without a browser dependency, then add an additive SQLite application-status field surfaced through the current queue table and selected-job controls.

**Tech Stack:** Python 3.11+, BeautifulSoup, SQLite, Streamlit 1.63.0, unittest/pytest-compatible tests

**Spec:** `docs/superpowers/specs/2026-09-11-eligibility-dates-application-status-design.md`

## Global Constraints

- Release version is `1.13.0`.
- Branch is `codex/eligibility-dates-applied-v1-13`.
- No new production dependency or headless browser is introduced.
- The actual CV, extracted text, API keys, cookies, private queue database, and application records remain outside Git.
- Restricted historical rows are hidden from the active queue but are not deleted.
- Opening an Apply link never marks an application as submitted.
- Known stale jobs are excluded; unknown dates are displayed honestly as `Unknown`.

---

### Task 1: Shared Eligibility Filtering

**Files:**
- Create: `src/job_hunter/eligibility.py`
- Modify: `src/job_hunter/scoring.py`
- Modify: `src/job_hunter/search.py`
- Modify: `src/job_hunter/app_ui.py`
- Modify: `src/app.py`
- Modify: `src/job_hunter/preferences.py`
- Modify: `config/preferences.example.yaml`
- Test: `tests/test_eligibility.py`
- Test: `tests/test_scoring.py`
- Test: `tests/test_search.py`
- Test: `tests/test_app_ui.py`

**Interfaces:**
- Produces: `hard_skip_matches(text: str, configured_keywords: object) -> tuple[str, ...]`
- Produces: `exclude_hard_skipped_jobs(jobs: Iterable[JobRecord], configured_keywords: object) -> list[JobRecord]`
- Consumes: the existing `preferences["hard_skip_keywords"]` list and combined job title, description, location, and fetched page text

- [ ] **Step 1: Write failing matcher and scoring tests**

Add tests proving that punctuation and case are normalized, that the configured legacy rule `locals/malaysian only` activates local-only aliases, and that unrelated uses of the word `local` do not match:

```python
def test_local_only_aliases_match_restricted_titles(self):
    keywords = ["locals/malaysian only"]
    assert hard_skip_matches("Senior BI Specialist (Local Applicant Only)", keywords) == (
        "locals/malaysian only",
    )
    assert hard_skip_matches("Local reporting team welcomes applicants", keywords) == ()

def test_scoring_skips_local_applicant_only_title(self):
    result = score_job(
        {"title": "BI Analyst (LOCAL APPLICANTS ONLY)", "description": "Power BI"},
        {"hard_skip_keywords": ["locals/malaysian only"]},
    )
    assert result.decision == "skip"
    assert result.score == 0
```

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `pytest tests/test_eligibility.py tests/test_scoring.py -q`

Expected: FAIL because `job_hunter.eligibility` does not exist and the current literal matcher misses the title variant.

- [ ] **Step 3: Implement the shared eligibility matcher**

Create `src/job_hunter/eligibility.py` with punctuation normalization and a local-only alias group:

```python
LOCAL_ONLY_ALIASES = (
    "local applicant only",
    "local applicants only",
    "local candidate only",
    "local candidates only",
    "locals only",
    "malaysian only",
    "malaysians only",
)

def hard_skip_matches(text: str, configured_keywords: object) -> tuple[str, ...]:
    normalized_text = _normalize(text)
    matches: list[str] = []
    for raw_keyword in configured_keywords or ():
        keyword = str(raw_keyword).strip()
        normalized_keyword = _normalize(keyword)
        direct_match = bool(normalized_keyword and normalized_keyword in normalized_text)
        local_rule = "only" in normalized_keyword and any(
            marker in normalized_keyword for marker in ("local", "malaysian")
        )
        alias_match = local_rule and any(alias in normalized_text for alias in LOCAL_ONLY_ALIASES)
        if (direct_match or alias_match) and keyword not in matches:
            matches.append(keyword)
    return tuple(matches)

def _normalize(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())
```

Keep aliases phrase-specific so ordinary wording such as `work with local teams` does not trigger exclusion.

- [ ] **Step 4: Route scoring through the shared matcher**

Replace the hard-skip `_all_contains` call in `score_job()` with `hard_skip_matches(text, preferences.get("hard_skip_keywords", ()))`. Keep the existing zero score, `skip` decision, reasons, and remarks contract.

- [ ] **Step 5: Write failing search-ingestion tests**

Add one test where the search-card title contains `(Local Applicant Only)` and another where the restriction appears only in the fetched job page. Assert `summary.skipped == 1`, `summary.added == 0`, an explanatory log is present, and `queue.list_jobs() == []`.

- [ ] **Step 6: Run the search tests and confirm failure**

Run: `pytest tests/test_search.py -k "local_only" -q`

Expected: FAIL because restricted results are currently passed to `queue.add_job()`.

- [ ] **Step 7: Exclude restricted candidates before insertion**

In `run_public_search()`, check the candidate title, snippet, and location before fetching the detail page. After a readable detail fetch, check the same fields plus `job_page_text`. On a match, increment `skipped`, emit a `skipped` progress event naming the configured rule, and continue without calling `queue.add_job()`.

Use a private helper returning a message such as:

```python
def _eligibility_skip_reason(candidate: SearchCandidate, keywords: object, page_text: str = "") -> str:
    text = " ".join((candidate.title, candidate.description, candidate.location, page_text))
    matches = hard_skip_matches(text, keywords)
    return f"Hard skip keyword found: {', '.join(matches)}" if matches else ""
```

- [ ] **Step 8: Write and implement historical-row visibility tests**

Add `exclude_hard_skipped_jobs()` in `app_ui.py`. It combines each record's title, description, and location and keeps only records with no match. Test that a historical local-only record is removed while an applied or ordinary record remains.

In `src/app.py`, pass preferences into `_render_queue(queue, preferences)` and obtain the active hard-skip list from `_active_preferences(preferences)`. Apply the same helper in `_render_sidebar()` before calculating the queue metric, and in `_render_queue()` before decision filters, the table, and the Apply selector are built. Do not delete the SQLite row.

- [ ] **Step 9: Seed explicit public configuration examples**

Add `local applicant only` to the default and example hard-skip lists while retaining `locals/malaysian only` for compatibility. Confirm the UI remains editable.

- [ ] **Step 10: Run focused eligibility tests**

Run: `pytest tests/test_eligibility.py tests/test_scoring.py tests/test_search.py tests/test_app_ui.py -q`

Expected: PASS.

- [ ] **Step 11: Commit eligibility filtering**

```bash
git add src/job_hunter/eligibility.py src/job_hunter/scoring.py src/job_hunter/search.py src/job_hunter/app_ui.py src/app.py src/job_hunter/preferences.py config/preferences.example.yaml tests/test_eligibility.py tests/test_scoring.py tests/test_search.py tests/test_app_ui.py
git commit -m "Exclude restricted local-only jobs"
```

---

### Task 2: Layered Posting-Date Enrichment

**Files:**
- Modify: `src/job_hunter/search.py`
- Test: `tests/test_search.py`

**Interfaces:**
- Extends: `normalize_posted_date(value: str, today: date | None = None) -> str`
- Extends: `extract_job_metadata(html: str, source_url: str, today: date | None = None) -> JobPageMetadata`
- Produces: private provider, metadata, embedded-data, and labeled-text extraction helpers returning raw strings or normalized ISO dates

- [ ] **Step 1: Write failing relative-date tests**

Extend the normalization test with deterministic month and year expectations:

```python
assert normalize_posted_date("2 months ago", today=date(2026, 9, 10)) == "2026-07-12"
assert normalize_posted_date("1 year ago", today=date(2026, 9, 10)) == "2025-09-10"
```

- [ ] **Step 2: Run the normalization test and confirm failure**

Run: `pytest tests/test_search.py::SearchTest::test_normalize_posted_date_accepts_iso_and_relative_values -q`

Expected: FAIL for the year value.

- [ ] **Step 3: Add year support**

Extend both relative-date regular expressions to include `year`, and map it to `amount * 365` days. Keep hour/day/week/month behavior unchanged.

- [ ] **Step 4: Write failing provider-date tests**

Add SerpAPI fixtures for direct `date`, nested `rich_snippet.top.detected_extensions.posted_at`, and relative `1 year ago` values. Assert that the parser preserves the normalized date on each `SearchCandidate`.

- [ ] **Step 5: Implement known provider-field extraction**

Add a helper that checks only recognized date keys (`date`, `datePosted`, `date_posted`, `posted_at`) and recognized nested containers. Do not recursively accept arbitrary date-looking values. Pass the selected raw value through `normalize_posted_date()`.

- [ ] **Step 6: Write failing page-metadata tests**

Cover all fallback layers with isolated HTML fixtures:

```html
<meta itemprop="datePosted" content="2026-09-08">
<div class="posted-time-ago__text">2 months ago</div>
<main>Date posted: 1 year ago</main>
<script>window.__JOB__ = {"postedAt":"2026-09-07"};</script>
```

Call `extract_job_metadata(..., today=date(2026, 9, 10))` for relative fixtures. Add a negative fixture containing unrelated text such as `Our company was founded 1 year ago` and assert the date stays empty.

- [ ] **Step 7: Run page-metadata tests and confirm failure**

Run: `pytest tests/test_search.py -k "metadata and (meta or visible or embedded or unrelated)" -q`

Expected: FAIL because only JSON-LD and generic `<time>` are currently inspected.

- [ ] **Step 8: Implement ordered page-date extraction**

Keep JSON-LD first, then inspect:

1. metadata with `itemprop`, `property`, or `name` values tied to `datePosted`, `datePublished`, or published-time fields;
2. job-date selectors including `<time>`, classes containing `posted`, and data-test attributes containing `posted`;
3. known embedded keys such as `datePosted`, `date_posted`, and `postedAt`;
4. visible phrases preceded by `date posted`, `posted`, `listed`, or `published`.

Normalize each candidate with the optional `today` argument and stop at the first valid value. Keep Apply-link discovery unchanged.

- [ ] **Step 9: Add date-source activity logging**

When a readable detail page still yields no posting date and the provider candidate also has none, emit a `date_unknown` progress event explaining that the source exposed no readable posting date. Do not increment `skipped`. Existing blocked-page handling stays `availability_unknown`.

- [ ] **Step 10: Verify stale enriched dates are excluded**

Add a search test where the search card has no date but the detail page says `Date posted: 1 year ago`; assert the result is skipped after enrichment and never enters the queue.

- [ ] **Step 11: Run focused search tests**

Run: `pytest tests/test_search.py -q`

Expected: PASS.

- [ ] **Step 12: Commit posting-date enrichment**

```bash
git add src/job_hunter/search.py tests/test_search.py
git commit -m "Improve job posting date detection"
```

---

### Task 3: Persisted Application Status

**Files:**
- Modify: `src/job_hunter/queue.py`
- Modify: `src/job_hunter/app_ui.py`
- Modify: `src/app.py`
- Test: `tests/test_queue.py`
- Test: `tests/test_app_ui.py`
- Test: `tests/test_app_navigation.py`

**Interfaces:**
- Produces: `JobRecord.application_status: str = "not_applied"`
- Produces: `JobQueue.update_application_status(job_id: int, application_status: str) -> None`
- Consumes: only `not_applied` and `applied` storage values
- Displays: `Not applied` and `Applied` labels

- [ ] **Step 1: Write failing storage and migration tests**

Extend the old-database migration test to assert the `application_status` column is added and its existing row reads `not_applied`. Add a fresh-record test and an update test:

```python
queue.update_application_status(job.id, "applied")
assert queue.list_jobs()[0].application_status == "applied"

with self.assertRaises(ValueError):
    queue.update_application_status(job.id, "submitted")
```

Also assert a missing job ID raises `ValueError`.

- [ ] **Step 2: Run storage tests and confirm failure**

Run: `pytest tests/test_queue.py -k "application_status or existing_database" -q`

Expected: FAIL because the field, column, and update method do not exist.

- [ ] **Step 3: Implement additive storage support**

Add the field to `JobRecord`, include it in every job `SELECT`, and map it in `_record_from_row()`. In `_init_db()` add:

```python
_ensure_column(
    conn,
    "jobs",
    "application_status",
    "TEXT NOT NULL DEFAULT 'not_applied'",
)
```

Implement `update_application_status()` with `{"not_applied", "applied"}` validation and the same missing-row behavior as the legacy updater. Do not repurpose or delete the legacy `status` field.

- [ ] **Step 4: Run storage tests**

Run: `pytest tests/test_queue.py -q`

Expected: PASS.

- [ ] **Step 5: Write failing queue-interface tests**

Update row-output expectations so `jobs_to_rows()` emits `Application status: Applied` or `Not applied`. Add `Application status` to width expectations. Extend the Streamlit source/AppTest checks to require an `I have applied to this job` checkbox and continue to reject the old generic `Set status` interface.

- [ ] **Step 6: Run UI tests and confirm failure**

Run: `pytest tests/test_app_ui.py tests/test_app_navigation.py -q`

Expected: FAIL because the column and checkbox are absent.

- [ ] **Step 7: Implement the queue column and checkbox**

Add the application-status label to `jobs_to_rows()`. Add a medium-width column configuration. Change `_render_queue_actions(jobs)` to `_render_queue_actions(queue, jobs)`, then render:

```python
applied = st.checkbox(
    "I have applied to this job",
    value=job.application_status == "applied",
    key=f"application_status_{job.id}",
)
desired_status = "applied" if applied else "not_applied"
if desired_status != job.application_status:
    queue.update_application_status(job.id, desired_status)
    st.toast("Application status updated.")
    st.rerun()
```

Place the checkbox beside the selected-job controls, not in the search form. Do not update status from the Apply link.

- [ ] **Step 8: Run application-status tests**

Run: `pytest tests/test_queue.py tests/test_app_ui.py tests/test_app_navigation.py -q`

Expected: PASS.

- [ ] **Step 9: Commit application tracking**

```bash
git add src/job_hunter/queue.py src/job_hunter/app_ui.py src/app.py tests/test_queue.py tests/test_app_ui.py tests/test_app_navigation.py
git commit -m "Track applied jobs in the queue"
```

---

### Task 4: Release Documentation And Verification

**Files:**
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/JOB_SCORING.md`
- Modify: `docs/APPLICATION_PIPELINE.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/PROJECT_SPEC.md`
- Modify: `docs/DEVELOPMENT_PLAN.md`
- Modify: `docs/superpowers/plans/2026-09-11-eligibility-dates-application-status.md`

**Interfaces:**
- Produces: package version `1.13.0`
- Documents: local-only exclusion, layered date limits, manual applied-state semantics, migration, and production test steps

- [ ] **Step 1: Update release metadata and user documentation**

Set `pyproject.toml` to `1.13.0`, correct the README's displayed version to `v1.13.0`, and add the `1.13.0` changelog entry dated `2026-09-11`. Update each listed document so it matches the implemented behavior and does not promise automatic application-history detection.

- [ ] **Step 2: Run the complete automated gate**

Run: `./tool/check.sh`

Expected: all tests pass, compilation succeeds, and dependency checks report no broken requirements.

- [ ] **Step 3: Review the complete branch diff**

Run: `git diff --check main...HEAD`

Run: `git diff --stat main...HEAD`

Run: `git diff main...HEAD -- src tests config pyproject.toml README.md CHANGELOG.md docs`

Review for accidental private data, secrets, incorrect migration ordering, overly broad date extraction, hidden applied jobs, and any path that inserts a restricted candidate.

- [ ] **Step 4: Perform local Streamlit smoke tests**

Start the app on an available local port and verify desktop and mobile layouts. Confirm:

1. Search jobs still has one criteria panel and visible progress.
2. A restricted historical row does not appear in the active queue.
3. Posting date and Application status columns are readable.
4. Selecting a job shows the correct Apply destination and applied checkbox.
5. Marking and unmarking applied persists across reruns.
6. Applied jobs remain visible.

- [ ] **Step 5: Mark the plan complete and commit release files**

Change each completed checkbox in this file to `[x]`, then commit:

```bash
git add pyproject.toml README.md CHANGELOG.md docs
git commit -m "Release Job Hunter 1.13.0"
```

- [ ] **Step 6: Push the feature branch and verify CI**

Run: `git push -u origin codex/eligibility-dates-applied-v1-13`

Wait for the GitHub Actions run for the feature branch and require a successful conclusion before merging.

- [ ] **Step 7: Merge to main and push**

Switch to `main`, merge the feature branch with a merge commit named `Release Job Hunter 1.13.0`, and push `main`. Do not rewrite history.

- [ ] **Step 8: Verify main CI and production**

Wait for the `main` GitHub Actions run to pass. Open `https://jobs-hunter.streamlit.app/` and verify version-relevant behavior without exposing the saved CV or secret configuration. Report the local path, GitHub URL, feature commits, merge commit, branch status, test count, CI status, production result, and any source pages that still expose no server-readable date.
