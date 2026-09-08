# Job Hunter

Local-first job matching and application planning assistant. Current version:
v0.2.0.

The goal is to help review many job openings quickly without pretending the
system can safely apply everywhere on its own. The current version builds the
project brain and the first local queue: a factual candidate profile,
preferences template, scoring rules, application pipeline notes, SQLite
storage, CSV import, duplicate detection, and a small CLI.

## What It Does

- Scores a job against target roles, locations, preferred keywords, and avoid
  keywords.
- Stores scored jobs in a local SQLite queue.
- Deduplicates by `source_url`, or by title/company/location when no URL is
  available.
- Imports a simple CSV with `title`, `company`, `location`, `description`, and
  `source_url` columns.
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
| `src/job_hunter/cli.py` | Local commands for adding, importing, and listing jobs |
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

## Design Notes

The style follows the user's existing projects:

- Plain README first, with concrete behavior before architecture.
- Local config templates are committed; real secrets and personal data are not.
- The important rules live in `AGENTS.md` so future AI coding sessions do not
  have to guess the safety boundary.
- Tests cover the small runtime surface from day one.

## Status

This is a local assistant, not a website automation bot yet. The first usable
loop is:

1. Paste or import a job description.
2. Score it against the candidate profile and preferences.
3. Put promising jobs into a human-reviewed application queue.
4. Generate tailored drafts only from supported experience.
5. Submit manually until browser automation is designed and tested.
