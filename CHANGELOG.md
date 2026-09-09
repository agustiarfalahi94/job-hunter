# Changelog

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
