# Project Spec

## Purpose

Job Hunter turns editable search preferences into a short, explainable list of Kuala Lumpur data jobs. It should reduce repetitive research without inventing candidate experience, mislabeling job freshness, or pretending that opening a job page means an application was submitted.

## Supported Web Workflow

1. Optionally save a PDF, DOCX, or best-effort DOC CV for private profile reference.
2. Search without requiring a CV by editing title, description, location, platform, freshness, and scoring criteria.
3. Watch live provider, availability, duplicate, freshness, and scoring progress.
4. Review ranked results with a verified posting date or `Unknown`.
5. Open the safest official application destination in a new tab.
6. Complete login, CAPTCHA, required questions, final review, and submission on the destination site.

## Included

- Contact-free public candidate profile supported by the supplied CV.
- Private PDF, DOCX, and best-effort legacy DOC storage and text extraction.
- Optional CV signal display; CV upload is not required for search.
- Editable target titles, primary keywords, bonus keywords, hard skips,
  strong-match goal, and maximum jobs per session.
- One searchable Malaysia city selector backed by a public API and local fallback.
- LinkedIn, JobStreet, Indeed, Foundit, and selected company-career search targets.
- Optional SerpAPI search configured through Streamlit secrets or environment.
- Public-result fallback when no API key is configured.
- Provider posting-age filters with a past-month default.
- Posting-date extraction from structured job metadata, platform cards, and recognizable search-result dates.
- A second recency check that rejects known dates older than the user-selected limit.
- Closed-job checks on result cards and trusted destination pages.
- Deterministic explainable scoring with mandatory remarks for weak and skipped jobs.
- SQLite queue migration that preserves existing local rows.
- Exact cross-platform duplicate detection by title, company, and location.
- Official HTTPS Apply URL discovery with original-posting fallback.
- One Streamlit workflow: **Profile & CV**, **Search jobs**, and **Job queue**.
- One Search criteria panel whose titles and keywords drive both discovery and
  scoring, without duplicated controls.
- Direct navigation from a saved CV to Search jobs.
- Readable queue table with wrapping, wide text columns, and no application-status column.
- Automated tests, local check script, versioned changelog, design, and implementation plans.

## Not Included

- Bypassing login, CAPTCHA, rate limits, access controls, or anti-bot systems.
- LinkedIn form automation or any activity prohibited by a platform's terms.
- Generic remote control of a visitor's logged-in browser from Streamlit Cloud.
- Automatic submission of arbitrary third-party forms.
- Storage of platform passwords, cookies, identity documents, or private form answers.
- Public-deployment authentication or per-user private storage.
- Guaranteed extraction from every legacy binary DOC file.

## Success Criteria

- Search can run when no CV is stored.
- A saved CV offers direct navigation to Search jobs.
- Search titles and required keywords appear once and drive both discovery and scoring.
- The queue never presents application status as posting freshness.
- Every row shows an ISO posting date or `Unknown`.
- Known stale or closed jobs are skipped with an explanatory activity message.
- Apply prefers a discovered safe HTTPS destination and otherwise opens the original safe posting.
- The app never claims that an application was submitted.
- Existing SQLite rows survive migration.
- A fresh clone passes the complete test gate and starts the Streamlit app without import errors.
- No CV, contact details, secrets, or local application data enter Git.

## Reference Projects Studied

- `kopi-kompas`: concise README style, explicit API-key boundary, and AI handover notes.
- `tiny-tapsters`: clear validation gate and strong secret-handling warnings.
- `agustiar-data-pipeline`: Python layout, Streamlit conventions, config templates, tests, and CI.
- `random_recall`: starter structure and repository naming patterns.

Only relevant project patterns were adapted; unrelated code was not copied.
