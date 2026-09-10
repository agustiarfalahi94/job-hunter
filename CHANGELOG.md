# Changelog

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
