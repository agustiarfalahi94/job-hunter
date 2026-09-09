# Project Spec

## Purpose

Job Hunter helps the candidate process many job openings without losing the
human judgment needed for truthful applications. It should turn a CV-supported
profile and local preferences into a shortlisting decision, application queue,
and later, tailored drafts.

## Current Scope

Included:

- Public documentation for the project.
- CV-supported candidate profile without contact details.
- Job preference template.
- Deterministic scoring engine.
- SQLite-backed local job queue.
- CSV import for job rows.
- Duplicate detection by URL or title/company/location.
- Cross-platform duplicate detection by exact title/company/location.
- CLI commands for adding, importing, and listing jobs.
- Local Markdown draft export for queued jobs.
- Unsupported-claim warnings for requirements not supported by the public profile.
- Dry-run application packets that default to no submission.
- Status updates and daily workflow summaries toward the application target.
- User criteria loaded from `config/preferences.local.yaml` when present.
- Hard skips for local-only and mandatory Mandarin requirements.
- Mandatory remarks for weak or skipped matches.
- Streamlit web dashboard for local/manual real-world testing.
- Local CV upload, replace, remove, and status display in the Streamlit app.
- Local CV text extraction and keyword signal detection.
- PDF, DOCX, and best-effort legacy DOC CV uploads.
- Public LinkedIn job-card search and public web-result search for selected
  platforms.
- Optional SerpAPI-backed search through Streamlit secrets or environment.
- Malaysia city autocomplete with CountriesNow API and local fallback.
- Search run logs, scoring, dedupe, and queue insertion for up to 50 results.
- Page-level descriptions and sample data for the web app.
- Production-readiness page and secrets template.
- Tests and local verification script.

Not included yet:

- Authenticated job-board scraping.
- Auto-submission.
- LLM-generated cover letters.
- Live job-board browser automation.
- Public deployment authentication and per-user storage.
- Guaranteed legacy `.doc` extraction for every old Word binary format.

## Success Criteria

- A public GitHub repository can be created without exposing private data.
- A developer can run the tests on a fresh clone.
- The candidate profile does not include unsupported or private claims.
- The scoring rules are easy to inspect and adjust.
- The Streamlit app can run a real public search and insert scored results.
- The next development phase is clear.

## Reference Projects Studied

- `kopi-kompas`: strong README style, explicit public/private API-key boundary,
  `AGENTS.md` as a handover document, and a single check script.
- `tiny-tapsters`: clear project layout, explicit validation gate, and strong
  warnings around secrets and shipped artifacts.
- `agustiar-data-pipeline`: Python project structure, `pyproject.toml`,
  requirements files, config example pattern, tests, and GitHub Actions CI.
- `random_recall`: existing Flutter starter structure and GitHub remote naming.

Useful patterns were adapted; unrelated app code was not copied.
