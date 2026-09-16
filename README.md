# Job Hunter

Job Hunter v1.15.3 is a Streamlit app that discovers, scores, and organizes data jobs. The live app is [jobs-hunter.streamlit.app](https://jobs-hunter.streamlit.app/).

## What It Does

- Searches LinkedIn, JobStreet, Indeed, Foundit, and up to five selected or user-entered company career sites.
- Discovers by job title **or** description keyword, so an unfamiliar title can still be found.
- Targets up to 50 unique jobs per run with at most 12 discovery requests, 50 detail-page fetches, 50 scoring calls, two job workers, and five minutes of new-work scheduling.
- Reads full descriptions from structured job data or recognized page sections; otherwise labels scoring as snippet-based or unavailable.
- Verifies job-specific posting dates where possible, labels unknown dates honestly, and skips known stale or closed jobs.
- Excludes semantic variants of local-only, Malaysian-only, and mandatory-Mandarin requirements before scoring.
- Uses Gemini for evidence-based matching when configured and visibly labels deterministic fallback scores when Gemini is unavailable.
- Consolidates confident duplicates while preserving alternate source links.
- Opens the safest application page in a new tab and lets the user record an application manually.

## Web App Tutorial

### 1. Choose A Matching Mode

Use **Matching mode** in the sidebar:

- **Criteria-based search** uses only the editable titles, primary keywords, bonus keywords, hard skips, and location. It never reads or sends CV text.
- **CV-based search** compares each job with both the editable criteria and readable text from the CV saved in the current session.

Profile & CV is hidden in Criteria-based mode. Switching modes does not clear a saved CV; it remains available when you switch back to CV-based mode, within the same session.

### 2. Optional CV

Open **Profile & CV** to upload PDF, DOCX, or best-effort legacy DOC. Click **Save CV**, then **Continue to Search jobs**. A CV can be replaced or removed at any time. Removing it also clears the visible upload selection.

CV bytes and extracted text are session-only in the hosted app. They are not written to the repository or a shared server database. They disappear when the Streamlit session resets, the app restarts, or the session expires.

### 3. Search Jobs

1. Open **Search jobs**.
2. Edit the title, required description, bonus, and hard-skip terms. Hard skips use normalized intent matching for supported eligibility and language requirements, so wording does not need to be identical.
3. Type or select one city in **Location**.
4. Select job platforms and a posting-age limit.
5. In **Company career sites**, choose Accenture, HCLTech, Razer, Prudential Malaysia, or Accord Innovations. The selector is case-insensitive and also accepts a public HTTPS careers domain, up to five sites total. Company sites require SerpAPI.
6. Click **Run search and score jobs**.
7. Follow the progress bar and activity log. Fifty is the maximum, not a required result count; a completed search fills the bar even when sources return fewer jobs and reports the number actually checked.
8. Use **Stop search** when needed, then click **Review Job queue**.

Stop prevents new discovery, page-fetch, and scoring work after cancellation is observed. An in-flight network or Gemini request has its own timeout and may take a short time to settle; completed results are kept.

### 4. Review And Apply

The queue defaults to **Actionable** jobs. Use **All** or **Already applied** to change the view, then filter by match decision. Each row shows the scoring engine, evidence limit, description quality, date source or limitation, reasons, remarks, and alternate sources.

Select a job and click **Apply** to open the safest official destination. Login, CAPTCHA, required questions, review, and submission stay on that platform. Opening Apply never changes application status. After submitting, explicitly select **I have applied to this job**; the record is labelled as manually recorded, not platform-verified.

## API Setup

Create `.streamlit/secrets.toml` locally or add these values in Streamlit Community Cloud secrets:

```toml
SERPAPI_API_KEY = "your-serpapi-key"
GEMINI_API_KEY = "your-gemini-api-key"
GEMINI_MODEL = "gemini-2.5-flash"
```

`SERPAPI_API_KEY` enables dependable Google-backed source discovery and custom domains. Without it, the app uses a limited public-search fallback that may be blocked or incomplete. `GEMINI_API_KEY` enables Gemini matching. Without it, searches still work with a clearly labelled deterministic fallback. Never commit real keys or `.streamlit/secrets.toml`.

Use **Check Gemini connection** on Search jobs to test the configured service with synthetic data only. It does not use your CV or SerpAPI. A configured key does not guarantee valid permissions, available model access, or quota; failures are shown with a sanitized reason in this check and in search logs.

If the configured Gemini model returns not found, the app asks Google for available text-generation Flash models and retries once with a supported model, preferring stable versions. Results identify the model actually used. No model name is guessed; authentication and quota errors do not trigger model switching. Model discovery checks at most 100 entries.

Gemini 3 Flash scoring uses low thinking to reduce latency while supporting the latest Flash models, which reject minimal thinking; Gemini 2.5 Flash disables thinking. Provider requests have a 30-second timeout and at most two scoring attempts. Google SDK 1.75 or newer is required for these settings. See [Google's thinking configuration](https://ai.google.dev/gemini-api/docs/generate-content/thinking).

## Run Locally

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run src/app.py
```

Run the complete verification gate with `./tool/check.sh`.

## Deploy

On Streamlit Community Cloud, select this repository, use `src/app.py` as the entry point, and add the secrets above. Anyone with the public app URL can open it, but each visitor receives separate session-only app data rather than an account with durable storage.

## Privacy And Boundaries

Never commit CVs, extracted CV text, contact details, platform credentials, cookies, identity documents, private form answers, application records, local databases, API keys, `config/preferences.local.yaml`, or `.streamlit/secrets.toml`.

Job Hunter does not bypass login, CAPTCHA, anti-bot controls, or platform terms, and it does not auto-submit applications. Search coverage, full-description extraction, posting dates, and application availability depend on what public providers expose.

## Project Layout

| Path | Purpose |
|---|---|
| `src/app.py` | Three-page Streamlit interface, modes, progress, Stop, queue, and Apply |
| `src/job_hunter/search_runner.py` | Bounded background search, cancellation, and immutable events |
| `src/job_hunter/search.py` | Queries, provider parsing, descriptions, dates, availability, and safe URLs |
| `src/job_hunter/matching.py` | Gemini matching, structured output, cache, retry, and fallback |
| `src/job_hunter/session_workspace.py` | Session-only CV, jobs, application records, and active run identity |
| `src/job_hunter/job_identity.py` | Canonical links, provider IDs, fingerprints, and source consolidation |
| `src/job_hunter/queue.py` | Backward-compatible local SQLite queue for CLI use |
| `config/preferences.example.yaml` | Public criteria template |
| `docs/` | Product, architecture, scoring, pipeline, and release documentation |
| `tests/` | Unit, integration, cancellation, privacy, and Streamlit regression tests |

The Streamlit app uses session memory. The SQLite queue and older command-line helpers remain for local backward compatibility.
