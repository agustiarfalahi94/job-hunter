# Changelog

## 1.15.2 - 2026-09-16

- Set minimal thinking for Gemini 3 Flash scoring and allow 30-second provider requests to reduce hosted latency failures.
- Require Google SDK 1.75 or newer for current thinking-level support.
- Accept provider-listed major-only Flash names such as Gemini 3 Flash alongside decimal versions.
- Add regression coverage for current-model settings and model-name recovery.

## 1.15.1 - 2026-09-16

- Recover from an unavailable Gemini model using Google's model listing, with a single alternate scoring attempt and stable text-generation Flash preference.
- Report the actual scoring model; retain sanitized authentication/quota failures without switching models.
- Add regression coverage for recovery, unsupported models, failed alternates, and authentication/quota boundaries.
- Follow up on the production synthetic connection check, which confirmed model availability was blocking scoring after v1.15.0.

## 1.15.0 - 2026-09-16

- Cleared the Streamlit file-uploader selection when a saved session CV is
  removed, preventing a stale filename from appearing as if the CV remained.
- Expanded hard-skip evaluation from literal phrases to normalized terms and
  conservative semantic variants for local/Malaysian-only and mandatory
  Mandarin requirements, while excluding optional language wording.
- Replaced the free-form career-domain text area with a searchable company-site
  selector containing named presets and support for friendly name variations or
  public career domains.
- Made terminally completed searches fill the progress bar while reporting the
  actual checked count and the fixed 50-job maximum separately.
- Fixed Review Job queue navigation from the polling fragment by handing the
  page request to a full app rerun before the page control is instantiated.
- Added regression coverage for CV removal, semantic exclusions, company-source
  resolution, terminal progress, and fragment navigation.
- Sorted the selected-job Apply dropdown by numeric job ID.
- Hid Profile & CV in Criteria-based mode without removing its implementation
  or clearing a saved session CV when matching mode changes.
- Reserved sufficient Gemini JSON output capacity and disabled thinking for
  supported Gemini 2.5 Flash models to prevent the former 700-token cutoff.
- Added a synthetic-data Gemini connection check and explicit sanitized error
  classification for invalid JSON, invalid keys, unavailable models, and quota.

## 1.14.0 - 2026-09-15

- Moved hosted CVs, queue records, application evidence, and score caches into
  isolated Streamlit session storage; local SQLite remains CLI-only.
- Added Criteria-based and CV-based Gemini matching with structured output,
  content-addressed session cache, bounded retry, sanitized failures, and a
  visible deterministic fallback.
- Split discovery into title OR description query families and added validated
  custom career-site domains when SerpAPI is configured.
- Added full/snippet/unavailable description provenance and stricter
  job-specific posting-date provenance.
- Added conservative provider IDs, URL cleanup, cross-source fingerprints, and
  alternate source links without treating generic Apply redirects as identity.
- Added a cancellable two-worker search controller with immutable progress
  events, stale-run rejection, a fixed 50-unique-job target, and bounded network
  and model work.
- Added Actionable, All, and Already applied queue views with explicit manual
  application time/evidence.
- Removed obsolete search-goal and adjustable result-cap controls, expanded the
  tutorial and deployment documentation, and added regression coverage.

## 1.13.0 - 2026-09-11

- Added punctuation-tolerant local-only eligibility matching, including `Local
  Applicant Only`, local-candidate variants, and Malaysian-only variants.
- Excluded restricted new results before queue insertion and hid matching
  historical rows without deleting stored data.
- Expanded posting-date discovery across known SerpAPI fields, page metadata,
  posting-time elements, embedded job data, and labeled visible text.
- Followed bounded HTTPS redirects on trusted job and applicant-tracking
  domains while rejecting untrusted redirect destinations.
- Added deterministic support for relative years and explicit activity messages
  when a posting date remains unavailable.
- Added an additive `application_status` SQLite migration and an Applied / Not
  applied queue column.
- Added a reversible selected-job checkbox while keeping applied jobs visible
  and never treating an opened Apply link as a completed submission.
- Added eligibility, date-enrichment, migration, and Streamlit regression tests.

## 1.12.0 - 2026-09-11

- Replaced the two overlapping Search jobs forms with one unified Search
  criteria panel.
- Made target titles and required description keywords the single source for
  both public queries and suitability scoring.
- Consolidated Session cap and Maximum jobs into one Maximum jobs per session
  control.
- Added a Continue to Search jobs button whenever a saved CV is available.
- Added Streamlit regression tests for the unified criteria and CV navigation
  flows.

## 1.11.1 - 2026-09-10

- Fixed a Streamlit Community Cloud hot-reload failure caused by importing new
  helper names from an already-cached module.
- Moved application-link validation behind a cache-safe module boundary and
  tightened the entrypoint import regression test.
- Pinned Streamlit 1.63.0 so dependency resolution is reproducible and this
  deployment receives a clean environment rebuild.

## 1.11.0 - 2026-09-10

- Unified the Streamlit app into Profile & CV, Search jobs, and Job queue.
- Made CV upload optional so users can search and score with editable criteria
  alone.
- Removed manual job entry, CSV import, draft/packet export, and application
  status controls from the web interface.
- Replaced the misleading `Status = new` queue column with an actual posting
  date or `Unknown`.
- Added date extraction from structured job metadata, LinkedIn cards, SerpAPI
  metadata, and recognizable relative dates.
- Added a second freshness check that skips known stale results beyond the
  selected posting-age limit.
- Added an additive SQLite migration for `posted_date` and `apply_url`.
- Backfills missing date and Apply metadata when an older queue row is found
  again as a duplicate.
- Added official HTTPS Apply destination discovery with a safe original-posting
  fallback.
- Restricted discovered Apply links to same-site or recognized ATS hosts and
  displayed the selected destination hostname before navigation.
- Enabled a real Apply link that opens in a new browser tab while leaving login,
  CAPTCHA, required questions, review, and submission in the user's browser.
- Added queue, search, URL-safety, migration, and Streamlit regression tests.

## 1.10.0 - 2026-09-09

- Added user-controlled posting-age filters for the past 24 hours, past week,
  past month, or any time; the past month is the default.
- Added search-card and destination-page checks that skip jobs marked as no
  longer accepting applications, closed, filled, unavailable, or expired.
- Added live search progress with provider, availability-check, scoring,
  duplicate, skip, and completion messages.
- Replaced the post-search instruction with a button that opens Job queue.
- Renamed Strong target to Strong-match goal and documented that it is a goal,
  while Session cap is the actual per-run maximum.
- Restricted destination-page checks to the selected platform's trusted job
  domains.

## 1.9.1 - 2026-09-09

- Fixed Streamlit Cloud import-time compatibility after the v1.9.0 UI cleanup.
- Added a regression test so the Streamlit entrypoint does not directly import
  newly added app UI helper names that can be stale during Cloud hot reloads.

## 1.9.0 - 2026-09-09

- Simplified the Streamlit app into two clear workflows: Automated search and
  Manual scoring.
- Made target titles, primary strengths/description keywords, bonus keywords,
  hard-skip keywords, strong target, and session cap editable in Search setup.
- Replaced separate city-autocomplete and exact-location controls with one
  searchable Location dropdown.
- Removed user-facing production-readiness, workflow-comparison, drafts, and
  progress pages from the main app flow.
- Folded draft, packet, and status actions into the Job queue page.
- Added full job descriptions to the queue table and widened/wrapped readable
  text columns.
- Updated the README with a step-by-step web-app tutorial.

## 1.8.0 - 2026-09-09

- Added Streamlit production-readiness guidance inside the app.
- Added `.streamlit/secrets.example.toml` for optional API search configuration.
- Added deployment, privacy, and automation-boundary documentation.
- Added final release verification and code-review workflow notes.

## 1.7.0 - 2026-09-09

- Added Malaysia city autocomplete backed by the CountriesNow public API.
- Added local city fallback data so the app still works when the API is down.
- Wired location selection into Search setup and Add job.

## 1.6.0 - 2026-09-09

- Added optional SerpAPI-backed search configuration through Streamlit secrets
  or environment variables.
- Kept free public LinkedIn search and public-result fallback when no API key is
  configured.
- Added provider status labels and blocked-provider logging.

## 1.5.0 - 2026-09-09

- Added CV upload support for PDF, DOCX, and best-effort legacy DOC files.
- Added DOCX text extraction from paragraphs and tables.
- Added private CV storage with the original supported extension.
- Expanded private file ignore rules for Word documents.

## 1.4.0 - 2026-09-09

- Added local CV text extraction from uploaded PDF files.
- Added CV signal detection for primary and bonus job-match keywords.
- Added public LinkedIn job-card search and public web-result search through a modular search provider.
- Added real Streamlit search run button that scores discovered jobs into the queue.
- Added search progress logs, run summary rows, and query preview.
- Added production dependencies for Streamlit Cloud deployment.
- Added v1.4 implementation plan documentation.
- Kept login, CAPTCHA, and final job application submission outside automation scope.

## 1.3.0 - 2026-09-08

- Added guided Streamlit workflow pages.
- Added local CV upload, replace, remove, and status display.
- Added page descriptions, sample CSV data, and clearer current/future workflow labels.
- Added cross-platform exact duplicate handling by title, company, and location.

## 1.2.0 - 2026-09-08

- Added first Streamlit web dashboard for local/manual testing.
- Added queue review, single job entry, CSV import, draft exports, packet exports,
  status updates, and progress display.

## 1.1.0 - 2026-09-08

- Added the user's target job titles, primary keywords, bonus keywords, hard skips,
  Kuala Lumpur location target, and daily target criteria.

## 1.0.0 - 2026-09-08

- Completed the first local daily application workflow.

## 0.1.0 - 2026-09-08

- Created the public-safe project foundation, candidate profile, scoring rules,
  documentation, tests, and GitHub repository.
