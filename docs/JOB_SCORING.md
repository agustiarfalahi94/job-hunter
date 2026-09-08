# Job Scoring

## Goal

Score jobs for fit, not ego. A high score means the role appears aligned with
the candidate's supported experience and preferences. It does not mean the
application should be submitted automatically.

## v0.1 Inputs

- Job title.
- Job description.
- Location.
- Remote policy or employment notes.
- Local preferences from `config/preferences.local.yaml`.

## Default Weights

| Signal | Points | Reason |
|---|---:|---|
| Role title match | 30 | Strong signal that the role category is right |
| Preferred keyword match | 40 | Captures concrete tools and responsibilities |
| Location match | 15 | Avoids spending effort on impossible roles |
| Remote/hybrid compatibility | 10 | Helps prioritise practical roles |
| Avoid keyword penalty | -30 | Rejects roles with strong mismatch signals |

Scores are clamped to 0-100.

## Decisions

| Score | Decision |
|---:|---|
| 70-100 | `shortlist` |
| 50-69 | `review` |
| 0-49 | `reject` |

Any job with several avoid keywords should fall into `reject` even if it has a
few attractive words.

## Future Improvements

- Store scored jobs in SQLite.
- Add duplicate detection by company/title/location/job URL.
- Add explainable LLM review after deterministic scoring.
- Add a "claim support" check that maps generated draft sentences back to
  candidate-profile evidence.
