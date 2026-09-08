# Job Hunter

Local-first job matching and application planning assistant. Current version:
v1.3.0.

The goal is to help review many job openings quickly without pretending the
system can safely apply everywhere on its own. The current version includes
the project brain, a factual candidate profile, preferences template, scoring
rules, Streamlit dashboard, local CV upload storage, SQLite queue, CSV import,
duplicate detection, draft exports, and a small CLI.

## What It Does

- Scores a job against target roles, locations, preferred keywords, and avoid
  keywords.
- Stores scored jobs in a local SQLite queue.
- Deduplicates exact same jobs by title/company/location, even when different
  platforms have different URLs.
- Imports a simple CSV with `title`, `company`, `location`, `description`, and
  `source_url` columns.
- Exports a local Markdown application draft for a queued job.
- Exports a dry-run application packet for human review.
- Flags unsupported job requirements instead of inventing matching experience.
- Tracks daily application progress against a target.
- Updates local application status after human action.
- Loads private local preferences from `config/preferences.local.yaml`.
- Applies hard skips for local-only and mandatory Mandarin requirements.
- Runs as a Streamlit web app for daily use.
- Saves/replaces/removes a local CV file under a git-ignored private folder.
- Explains every Streamlit page with sample data and current/future workflow
  boundaries.
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

Use `config/preferences.example.yaml` as the public template. Keep the real
working copy at `config/preferences.local.yaml`.

## Project Layout

| Path | Purpose |
|---|---|
| `src/job_hunter/profile.py` | Public, CV-supported profile summary with contact details excluded |
| `src/job_hunter/scoring.py` | Deterministic v0.1 scoring engine |
| `src/job_hunter/queue.py` | SQLite queue, scoring-at-import, and duplicate detection |
| `src/job_hunter/cv_store.py` | Local private CV save, replace, remove, and status helpers |
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

The web app currently has these pages:

- `Profile & CV`: upload, replace, or remove the local private CV file.
- `Search setup`: configure the intended 50-job search flow and preview the
  future scraping progress log.
- `Job queue`: review scored jobs, remarks, decisions, and source links.
- `Add job`: paste one job description and score it immediately.
- `Import CSV`: bulk-load jobs with example CSV data.
- `Drafts & packets`: export application drafts and review packets.
- `Progress`: check progress toward the current 20-strong-match target.

For free hosting, deploy this repository on Streamlit Community Cloud and set
the app entry point to:

```text
src/app.py
```

The hosted app will use its own Streamlit Cloud storage. Treat a public
deployment as a demo until authentication and per-user storage exist. Do not
upload private CV files or secrets to a public deployment.

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
PYTHONPATH=src python3 -m job_hunter.cli today --target 100
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

This is a local daily workflow assistant, not a live website automation bot
yet. The first usable loop is:

1. Paste or import a job description.
2. Score it against the candidate profile and preferences.
3. Put promising jobs into a human-reviewed application queue.
4. Generate tailored drafts only from supported experience.
5. Submit manually until browser automation is designed and tested.
6. Mark submitted jobs locally and check daily progress.

The target automated loop is documented in the Streamlit `Search setup` page:
choose platforms, search up to 50 jobs, score and deduplicate them, then review
before any apply action.
