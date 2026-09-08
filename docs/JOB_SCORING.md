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

## Current Criteria

Target titles:

- Data Analyst
- Data Engineer
- BI Developer
- Reporting Analyst
- Reporting Engineer
- Business Intelligence Analyst
- BI Analyst
- BI Engineer

Primary keywords:

- Power BI
- SSRS
- Google BigQuery / BigQuery

A strong match should include at least one primary keyword. Bonus keywords add
confidence, but they do not replace the primary signal.

Bonus keywords include PostgreSQL, Alibaba MaxCompute, Domo, MySQL, T-SQL,
MSSQL, data migration, Apache Airflow, Docker, Python, Python scripts, PySpark,
Git/GitHub/GitLab, CI/CD pipeline variables, Agile/Scrum, and CAB deployment.

Hard skip keywords:

- `locals/malaysian only`
- `mandarin speaker is mandatory`

Managerial titles are allowed when the description still fits the candidate's
hands-on BI/reporting/data engineering experience.

## Default Weights

| Signal | Points | Reason |
|---|---:|---|
| Role title match | 30 | Strong signal that the role category is right |
| Primary keyword match | 50-60 | Captures the main advantage: Power BI, SSRS, or BigQuery |
| Bonus keyword match | 10 | Captures supporting experience |
| Location match | 15 | Avoids spending effort on impossible roles |
| Remote/hybrid compatibility | 10 | Helps prioritise practical roles |
| Avoid keyword penalty | -30 | Rejects roles with strong mismatch signals |

Scores are clamped to 0-100.

## Decisions

| Score | Decision |
|---:|---|
| 90-100 | `shortlist` |
| 50-69 | `review` |
| 0-49 | `reject` |

Hard skips return `skip` at score 0 with remarks. Low-suitability and 0% jobs
must include remarks so it is clear why the job was skipped or deprioritised.

## Future Improvements

- Store scored jobs in SQLite.
- Add duplicate detection by company/title/location/job URL.
- Add explainable LLM review after deterministic scoring.
- Add a "claim support" check that maps generated draft sentences back to
  candidate-profile evidence.
