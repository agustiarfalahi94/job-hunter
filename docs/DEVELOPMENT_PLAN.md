# Development Plan

## v0.1 - Foundation

- Create public-safe repository structure.
- Add factual candidate profile.
- Add preference template.
- Add deterministic scoring module.
- Add tests and local check script.

## v0.2 - Local Job Queue

- Added SQLite storage for jobs, scores, decisions, and application status.
- Added import from pasted job descriptions or CSV.
- Added duplicate detection.
- Added CLI commands for scoring and queue review.

## v0.3 - Draft Assistant

- Added draft generation that cites candidate-profile evidence.
- Added a guard that flags unsupported claims.
- Added local draft exports for cover letters and form answers.

## v0.4 - Browser-Assisted Applications

- Added dry-run application packets.
- Added user-confirmation defaults before submit.
- Added audit-friendly packet exports.
- Kept real browser automation, captchas, logins, and missing required-field
  handling for a later explicit integration phase.

## v1.0 - Daily Application Workflow

- Combined queue, scoring, drafts, packets, status updates, and daily progress
  into a repeatable local workflow.
- Added daily progress tracking toward the user's target.
- Kept quality controls explicit: dry-run packets and human submission remain
  the boundary until browser automation gets a separate integration design.

## v1.1 - User Criteria

- Added the user's job-title, primary-keyword, bonus-keyword, hard-skip, and
  daily target criteria.
- Added private local preference loading from `config/preferences.local.yaml`.
- Added mandatory remarks for weak matches and hard skips.

## v1.2 - Streamlit Web App

- Added a Streamlit dashboard for queue review, single-job entry, CSV import,
  draft and packet exports, status updates, and daily progress.
- Added Streamlit runtime dependency and Community Cloud entry-point docs.

## v1.3 - Guided Streamlit Workflow

- Added a Profile & CV page for local CV upload, replacement, removal, and
  status display.
- Added page descriptions, examples, and sample CSV data to reduce confusion.
- Added a Search setup page that previews the intended 50-job search flow
  without pretending job-board scraping is implemented.
- Updated duplicate handling so exact same roles across platforms are skipped.
- Clarified public deployment limits around authentication and per-user data.

## v1.4 - Public Search Automation

- Added CV PDF text extraction and private extracted-text storage.
- Added CV signal detection for primary and bonus matching keywords.
- Added public web-result search for selected platforms.
- Added real Streamlit search execution with logs, scoring, queue insertion,
  and duplicate handling.
- Added production dependency list for Streamlit Cloud.
- Added changelog and implementation-plan documentation.

## v1.5 - Word CV Uploads

- Added PDF, DOCX, and best-effort legacy DOC CV upload handling.
- Added DOCX paragraph/table text extraction with `python-docx`.
- Preserved private CV storage and expanded Word file ignore rules.

## v1.6 - API-Ready Search

- Added optional SerpAPI configuration through Streamlit secrets or environment.
- Added API search query construction and JSON result parsing.
- Kept free public search fallback when no key is configured.

## v1.7 - City Autocomplete

- Added Malaysia city lookup through the CountriesNow public API.
- Added local fallback city data and filtered city options.
- Wired location selection into the Streamlit search flow.

## v1.8 - Production Readiness

- Added Streamlit production-readiness tab.
- Added secrets example file and deployment documentation.
- Added final release documentation, versioning, review, and verification pass.

## v1.9 - Streamlit User Flow Cleanup

- Replaced the broad tab set with two sidebar workflows: Automated search and
  Manual scoring.
- Made search/scoring criteria editable in the app instead of showing read-only
  hardcoded values.
- Collapsed city autocomplete and exact location into one searchable Location
  dropdown.
- Removed user-facing production-readiness, workflow-comparison, drafts, and
  progress pages from the main app flow.
- Moved draft, packet, and status actions into the Job queue page.
- Added full descriptions and wider readable text columns to the queue table.
- Added a README tutorial for real Streamlit usage.

## v1.10 - Search Freshness and Live Progress

- Added user-controlled posting-age filters with a past-month default.
- Added search-result and trusted destination-page checks for closed jobs.
- Added real-time search progress and activity messages.
- Added one-click navigation from a completed search to Job queue.
- Clarified Strong-match goal as a planning goal and Session cap as the actual
  per-run maximum.
- Added trusted-domain validation before destination-page availability checks.

## v1.11 - Streamlined Search, Dates, and Apply Links

- Replaced the separate automated/manual Streamlit modes with one three-page
  journey: Profile & CV, Search jobs, and Job queue.
- Made CV upload explicitly optional; keyword-only search and scoring work
  without a saved CV.
- Removed manual job entry, CSV import, draft export, packet export, and
  application-status controls from the Streamlit interface.
- Replaced the misleading application status column with a real posting date
  or `Unknown`.
- Added posting-date normalization from structured job data, LinkedIn cards,
  SerpAPI metadata, and recognizable relative dates.
- Added a second freshness check so known stale results are skipped even when a
  provider returns them after a date-filtered query.
- Added additive SQLite fields for posting date and discovered Apply URL.
- Added official HTTPS Apply destination discovery with an original-posting
  fallback that opens in a new browser tab.
- Kept login, CAPTCHA, required questions, review, and final submission in the
  user's browser; prohibited LinkedIn automation remains out of scope.

## v1.11.1 - Streamlit Cloud Rebuild Hotfix

- Restored the stable-import boundary required by Streamlit hot reloads.
- Isolated application-link validation in its own module.
- Pinned the tested Streamlit version so Community Cloud performs a clean,
  reproducible dependency rebuild.

## v1.12 - Unified Search Criteria and CV Navigation

- Consolidated titles, required description keywords, bonus keywords, hard
  skips, location, platforms, freshness, goal, and maximum results into one
  Search criteria panel.
- Reused the same title and required-keyword values for query construction and
  suitability scoring.
- Added a direct Continue to Search jobs action after a CV is saved.
- Added Streamlit regression coverage for both user-flow fixes.

## v1.13 - Eligibility, Dates, and Application Status

- Added shared punctuation-tolerant matching for local-only and Malaysian-only
  restrictions in search results, detail pages, scoring, and queue visibility.
- Prevented restricted new jobs from entering the active queue while retaining
  historical data outside the active view.
- Expanded posting-date enrichment to known provider fields, page metadata,
  posting-time elements, embedded job data, and labeled visible text.
- Added relative-year parsing and activity messages for unavailable dates.
- Added additive Applied / Not applied persistence and a reversible queue
  checkbox while keeping applied jobs visible.
- Added focused regression tests, documentation, review, CI, and production
  verification for the release.

## v1.14 - Session-Safe Gemini Search

- Isolated hosted CV, queue, cache, and application data by Streamlit session.
- Added separate Criteria-based and CV-based Gemini matching modes with a
  visible deterministic fallback.
- Added title OR description discovery and validated custom career-site
  domains for SerpAPI users.
- Replaced snippets with full descriptions when available and exposed
  description and posting-date provenance.
- Added stable provider identity, alternate source preservation, and manual
  application evidence.
- Added a cancellable, bounded two-worker runner with live 0/50 progress and
  stale-run protection.
- Simplified the app to one criteria panel with a fixed 50-unique-job target and
  Actionable / All / Already applied queue views.

## v1.15.2 - Flash Latency Follow-Up

- Use officially supported minimal thinking on Gemini 3 Flash and a bounded 30-second timeout.
- Update the SDK floor, verify current model-name variants, and repeat release/production checks.

## v1.15.1 - Production Gemini Model Recovery

- Diagnose with synthetic data against the deployed provider configuration.
- Test model discovery and bounded recovery before implementation.
- Select only provider-listed text-generation Flash models and preserve the two-generation ceiling.
- Run the full release gate, feature CI, main CI, and repeat the production connection check.

## v1.15 - Search Completion And Criteria UX

- Clear the uploader widget when a session CV is removed.
- Match supported hard-skip requirements by conservative intent rather than
  requiring exact word-for-word phrases.
- Offer named company career-site presets and flexible public-domain entries in
  one searchable selector.
- Separate actual jobs checked from the 50-job ceiling in terminal progress.
- Route fragment navigation through a pending request consumed by a full app
  rerun before the page selector is rendered.
- Add focused regression, release, CI, and production verification.
- Hide Profile & CV in criteria mode while preserving saved session data.
- Sort Apply choices by numeric job ID without changing ranked queue ordering.
- Fix Gemini output allocation and add a non-sensitive Cloud connection check.

## Next

- Add authenticated durable accounts only with an explicit privacy and data
  retention design.
- Add more provider adapters where public APIs or platform terms permit them.
- Improve full-description extraction with provider-specific fixtures.
- Keep login, CAPTCHA, and final submission outside the hosted app.
