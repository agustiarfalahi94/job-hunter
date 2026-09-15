# Job Hunter Session-Safe Gemini Search Design

**Date:** 2026-09-15  
**Target release:** v1.14.0  
**Branch:** `codex/session-gemini-pipeline-v1-14`

## Purpose

Upgrade the existing Streamlit app without rebuilding unrelated features. The
release must provide public-safe session storage, CV-based and criteria-based
Gemini matching, broader job discovery, full-description enrichment where
available, stronger deduplication, manual application tracking, responsive
cancellation, and honest metadata labels.

Final application review and submission remain manual. The app will not log in
to job platforms, bypass CAPTCHA, or submit applications.

## Reconciled Starting Point

- GitHub `main` and the live Streamlit app run v1.12.0.
- The local v1.13.0 feature work is complete and committed but not pushed. It
  adds stronger local-only exclusions, better date extraction, safe redirects,
  and a manual application-status field.
- Search uses SerpAPI Google organic results when configured and public HTML
  fallbacks otherwise.
- Scoring is deterministic keyword scoring. No Gemini SDK, key loading,
  prompting, or model cache exists.
- Job pages are fetched for availability, posting date, and Apply links, but
  their description does not replace the search-result snippet before scoring.
- Search queries combine title and description groups, effectively requiring
  both groups instead of discovering by title OR description.
- SQLite and CV files use one server path. The public app has no authentication
  or per-user namespace, so those files cannot safely back public CV or
  application workflows.
- Search runs inside one Streamlit script execution. A second widget event
  cannot cancel that synchronous call.

## Storage And Privacy Boundary

The hosted Streamlit UI will use one `SessionWorkspace` stored in
`st.session_state`. It owns:

- uploaded CV bytes, filename, and extracted text;
- queue records and alternate source links;
- manual application records;
- Gemini score-cache entries;
- the active search-run controller and completed run summaries.

The hosted UI will not construct `CVStore` or `JobQueue` with shared disk paths.
It will not read legacy server CV or SQLite files. Existing local-only storage
classes remain available to CLI and tests but are outside the hosted app path.

Session storage is private to the active Streamlit session, not permanent user
storage. The UI will say that data can disappear after browser-session or app
restart and that users should not rely on it as an account. It will show
`CV Saved` only when readable extracted text exists and will provide Replace and
Remove actions. Removing or replacing a CV also invalidates CV-mode score cache
entries in that session.

No CV content, personal application data, secrets, cache payloads, or generated
private artifacts may enter Git, logs, progress messages, or exception text.

## Search Modes

The Search page will expose a sidebar mode selector with two choices.

### CV-Based Search

This mode requires readable CV text in the current session. If it is missing,
the Run button is disabled and the UI explains the requirement with a button
to open Profile & CV.

Gemini receives:

- the extracted CV text;
- editable target titles, description keywords, bonus keywords, hard skips,
  location, and posting-age criteria;
- the job title, company, location, and best available description.

The UI will state these inputs without displaying or logging the CV text.

### Criteria-Based Search

This mode neither loads nor passes saved CV text. Gemini receives only the
editable criteria and job data. A regression test will use a CV store/workspace
that raises on access to prove this boundary.

Both modes use the same discovery, enrichment, exclusion, deduplication,
scoring, progress, cancellation, and queue code.

## Search Controls

The following remain editable:

- target titles;
- description keywords;
- bonus keywords;
- hard-skip keywords;
- location;
- posting-age filter;
- predefined platforms and additional supported domains.

The location control accepts a typed value and displays Malaysia city
suggestions when available. Failure of the city service does not block typed
locations.

Additional sources accept HTTPS URLs or domain names. Inputs are normalized to
hostnames, deduplicated, limited to five per run, and rejected when malformed,
local/private-network, credential-bearing, or unsupported by the active search
provider. Custom domains work through SerpAPI site queries. The public fallback
will explain that custom domains require SerpAPI rather than implying a native
integration.

Strong-match goal and the user-facing maximum-jobs control are removed. Every
run has a hard ceiling of 50 unique candidates. It may return fewer when search
results end, pages fail, or filters exclude jobs. A run also has at most 12
search-result requests, 50 job-page fetches, 50 Gemini attempts, two concurrent
job tasks, and a five-minute scheduling deadline. Individual network and model
calls have bounded timeouts.

## Discovery

Each supported source can produce separate title-driven and
description-driven queries. Location and provider posting-age parameters apply
to both. Results from both paths enter one candidate stream and are deduplicated
before page enrichment whenever their available identity is sufficient.

A title hit is a discovery signal only. It does not guarantee a high score.
Description-only discoveries are allowed even when the title is not in the
configured target list.

SerpAPI remains the preferred discovery provider. The direct public fallback
remains best effort and is labelled as limited. Provider challenge pages,
blocked pages, malformed results, quota errors, and request failures produce
concise progress events without exposing request credentials.

## Description Enrichment

`JobDescription` will carry text, kind, source, and limitation reason. Kind is
one of:

- `full`: a description extracted from structured `JobPosting.description` or
  a recognized job-description container;
- `snippet`: provider search-result text used because full text was unavailable;
- `unavailable`: neither a usable full description nor snippet exists.

Structured `JobPosting` content is preferred. Recognized job-specific HTML
containers are next. Generic page text may support eligibility and closed-job
checks but will not be labelled a full description unless it passes job-content
quality checks. Scripts, styles, navigation, footers, cookie text, and repeated
boilerplate are excluded.

The full description replaces the snippet for Gemini and fallback scoring.
Snippet and unavailable scores are visibly marked limited; they are not
presented as full-description confidence. Blocked or prohibited pages are not
circumvented.

## Exclusions And Gemini Scoring

Deterministic hard skips and closed/stale checks run before Gemini. They remain
authoritative for obvious exclusions such as local-only or mandatory-Mandarin
wording. Verified dates older than the selected age are excluded. Unknown dates
remain reviewable with a warning.

The scoring interface accepts a mode-specific `MatchContext` and returns:

- integer score from 0 to 100;
- decision;
- concise evidence-based reasons;
- mandatory remarks for weak or rejected jobs;
- scoring engine and model label;
- description kind and limitations;
- cache status.

The Gemini implementation uses the official `google-genai` SDK and structured
JSON output. The prompt forbids invented candidate experience, requires quoted
or tightly paraphrased evidence from supplied inputs, and treats missing job or
candidate evidence as unknown. Model name is configurable, with
`gemini-2.5-flash` as the initial default. Temperature is low and output tokens
are bounded.

Gemini calls use a short timeout and at most two total attempts for retryable
rate-limit or server errors. Authentication, quota exhaustion, invalid output,
and repeated timeout errors are surfaced once per run. The job is then scored
by the deterministic fallback and labelled `Deterministic fallback`; it is not
silently presented as Gemini output. A missing Gemini key uses the same clearly
labelled fallback and does not block searching.

Session score-cache keys hash the normalized job content, description kind,
mode, selected CV or criteria input, model, and scoring-prompt version. Raw CV
or description text is not used as a visible key or logged. Cache entries are
session-only.

## Job Identity And Deduplication

The job model preserves these values separately:

- original source URL and platform;
- canonical source URL;
- stable platform job ID when available;
- discovered application URL;
- alternate source links.

Canonical URLs remove fragments and known tracking parameters without changing
the underlying posting path or provider job ID. Identity resolution proceeds in
this order:

1. matching provider plus stable job ID;
2. matching canonical source URL;
3. conservative normalized title, employer, and location fingerprint when all
   three are sufficiently specific.

A generic ATS or application URL is never sufficient identity. A Foundit result
whose Apply link points to LinkedIn therefore remains a Foundit source unless
stable source identity or the conservative vacancy fingerprint confirms the
same vacancy. Confident duplicates consolidate their source links into one queue
record. Different vacancies sharing an employer or ATS URL remain separate.

Application status belongs to resolved vacancy identity. When a new source is
consolidated into an already-applied vacancy, it inherits the manual application
record.

## Application Status And Queue

Opening Apply never changes application status. After the user submits on the
external platform, the queue offers a manual `Mark as applied` control.

An applied record stores status, recorded time, and evidence
`Marked manually by the user; not verified with the job platform`. Its displayed
decision becomes `Already applied`, and the remarks include that evidence.
Applied jobs remain stored and available through an `Already applied` filter,
but the default `Actionable` queue excludes them. No copy claims to inspect the
user's LinkedIn or other platform account.

## Posting Dates

Date extraction records normalized date, verification state, source, and reason.
The order is:

1. `JobPosting.datePosted` structured data;
2. provider fields explicitly documented as posting dates;
3. job-specific time elements and labelled visible posting text.

Supported values include ISO dates, common English absolute dates, today,
yesterday, and relative hours/days/weeks/months/years. Generic crawl dates,
page-update metadata, application timestamps, and unlabeled dates are ignored.

Age filtering applies only to verified posting dates. Unknown, blocked, or
ambiguous dates remain visible as `Unknown` with a concise reason such as
`Job page blocked` or `No job-specific posting date found`.

## Responsive Run Controller

A `SearchRunController` owns a unique run ID, cancellation event, bounded worker
pool, event queue, counters, completed results, and terminal state. Background
workers never call Streamlit APIs or mutate `st.session_state`.

The Search page uses an automatically rerunning Streamlit fragment to drain
events and completed results. It renders progress, recent activity, and a Stop
button that is disabled while idle and enabled while running. The Stop action
sets the cancellation event and prevents further searches, page fetches,
retries, and Gemini calls from being scheduled.

In-flight network calls are allowed to finish within their timeout. Before each
stage and before publishing a result, workers check cancellation and run ID. The
main thread accepts a result only when its run ID matches the active controller.
This prevents cancelled workers from writing late data or overwriting a newer
run. Completed results already accepted into the session queue are preserved.
The final state is `Completed`, `Cancelled`, or `Failed`.

## Error Handling

- Validation errors stay next to the relevant control and disable Run.
- Provider and page failures are per-source or per-job events and do not abort
  unrelated work.
- Gemini quota and authentication failures stop additional Gemini scheduling
  for that run and switch remaining jobs to the labelled fallback.
- Unexpected worker failures are captured as sanitized run events.
- Secrets, full CV text, and credential-bearing URLs are never shown in errors.
- A fatal controller error preserves accepted results and sets state `Failed`.

## Acceptance Tests

### Storage And Modes

- Hosted app construction performs no CV or SQLite disk access.
- One simulated session cannot read another session's CV, queue, cache, or
  application status.
- CV mode is disabled without readable text and enabled after PDF or Word text
  extraction.
- Criteria mode completes while any CV access raises an exception.
- Replace and Remove update `CV Saved` status and invalidate CV cache entries.

### Search And Scoring

- Title-only and description-only fixtures are both discovered.
- Full structured and recognized-container descriptions replace snippets.
- Blocked, snippet-only, and unavailable descriptions retain accurate labels.
- Gemini receives CV text only in CV mode and criteria only in criteria mode.
- Structured Gemini responses map to queue scores and evidence.
- Missing key, quota, timeout, invalid JSON, and retry exhaustion use a visibly
  labelled deterministic fallback.
- Cache hits require identical job content, mode inputs, model, and prompt
  version; changing any input causes a miss.
- Request, result, concurrency, retry, and runtime ceilings are enforced.

### Deduplication And Applications

- Tracking variations of one source URL consolidate.
- Stable IDs consolidate the same vacancy across alternate source URLs.
- A matching Foundit/LinkedIn vacancy consolidates and keeps both source links.
- A Foundit Apply redirect to LinkedIn alone does not prove duplication.
- Different vacancies sharing one generic ATS URL remain separate.
- Applied status follows a confidently consolidated vacancy.
- Apply click does not mark applied; the manual control does.
- Default Actionable hides applied jobs; Already applied reveals them with
  evidence and displayed decision `Already applied`.

### Dates And Cancellation

- Structured `datePosted` wins over crawl/update/application timestamps.
- Relative year/month/week/day/hour and supported absolute formats normalize.
- Ambiguous fixtures remain Unknown with a reason and are not age-filtered.
- Slow mocked search, page, and Gemini calls can be cancelled.
- Stop prevents new scheduling, preserves completed results, and rejects late or
  stale-run writes.
- Streamlit interaction tests verify idle/running Stop states, navigation,
  mode requirements, progress updates, and queue filters.

## Delivery Sequence

1. Retain and reconcile v1.13 fixes as the baseline.
2. Introduce the session workspace and protect the hosted data boundary.
3. Add mode-specific contexts, description enrichment, Gemini scoring, cache,
   and deterministic fallback.
4. Split discovery into title OR description queries and add source validation.
5. Add stable identity, canonical URLs, alternate sources, and application
   records.
6. Introduce the background run controller and fragment polling.
7. Finish posting-date provenance and UI copy/control cleanup.
8. Update README, architecture, scoring, pipeline, development history,
   changelog, examples, and version metadata.
9. Run focused tests throughout, then `./tool/check.sh`, package/import checks,
   Streamlit AppTest coverage, and local browser smoke tests.
10. Review the complete diff for correctness, privacy, and deployment risk.
11. Push the feature branch, confirm GitHub CI, merge to `main`, confirm main CI,
    and smoke-test production separately.

## Deployment Inputs And Limitations

`SERPAPI_API_KEY` remains optional but is required for dependable custom-domain
queries. `GEMINI_API_KEY` is optional; without it the app remains usable with the
labelled deterministic fallback. Real keys belong only in Streamlit secrets or
environment variables.

Public job pages can block or omit descriptions, dates, and Apply links. The app
will report those limitations and will not bypass access controls. Session-only
storage protects visitors from shared records but intentionally does not provide
account persistence across session or app restarts.
