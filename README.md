# Job Hunter

Job Hunter is a Streamlit app that searches, scores, and ranks Kuala Lumpur data jobs using criteria the user controls. Current version: v1.11.0.

Live app: [jobs-hunter.streamlit.app](https://jobs-hunter.streamlit.app/)

## What It Does

- Searches selected public job sources for up to 50 results per session.
- Supports LinkedIn, JobStreet, Indeed, Foundit, and selected company career pages.
- Uses SerpAPI when `SERPAPI_API_KEY` is configured and a limited public-search fallback otherwise.
- Accepts an optional PDF, DOCX, or best-effort legacy DOC CV.
- Lets users search and score jobs without uploading a CV.
- Makes target titles, primary strengths, bonus skills, hard skips, location, posting age, strong-match goal, and session cap editable.
- Scores each result with visible reasons and mandatory remarks for weak or skipped matches.
- Shows real search progress, including the provider, current result, duplicate checks, stale or closed jobs, and scoring activity.
- Stores the real posting date when one can be verified and displays `Unknown` otherwise.
- Skips a result when its known posting date is older than the selected limit.
- Skips visible closed, filled, unavailable, or expired postings.
- Deduplicates the same title, company, and location across platforms.
- Finds an official HTTPS application destination when the readable posting provides one.
- Opens Apply in a new browser tab, falling back to the original posting when no separate application URL is available.
- Keeps CV files, extracted CV text, local queue data, preferences, and secrets out of Git.

## How To Use The Web App

### 1. Profile & CV

Uploading a CV is optional.

- Upload PDF, DOCX, or DOC to keep a private profile reference.
- Replace or remove the saved CV at any time.
- The app shows primary and bonus skill signals found in readable CV text.
- After saving, click **Continue to Search jobs** to move directly to the next
  step.
- Skip this page if you want to search using only the editable criteria.

On Streamlit Community Cloud, uploaded data belongs to that app session/storage environment. A public deployment should not be treated as a private multi-user account system until authentication and per-user storage are added.

### 2. Search Jobs

1. Use the single **Search criteria** panel to edit target job titles, required
   description keywords, bonus skills, and hard-skip phrases. These values
   control both searching and scoring.
2. Set the **Strong-match goal**. This is the exact number of strong results you hope to find; it is not a minimum, maximum, or stopping rule.
3. Set **Maximum jobs in one session**. This is the search limit, capped at 50.
4. Choose one searchable Malaysia **Location**.
5. Select the job platforms.
6. Choose **Date posted**: past 24 hours, past week, past month, or any time.
7. Click **Run search and score jobs**.
8. Watch the progress bar and activity log.
9. Click **Review Job queue** when the run finishes.

`Past month` is the default. Start with a smaller maximum while testing, especially with SerpAPI's free allowance.

### 3. Job Queue

The queue is ordered by score and shows:

- score and decision;
- actual posting date, or `Unknown` when the source does not expose one;
- title, company, and location;
- match reasons and low-suitability remarks;
- description and source link.

Filter by decision, choose a job, and click **Apply**. Job Hunter prefers a discovered official application URL and otherwise opens the original posting in a new browser tab.

## Apply Boundary

The hosted Streamlit server cannot take over the visitor's existing logged-in browser session, bypass CAPTCHA, or safely complete arbitrary third-party forms. LinkedIn also prohibits third-party software and browser extensions that automate activity on LinkedIn.

For that reason, Job Hunter performs the supported part of the application flow:

1. locate a same-site or recognized ATS HTTPS application destination where possible;
2. fall back to the original job posting when discovery is blocked or unsupported;
3. show its hostname and open that destination in a new tab;
4. leave login, CAPTCHA, required questions, final review, and submission in the user's browser.

Opening a page is never recorded or described as a submitted application.

## Search Boundary

With SerpAPI configured, the app reads Google organic results for the selected platforms. Without it, the app tries public LinkedIn job cards and public web-result pages. Public pages can be incomplete or blocked.

Posting-age filters are sent to providers that support them. Job Hunter also checks dates it can parse from search metadata or structured `JobPosting` data. Unknown dates remain visible for review rather than being mislabeled as new.

Destination availability checks are limited to trusted source domains. If a site blocks the check, the activity log says availability could not be confirmed and keeps the result for review.

## SerpAPI Setup

Add this to Streamlit Community Cloud secrets:

```toml
SERPAPI_API_KEY = "your-key-here"
```

Do not commit the real key or `.streamlit/secrets.toml`.

## Run Locally

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run src/app.py
```

Run the complete automated check:

```sh
./tool/check.sh
```

## Deploy On Streamlit Community Cloud

Use this repository and set the app entry point to:

```text
src/app.py
```

Add `SERPAPI_API_KEY` in the deployment's Secrets settings. The live app automatically redeploys from the configured GitHub branch after a push.

## Public And Private Data

This repository is public. Never commit:

- the actual CV or extracted CV text;
- email, phone number, home address, passport, or visa details;
- platform passwords, cookies, exported browser profiles, or CAPTCHA data;
- API keys;
- local queue databases or application records;
- `config/preferences.local.yaml` or `.streamlit/secrets.toml`.

Use `config/preferences.example.yaml` as the safe public template.

## Project Layout

| Path | Purpose |
|---|---|
| `src/app.py` | Streamlit interface for Profile, Search, Queue, and Apply links |
| `src/job_hunter/search.py` | Query building, result parsing, freshness checks, metadata discovery, and live progress |
| `src/job_hunter/scoring.py` | Deterministic explainable job scoring |
| `src/job_hunter/queue.py` | Additive SQLite storage and duplicate detection |
| `src/job_hunter/cv_store.py` | Private CV save, replace, and removal |
| `src/job_hunter/cv_parser.py` | PDF and Word text extraction plus skill-signal detection |
| `src/job_hunter/locations.py` | Malaysia city lookup with local fallback |
| `src/job_hunter/runtime_config.py` | Streamlit secrets and environment configuration |
| `config/preferences.example.yaml` | Public criteria template |
| `docs/` | Product, scoring, architecture, pipeline, and release plans |
| `tests/` | Queue, search, scoring, privacy, and Streamlit regression tests |
| `tool/check.sh` | Complete local test gate |

The older command-line helpers remain for backward compatibility, but the supported user journey is the Streamlit app described above.
