# Changelog

## 1.18.2 - 2026-09-20

- Integrate SerpAPI `google_jobs` engine support for structured job discovery and full description extraction.
- Support parsing `jobs_results` payloads in `parse_serpapi_results()` including full descriptions, direct `apply_options`, `company_name`, and detected posted age.
- Provide automatic fallback to `organic_results` web search when `jobs_results` is empty or unavailable.
- Bypass platform anti-bot/Cloudflare challenge blocks on Indeed and LinkedIn page fetching by utilizing Google Jobs pre-crawled structured data.
- Add unit regressions for `google_jobs` parsing, candidate fallbacks, and eligibility filtering.

## 1.18.1 - 2026-09-18

- Follow provider-advertised SerpAPI result pages in hosted discovery, after initial source/signal queries, within the existing twelve-request/fifty-candidate/runtime/cancellation limits. Stop empty/repeated pages.
- Remove the unsupported assumption that `num=50` retrieves fifty Google results. Validate advancing pagination offsets and reconstruct the original authenticated query rather than following response URLs or replacement parameters.
- Fix Indeed title/city/footer parsing in API and public fallback results: retain internal title separators, put recognized trailing city evidence in Location and do not infer employers from title fragments.
- Add later-page reference-URL, source ordering, original-secret/filter preservation, invalid-link, repeated-page, caps, Stop and fallback-parser regressions. A known URL is not guaranteed to appear in real provider rankings; a queue export cannot establish whether it was discovered or skipped.
- Retain v1.18.0's optional account saving and external owner OAuth/Supabase setup requirements.

## 1.18.0 - 2026-09-18

- Add optional native Google sign-in with verified-email allowlisting and stable issuer/subject ownership. Accounts stay off by default; incomplete enabled configuration fails closed.
- Restore and automatically save encrypted CV bytes/text, all search criteria, matching mode, queue, posting corrections and manually recorded application history in a server-only Supabase database.
- Add bounded authenticated storage RPCs, atomic revision checks and deletion tombstones so stale tabs cannot overwrite newer history or recreate cleared data.
- Clear private state and cancel search work on sign-out/account change; never persist provider credentials, cookies, controllers or caches. Criteria-based matching still receives no CV text.
- Show real save status, outages and conflicts; require explicit reload/delete confirmation. Add CV/storage limits, safe secrets template, SQL migration, owner setup and recovery documentation.
- Add mocked account/UI/restart regressions and mandatory disposable-PostgreSQL migration/concurrency/grant tests in CI. Live Google sign-in and cloud save/reboot verification require owner credentials and are not claimed by mocked tests.

## 1.17.2 - 2026-09-17

- Target individual Indeed viewjob URLs instead of broad listing discovery, retaining regional-domain validation and the existing request budget.
- Add rejection-reason counts without logging returned URLs or raw provider data. A controlled production reproduction of the previous query returned twenty web results but zero accepted vacancy links, before scoring.
- Refresh the whole page once per terminal run after accepting events/results so Run search is enabled again rather than remaining disabled after fragment completion.
- Add red/green vacancy-query, rejected-listing/source and once-only terminal-refresh regressions.
- Production verification on September 18 found and queued ten Indeed vacancies, filled terminal progress, re-enabled search, opened the queue shortcut and preserved criteria on return. The separate synthetic Gemini check reported unavailable quota; the live scores were deterministic fallbacks, not verified Gemini scores.

## 1.17.1 - 2026-09-17

- Update runtime/scoring and example-secret defaults from inherited Gemini 2.5 Flash to current stable 3.8 Flash; preserve explicit model settings and observed-model reporting.
- Distinguish provider response errors from legitimate empty Google results, with sanitized authentication/allowance/error classifications and per-query web-result versus accepted-job counts.
- Show warnings for runs with no discovered/scored jobs; fail runs where every discovery request fails instead of claiming queue results exist.
- Add mocked discovery-error, empty-result, rejected-link, secret-redaction and model-default regressions. Live discovery remains dependent on indexing, provider allowance, and job-page access.

## 1.17.0 - 2026-09-17

- Replace the single Location selector with persistent OR selections for cities, countries, ASEAN, and a documented APAC country/economy preset; retain empty defaults and migrate saved single-city settings.
- Expand regional search signals within the existing twelve-request ceiling, group OR clauses so location/source constraints cannot escape keyword matching, and fairly include other platforms in broad LinkedIn fallback planning.
- Use observed ISO country/address evidence for country and region eligibility and deterministic location scoring. Keep missing geography unverified and preserve legacy CLI location input.
- Include regional JobStreet domains and Foundit Indonesia, Singapore, and India in discovery and safe result-domain handling.
- Verify and cache new company names for each distinct selected region; deduplicate resolved hosts and enforce five company/region lookup pairs before provider calls, without increasing the five-site cap.
- Document regional membership/coverage, company limits, and the fifty-candidate ceiling being a pre-scoring budget rather than the best fifty matches.
- Add multi-location navigation, regional query/parser, geographic scoring, runner filtering, company budget, migration, and cache regression coverage.
- Add Europe OR APAC and Global unrestricted geography without expanding discovery/checking budgets.
- Display configured Gemini model and actual connection-check model; document usage/error charts versus project/model/grounding limits.
- Add strict own-platform LinkedIn Easy Apply, Indeed Apply, and Foundit Quick Apply filters; bind observed apply IDs to the selected vacancy and never infer methods from descriptions.
- Extract recognized platform header locations and Indeed result-title location slots when structured addresses are missing. Hide Location only when all visible results are unverified.
- Add session-only posting-date/expiry corrections with user provenance, future-date rejection, atomic date/provenance deduplication, structured validThrough checks, and disabled Apply for marked-expired jobs.
- Remove alternate-source rows/buttons, queue storage, and duplicate-alias publication; retain primary URL/provider/fingerprint identity and application records.
- Preserve explicit country evidence over ambiguous city inference and structured address locality roles; insufficient city evidence stays unverified.
- Share the twelve-request fallback planner with the legacy public search path and document reference-job positive/negative tests plus the observed Indeed direct-fetch access limitation.
- Associate known-provider vacancy metadata by stable job ID when tracking parameters differ, without accepting unrelated job IDs or overriding explicit conflicting vacancy URLs.

## 1.16.1 - 2026-09-17

- Fix direct LinkedIn fallback discovery to use quoted OR alternatives for both title and description lists, matching SerpAPI/public web query behavior.
- Verify case-insensitive, any-value matching across all four title/keyword fields, and custom values outside the suggestion catalog surviving page navigation.
- Verify that saving a CV does not change available suggestions or select criteria. Document the static suggestion catalog's origin and each field's OR meaning in the README and scoring specification.

## 1.16.0 - 2026-09-17

- Preserve all edited search parameters, including custom hard skips, across page navigation, completed searches, and matching-mode switches using non-widget session storage.
- Start new web sessions with empty selections and no selected location; retain Past month freshness protection and leave CLI defaults/CV evidence suggestions unchanged.
- Apply the selected location to matching instead of hidden Kuala Lumpur defaults, and explicitly describe case-insensitive OR keyword semantics with optional bonus signals in Gemini prompts.
- Show career-site presets with their domains. Presets are curated convenience choices from earlier user examples, not inferred from a CV or selected automatically.
- Resolve new company names using Gemini Google Search and verify live official/regional sources, a careers link from the official company page, and readable careers content. Reject unsafe URLs, ungrounded guesses, and mismatched regions.
- Cache company lookups by name/region/model in the current session, provide retries for failed lookups, and display evidence and Google Search suggestions. Restrict automatic lookup to brand-matching corporate/company-owned careers domains; reject ambiguous shared ATS scopes, retain query-sensitive evidence comparisons, and check destination region.
- Prioritize relevant citations within the resolution budget, handle punctuated company names, and search company-owned hosts without excluding job details on sibling paths.
- Stop labelling general search results with the requested city as observed location. Extract JobPosting addresses, skip known location mismatches before scoring, and explain unverified locations in result remarks.
- Associate structured addresses with the selected vacancy rather than merging related postings. Normalize common country codes and treat country-only city evidence as unverified, not a false city mismatch.
- Give company lookup its own actionable provider/quota messages; never claim a deterministic scoring fallback verified a company site.
- Add navigation, empty-default, case/OR, grounding, regional verification, source-limit, retry, privacy, cache, and path-scoping regression coverage.

## 1.15.3 - 2026-09-16

- Correct Gemini 3 Flash thinking to `low`: current Gemini 3.7/3.8 Flash models explicitly reject `minimal`.
- Classify rejected request settings (HTTP 400) separately from generic service failures without exposing provider response text.
- Verify the thinking setting against the latest model in regression tests.

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
