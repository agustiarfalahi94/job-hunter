# Discovery Diagnostics Hotfix

## Scope

User-approved production debugging: Indeed-only Data Analyst / Power BI / Kuala Lumpur / Any time returned zero candidates but reported scored-result success. Discovery happens before Gemini, so changing the scoring model cannot repair an empty discovery response.

## Findings And Execution

- The parser ignored SerpAPI error fields and the runner always reported queue success after an error-free loop, including zero candidates. SerpAPI documents HTTP 200 empty responses and explicit error/status fields.
- Add safe provider-response classification and per-query counts before asserting a discovery root cause. Keep raw responses and API URLs/keys out of logs.
- Warn when no jobs were discovered/scored; fail when all discovery requests failed.
- Update the inherited 2.5 model default to officially listed stable 3.8. Preserve secret/environment overrides and fallback provenance.
- Write failing mocked regressions, implement, review, run the full gate, push the feature branch, verify CI, integrate main, and inspect a bounded production reproduction. Do not claim any exact vacancy is guaranteed discoverable.

## Production Follow-Up

The diagnostic release v1.17.1 passed 274 tests and feature/main CI. A fresh production test with Data Analyst / Power BI / Kuala Lumpur / Indeed / Any time returned 10 web results on each of two queries but zero accepted job links, proving the failure preceded scoring. Production displayed the user's explicitly configured gemini-3.8-flash. No CV or private data was sent.

Follow-up v1.17.2 targets Indeed vacancy paths, shows exclusion-reason counts, and fixes the observed disabled Run button with a once-only full-page terminal refresh. Preserve all selected settings and accepted results across that rerun. Validate the query/rejection/refresh regressions and repeat a bounded production discovery test after deployment; do not claim the exact reference URL must appear.

## Rollback

Revert this hotfix release commit if imports/navigation fail. Do not alter secrets, CV/session storage, other projects, or existing worktrees.
