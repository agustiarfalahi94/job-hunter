# AGENTS.md - Job Hunter Engineering Guide

## Start Here

Job Hunter v1.18.3 is a public Streamlit job-discovery and matching app with optional private Google accounts. Read this file, `README.md`, and the relevant files in `docs/` before changing behavior.

## Non-Negotiable Rules

1. Keep the repository safe to publish.
2. Never commit CVs, extracted CV text, contact details, job-board credentials, cookies, API keys, private preferences, local databases, application records, identity documents, or form answers.
3. Do not invent candidate experience. Gemini and deterministic reasons must use only supplied CV text, editable criteria, and job content.
4. Criteria-based discovery/matching must never load or send CV text. Separately authorized private account restore/save may retain the CV without exposing it to scoring.
5. Hosted live data stays in `SessionWorkspace`; do not route Streamlit users through shared files or SQLite. Only the authenticated account adapter may persist encrypted private snapshots to the configured backend.
6. Background workers must not call Streamlit or mutate `st.session_state`. Publish immutable events and matches for the Streamlit thread to accept.
7. Respect ceilings: 12 discovery requests, 50 unique candidates, 50 page fetches, 50 scoring attempts, two workers, and five minutes of new-work scheduling.
8. Stop must prevent new work after cancellation is observed. Keep already completed results and use bounded timeouts for in-flight calls.
9. Do not automate login, CAPTCHA, prohibited platform activity, or final application submission.
10. Run `./tool/check.sh` before every commit. Report anything unverified instead of guessing.
11. New web sessions start with no selected titles, keywords, locations, platforms, or companies. Suggestions and CLI defaults are not selected web criteria. Keep selected web settings separate from disposable widget keys.
12. Company-name lookup sends only public company name and requested region to Gemini Google Search. Require grounded official/regional pages and an official careers link, validate HTTPS/public network destinations, and cache lookup successes/failures per session. Never guess a domain or send CV text for this lookup.
13. Locations are OR scopes: cities, ISO countries, or documented regional presets. Apply identical geographic membership to discovery, pre-scoring checks, and deterministic scoring. Missing geography remains unverified. Preserve legacy single-location CLI input.
14. Keep at most five selected/resolved company sites and five company/region lookup pairs per selection. Validate lookup budgets before contacting Gemini; regional presets count as one company-verification region rather than dozens of country calls.
15. Optional quick-apply filters apply only to their named platform and require vacancy-associated controls, never description words. Manual date/expiry corrections retain user provenance; merge dates and verification atomically. No alternate-source storage/display; retain primary-identity duplicate checks.
16. Discovery errors must never be reported as empty success. Report API web-result/eligible-link counts and safe error classifications; never expose query URLs with keys or raw provider errors. Zero scored jobs require a warning, not a queue-success claim.
17. Accounts are off by default; enabled invalid setup fails closed. Use native Streamlit Google claims, verified-email allowlists and stable issuer/subject ownership, never client-supplied ownership. Keep Supabase secret keys and encryption keys server-only; service credentials bypass RLS.
18. Never overwrite after failed account load or conflicting revision. Clear data using revision-aware tombstones. Save accepted worker results on the Streamlit thread; sign-out, denial and account switching cancel work and clear all private state. Caches, controllers, cookies and provider tokens are not persisted. Confirm destructive actions, show failed saves honestly, and retain encryption keys privately.
19. Hosted SerpAPI pagination shares the twelve-request ceiling and processes initial source/signal queries first. Prefer validated advancing offsets from official continuation links; rebuild original server URL/parameters, never follow provider-supplied destinations or replacements. For standard Google results only, a full ten-result page with the pagination field entirely absent may advance by ten up to offset forty. A present pagination field without a valid next link, a short page, a structured Jobs payload, a repeated page, or an empty page must stop. Indeed result-title separators do not establish an employer; preserve complete titles and recognized trailing location evidence.

## Git Flow

- Use `codex/` feature branches.
- Keep commits meaningful and scoped.
- Public remote: `https://github.com/agustiarfalahi94/job-hunter.git`.
- Verify the feature-branch CI before integrating into `main`, then verify `main` and production separately.

## Validation

```sh
PYTHON_BIN=/path/to/.venv/bin/python ./tool/check.sh
python -m compileall -q src tests
python -m pip check
git diff --check
```

Use mocked providers for automated tests. Do not consume SerpAPI or Gemini quota in the test suite.
