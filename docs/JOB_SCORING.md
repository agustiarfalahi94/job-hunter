# Job Scoring

## Principle

A score estimates fit against supplied evidence. It is not a hiring prediction and never authorizes automatic submission.

## Modes

**Criteria-based search** compares job title, location, and description with editable target roles, primary strengths, bonus skills, hard skips, and the shortlist threshold. CV text is absent from this mode's payload.

**CV-based search** sends readable session CV text and the same editable criteria. The prompt permits only supplied evidence and treats missing qualifications as unknown.

## Criteria

Default target roles include Data Analyst, Data Engineer, BI Developer, Reporting Analyst, Reporting Engineer, Business Intelligence Analyst, BI Analyst, and BI Engineer.

Primary strengths are Power BI, SSRS, and Google BigQuery. Bonus experience includes PostgreSQL, Alibaba MaxCompute, Domo, MySQL, T-SQL/MSSQL, data migration, Apache Airflow, Docker, Python, Python scripts, PySpark, Git/GitHub/GitLab, CI/CD pipeline variables, Agile/Scrum, and CAB deployment. Users can edit all of these fields in the app.

Hard skips include local/Malaysian-only requirements and mandatory Mandarin-speaker requirements. Normalized hard-skip matching runs before Gemini. Managerial titles remain eligible when their descriptions fit the supplied evidence.

## Gemini Result

Gemini returns structured JSON containing a 0-100 score, reasons, and remarks. The app derives the displayed decision from the configured threshold:

| Score | Decision |
|---:|---|
| shortlist threshold to 100 | `shortlist` |
| 50 to below threshold | `review` |
| 0-49 | `reject` |

Weak results receive remarks. A result scored from a snippet or unavailable description is marked as limited evidence.

## Fallback And Cache

Missing configuration, authentication failure, quota exhaustion, timeout, invalid model output, service failure, or cancellation uses the deterministic scorer and labels the engine `Deterministic fallback`. The fallback uses the same editable criteria and never invents experience.

Successful and fallback results are cached within the visitor's session by a hash of job content, matching mode input, model, and prompt version. CV replacement or removal invalidates CV-mode cache entries. No raw key, prompt, CV text, or cache input is logged.
