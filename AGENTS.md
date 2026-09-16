# AGENTS.md - Job Hunter Engineering Guide

## Start Here

Job Hunter v1.15.1 is a public Streamlit job-discovery and matching app. Read this file, `README.md`, and the relevant files in `docs/` before changing behavior.

## Non-Negotiable Rules

1. Keep the repository safe to publish.
2. Never commit CVs, extracted CV text, contact details, job-board credentials, cookies, API keys, private preferences, local databases, application records, identity documents, or form answers.
3. Do not invent candidate experience. Gemini and deterministic reasons must use only supplied CV text, editable criteria, and job content.
4. Criteria-based search must never load or send CV text.
5. Hosted data stays in `SessionWorkspace`; do not route Streamlit users through shared files or SQLite.
6. Background workers must not call Streamlit or mutate `st.session_state`. Publish immutable events and matches for the Streamlit thread to accept.
7. Respect ceilings: 12 discovery requests, 50 unique candidates, 50 page fetches, 50 scoring attempts, two workers, and five minutes of new-work scheduling.
8. Stop must prevent new work after cancellation is observed. Keep already completed results and use bounded timeouts for in-flight calls.
9. Do not automate login, CAPTCHA, prohibited platform activity, or final application submission.
10. Run `./tool/check.sh` before every commit. Report anything unverified instead of guessing.

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
