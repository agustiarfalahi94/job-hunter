# Job Hunter

Local-first job matching and application planning assistant.

The goal is to help review many job openings quickly without pretending the
system can safely apply everywhere on its own. v0.1 builds the project brain:
a factual candidate profile, preferences template, scoring rules, application
pipeline notes, and a small tested Python scoring module.

## What It Does In v0.1

- Scores a job against target roles, locations, preferred keywords, and avoid
  keywords.
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

## Design Notes

The style follows the user's existing projects:

- Plain README first, with concrete behavior before architecture.
- Local config templates are committed; real secrets and personal data are not.
- The important rules live in `AGENTS.md` so future AI coding sessions do not
  have to guess the safety boundary.
- Tests cover the small runtime surface from day one.

## Status

v0.1 is a project foundation, not a website automation bot yet. The first
usable loop is:

1. Paste or import a job description.
2. Score it against the candidate profile and preferences.
3. Put promising jobs into a human-reviewed application queue.
4. Generate tailored drafts only from supported experience.
5. Submit manually until browser automation is designed and tested.
