# Job Scoring

## Principle

A score estimates fit against supplied evidence. It is not a hiring prediction and never authorizes automatic submission.

## Modes

**Criteria-based search** compares job title, location, and description with editable target roles, primary strengths, bonus skills, hard skips, and the shortlist threshold. CV text is absent from this mode's payload.

**CV-based search** sends readable session CV text and the same editable criteria. The prompt permits only supplied evidence and treats missing qualifications as unknown.

Criteria mode starts with empty selected web criteria. CV mode merges configured roles/hard skips and primary/bonus skills detected in the saved CV once per CV fingerprint, preserving existing selections and later manual edits. It never derives location or sources from the CV. All title/keyword text comparisons ignore case. Values within each list are alternatives, and bonuses are optional advantages found in the title or description, not discovery filters or mandatory qualifications. More bonus matches may earn more points. Any hard-skip match excludes a job. Location, sources and freshness are independent search constraints. The selected location is used for matching; no hidden Kuala Lumpur preference is applied to another location.

Location values are also OR alternatives: cities, ISO countries, ASEAN, or the documented APAC preset. Country selections accept observed cities in that country; regional selections accept member-country evidence. Confirmed geography mismatches skip before scoring; unknown geography stays unverified. The same shared geographic matcher supplies deterministic location points. Fifty is a discovery/checking ceiling before scoring, not fifty best matches; the queue ranks retained candidates. See [Geographic Scopes](LOCATION_SCOPES.md).

Persistence, case-insensitive comparison, and OR alternatives apply to every one of Target job titles, Required description keywords, Bonus keywords, and Hard skip keywords, including custom typed values. Positive title/primary signals can discover or strengthen a match, any bonus can add points without being mandatory, and any hard skip overrides positive signals. Direct LinkedIn queries use the same quoted OR alternatives as web/SerpAPI queries. External sources may still limit or reinterpret queries; the app's deterministic matching and Gemini instructions preserve these rules.

Available dropdown suggestions are a static catalog from the project's original preferences. Criteria mode leaves them unselected; CV mode selects the evidence-backed subset and configured role/rule values without changing the catalog. All four fields accept custom terms; the catalog is not an allowed-values restriction.

## Criteria

Default target roles include Data Analyst, Data Engineer, BI Developer, Reporting Analyst, Reporting Engineer, Business Intelligence Analyst, BI Analyst, and BI Engineer.

Primary strengths are Power BI, SSRS, and Google BigQuery. Bonus experience includes PostgreSQL, Alibaba MaxCompute, Domo, MySQL, T-SQL/MSSQL, data migration, Apache Airflow, Docker, Python, Python scripts, PySpark, Git/GitHub/GitLab, CI/CD pipeline variables, Agile/Scrum, and CAB deployment. Users can edit all of these fields in the app.

Hard skips include local/Malaysian-only requirements and mandatory Mandarin-speaker requirements. Matching normalizes punctuation, word order, plurals, and supported requirement concepts such as `must be Malaysian` or `Mandarin required`; optional wording such as `Mandarin is an advantage` is not excluded. Generic custom phrases receive conservative normalized-term matching. Hard skips run before Gemini. Managerial titles remain eligible when their descriptions fit the supplied evidence.

## Gemini Result

Gemini returns structured JSON containing a 0-100 score, reasons, and remarks. The app derives the displayed decision from the configured threshold:

| Score | Decision |
|---:|---|
| shortlist threshold to 100 | `shortlist` |
| 50 to below threshold | `review` |
| 0-49 | `reject` |

Weak results receive remarks. A result scored from a snippet or unavailable description is marked as limited evidence.

Gemini 2.5 Flash scoring disables thinking; Gemini 3 Flash uses low thinking, including current models that reject minimal. Scoring allows 2048 output tokens for structured JSON and a bounded 30-second provider timeout. Malformed JSON is explicitly classified and retried at most once. An unavailable model can recover using Google's supported Flash model listing within the same two-attempt ceiling. The connection check sends only a synthetic criteria/job pair, never session CV text.

## Fallback And Cache

Missing configuration, authentication failure, quota exhaustion, timeout, invalid model output, service failure, or cancellation uses the deterministic scorer and labels the engine `Deterministic fallback`. The fallback uses the same editable criteria and never invents experience.

Successful and fallback results are cached within the visitor's session by a hash of job content, matching mode input, model, and prompt version. CV replacement or removal invalidates CV-mode cache entries. No raw key, prompt, CV text, or cache input is logged.
