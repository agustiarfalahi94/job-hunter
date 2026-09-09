# Job Hunter

Local-first job matching and application planning assistant. Current version:
v1.10.0.

The goal is to help review many job openings quickly without pretending the
system can safely apply everywhere on its own. The current version includes
the project brain, a factual candidate profile, preferences template, scoring
rules, Streamlit dashboard, PDF/Word CV upload and text extraction, public
and optional API-backed search, editable search criteria, city lookup, SQLite
queue, CSV import, duplicate detection, draft exports, and a small CLI.

## What It Does

- Scores a job against target roles, locations, preferred keywords, and avoid
  keywords.
- Extracts readable text from locally uploaded PDF, DOCX, and best-effort DOC
  CV files.
- Detects primary and bonus CV signals from the extracted text.
- Searches public LinkedIn job cards and public web-result pages for selected
  job platforms.
- Supports optional SerpAPI search through Streamlit secrets.
- Lets the user limit results to the past 24 hours, week, month, or any time.
- Checks search cards and trusted destination pages for closed-job labels before
  adding a result to the queue.
- Loads Malaysia city options from a public city API with local fallback.
- Lets the user edit target titles, primary keywords, bonus keywords, hard
  skips, strong-match goal, and session cap inside the app.
- Adds and scores discovered search results into the local queue.
- Stores scored jobs in a local SQLite queue.
- Deduplicates exact same jobs by title/company/location, even when different
  platforms have different URLs.
- Imports a simple CSV with `title`, `company`, `location`, `description`, and
  `source_url` columns.
- Exports a local Markdown application draft for a queued job.
- Exports a dry-run application packet for human review.
- Flags unsupported job requirements instead of inventing matching experience.
- Shows the daily strong-match goal in the sidebar.
- Shows live platform, availability-check, scoring, duplicate, and skip activity
  while a search is running.
- Updates local application status after human action.
- Loads private local preferences from `config/preferences.local.yaml`.
- Applies hard skips for local-only and mandatory Mandarin requirements.
- Runs as a Streamlit web app for daily use.
- Saves/replaces/removes a local CV file under a git-ignored private folder.
- Saves extracted CV text under the same git-ignored private folder.
- Separates automated platform search from fully manual scoring.
- Separates public project templates from private candidate inputs.
- Documents the first application workflow before browser automation exists.
- Keeps the real CV, contact details, secrets, and local preferences out of Git.

## Public/Private Boundary

This repository is intended to be public. Do not commit:

- The actual CV file.
- Phone number, email address, passport, visa, or address details.
- Job-board session cookies, exported browser profiles, or application drafts
  containing private information.
- API keys or model provider credentials.
- `.streamlit/secrets.toml`.

Use `config/preferences.example.yaml` as the public template. Keep the real
working copy at `config/preferences.local.yaml`.

## Project Layout

| Path | Purpose |
|---|---|
| `src/job_hunter/profile.py` | Public, CV-supported profile summary with contact details excluded |
| `src/job_hunter/scoring.py` | Deterministic v0.1 scoring engine |
| `src/job_hunter/queue.py` | SQLite queue, scoring-at-import, and duplicate detection |
| `src/job_hunter/cv_store.py` | Local private CV save, replace, remove, and status helpers |
| `src/job_hunter/cv_parser.py` | Extracts CV text and detects CV keyword signals |
| `src/job_hunter/search.py` | Builds public search queries, parses result pages, and ingests results |
| `src/job_hunter/locations.py` | Loads/filter Malaysia city choices for autocomplete |
| `src/job_hunter/runtime_config.py` | Reads optional API search config from secrets/env |
| `src/job_hunter/cli.py` | Local commands for adding, importing, and listing jobs |
| `src/job_hunter/drafts.py` | Truthful draft generation and unsupported-claim warnings |
| `src/job_hunter/application_packet.py` | Dry-run application packets with submit safety notes |
| `src/job_hunter/workflow.py` | Daily progress summary and next-action guidance |
| `src/job_hunter/preferences.py` | Simple local preference loading |
| `src/app.py` | Streamlit web dashboard |
| `config/preferences.example.yaml` | Safe preferences template |
| `docs/` | Product spec, profile, scoring, pipeline, architecture, and development plan |
| `tests/` | Unit tests for scoring and the public profile boundary |
| `tool/check.sh` | Local test gate |

## Run It

```sh
python -m venv .venv
source .venv/bin/activate
./tool/check.sh
```

## Web App

Run locally:

```sh
streamlit run src/app.py
```

The web app has two modes in the sidebar.

### Automated Search

Use this when you want Job Hunter to search selected platforms, score results,
and fill the queue.

1. Open `Profile & CV`.
2. Upload or replace your CV. PDF and DOCX are preferred; legacy DOC is
   best-effort.
3. Open `Search setup`.
4. Edit the search and scoring criteria:
   - `Target titles`
   - `Primary strengths / description keywords`
   - `Bonus keywords`
   - `Hard skip keywords`
   - `Strong-match goal`: the exact number of high-scoring jobs you aim to find;
     it does not stop or limit a search
   - `Session cap`
5. Choose `Location`. The dropdown is searchable and uses Malaysia city data
   from a public API with a fallback list.
6. Choose platforms. With `SERPAPI_API_KEY` configured, the app uses API-backed
   search. Without it, the app falls back to public search pages.
7. Choose `Date posted`. `Past month` is the default; use `Any time` only when
   older listings are still useful.
8. Start with a low session cap such as `10` while testing, especially on the
   SerpAPI free tier.
9. Click `Run search and score jobs`. The progress bar and activity log show the
   provider, current availability check, score result, duplicates, and skips.
10. Click `Review Job queue` to open the ranked results without returning to the
    top of the page.

### Manual Scoring

Use this when you already found jobs yourself and only want Job Hunter to score
them.

1. Select `Manual scoring` in the sidebar.
2. Use `Add job` for one pasted job description.
3. Use `Import CSV` for many rows from a spreadsheet or saved research list.
4. Open `Job queue` to review the results.

### Job Queue

The queue is shared by both modes. It shows score, decision, status, title,
company, location, full description, reasons, remarks, and source link. Use the
actions below the table to export a draft, export an application packet, or
update the status after you apply manually.

For free hosting, deploy this repository on Streamlit Community Cloud and set
the app entry point to:

```text
src/app.py
```

The hosted app will use its own Streamlit Cloud storage. Treat a public
deployment as a personal demo until authentication and per-user storage exist.
Do not publish private CV files or secrets in the repository.

Optional API search uses this secret:

```toml
SERPAPI_API_KEY = "your-key-here"
```

You can set that in Streamlit Community Cloud secrets. Do not commit a real
`.streamlit/secrets.toml` file.

### Production Search Boundary

The Streamlit search button reads API-backed search results when SerpAPI is
configured. Without SerpAPI, it reads public LinkedIn job cards when available,
then uses public web-result search for the other selected platforms. It scores
the visible title/company/location/snippet/source URL. Posting-age filters are
sent to providers that support them. Before scoring, the app also checks visible
closed-job wording on the search result and trusted destination page. If a site
blocks the destination check, the activity log reports that availability could
not be confirmed and keeps the result for human review. It does not log in to
LinkedIn, JobStreet, Indeed, Foundit, or company portals. It also does not
bypass CAPTCHA, submit forms, or use saved browser sessions.

For stronger production search, configure SerpAPI first. Future providers can
be added behind `search.py`, such as Google Custom Search, Adzuna, a paid
job-search API, or official company ATS feeds. Put provider keys in Streamlit
secrets, never in Git.

## CLI

Add one pasted job:

```sh
PYTHONPATH=src python3 -m job_hunter.cli add \
  --title "Data Engineer" \
  --company "Example Analytics" \
  --location "Kuala Lumpur" \
  --description "SQL Python Airflow BigQuery migration pipelines" \
  --source-url "https://example.com/jobs/1"
```

Import CSV:

```sh
PYTHONPATH=src python3 -m job_hunter.cli import-csv data/raw/jobs.csv
```

List queue:

```sh
PYTHONPATH=src python3 -m job_hunter.cli list
```

Export a draft for queued job `1`:

```sh
PYTHONPATH=src python3 -m job_hunter.cli draft 1
```

Export a dry-run application packet for queued job `1`:

```sh
PYTHONPATH=src python3 -m job_hunter.cli packet 1
```

Mark a job as submitted after you submit it yourself:

```sh
PYTHONPATH=src python3 -m job_hunter.cli status 1 submitted
```

Check today's progress toward 20 strong matches:

```sh
PYTHONPATH=src python3 -m job_hunter.cli today --target 20
```

The current local target is 20 strong matches, with up to 50 suitable matches
for review.

## Design Notes

The style follows the user's existing projects:

- Plain README first, with concrete behavior before architecture.
- Local config templates are committed; real secrets and personal data are not.
- The important rules live in `AGENTS.md` so future AI coding sessions do not
  have to guess the safety boundary.
- Tests cover the small runtime surface from day one.

## Status

This is a local daily workflow assistant with public/API search support, not a
live job-board login or auto-apply bot yet. The first usable loop is:

1. Upload a CV locally.
2. Search platform results, paste a job description, or import a CSV.
3. Score jobs against the candidate profile and preferences.
4. Put promising jobs into a human-reviewed application queue.
5. Generate tailored drafts only from supported experience.
6. Submit manually until browser automation is designed and tested.
7. Mark submitted jobs locally in the queue.
