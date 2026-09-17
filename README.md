# Job Hunter

Job Hunter v1.17.1 is a Streamlit app that discovers, scores, and organizes data jobs. The live app is [jobs-hunter.streamlit.app](https://jobs-hunter.streamlit.app/).

## What It Does

- Searches LinkedIn, JobStreet, Indeed, Foundit, and up to five selected or user-entered company career sites.
- Discovers by job title **or** description keyword, so an unfamiliar title can still be found.
- Targets up to 50 unique jobs per run with at most 12 discovery requests, 50 detail-page fetches, 50 scoring calls, two job workers, and five minutes of new-work scheduling.
- Reads full descriptions from structured job data or recognized page sections; otherwise labels scoring as snippet-based or unavailable.
- Verifies job-specific posting dates where possible, labels unknown dates honestly, and skips known stale or closed jobs.
- Excludes semantic variants of local-only, Malaysian-only, and mandatory-Mandarin requirements before scoring.
- Uses Gemini for evidence-based matching when configured and visibly labels deterministic fallback scores when Gemini is unavailable.
- Skips confident duplicates while keeping one primary posting per vacancy, without alternate-source storage or display.
- Supports platform quick-apply filters and user corrections for posting date/expiry.
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
2. Select or type the title, description, bonus, and hard-skip terms. New sessions start empty: suggestions are not preselected, and saving a CV does not populate criteria. Edited parameters survive page/mode changes and completed searches in this session. Hard skips use normalized intent matching for supported eligibility and language requirements, so wording does not need to be identical.
3. Select one or more areas in **Location**, for example `Kuala Lumpur` OR `Jakarta`, or `Europe` OR `APAC`. Choose `Malaysia` for country-wide search, `ASEAN` for its members, or `Global` for no geographic restriction. Global overrides other areas. Selections persist just like keywords.
4. Select job platforms and a posting-age limit. Optional **Platform application filters** restrict only their named platform: LinkedIn Easy Apply, Indeed Apply, or Foundit Quick Apply. Other platforms are unaffected. These strict filters require posting-level button/link evidence; inaccessible or unverified quick-apply jobs are skipped with a log reason. They do not submit applications. Leave them empty for widest discovery coverage.
5. In **Company career sites**, select a preset (its domain is shown), enter a company name such as `Deloitte`, or enter a public HTTPS careers domain. Up to five sites are allowed; company-site job searches require SerpAPI. New company names additionally require Gemini and a selected location. The app searches the web, checks official careers/regional evidence, and shows the confirmed destination plus source links. If verification fails, it explains why rather than guessing; use **Retry company lookup** or enter the known careers domain.
6. Click **Run search and score jobs**.
7. Follow the progress bar and activity log. Fifty is the maximum, not a required result count; a completed search fills the bar even when sources return fewer jobs and reports the number actually checked.
8. Use **Stop search** when needed, then click **Review Job queue**.

Stop prevents new discovery, page-fetch, and scoring work after cancellation is observed. An in-flight network or Gemini request has its own timeout and may take a short time to settle; completed results are kept.

**Matching rules:** Text matches ignore capitalization: `azure`, `Azure`, and `AZURE` are equivalent. Values within a title/keyword list are alternatives, not an AND checklist. Discovery uses title signals OR description signals. Bonus terms such as Agile OR Scrum can improve scoring when present in a title or description; they do not generate discovery queries or exclude jobs if absent, and more matches can earn more bonus points. Any matched hard-skip term excludes the job. The selected location, sources, and posting-date limit still constrain the search; they are not OR alternatives to keywords.

All four fields share session persistence, case-insensitive matching, and OR alternatives within their own list:

| Field | Meaning of OR |
| --- | --- |
| Target job titles | Any listed title can supply a role/discovery signal. |
| Required description keywords | Any listed primary keyword can supply a primary/discovery signal; missing all reduces suitability, not an automatic hard skip. |
| Bonus keywords | Any listed bonus can add points; bonuses are optional and do not drive discovery. |
| Hard skip keywords | Any listed restriction match excludes the job; it overrides positive matches. |

**Available suggestions:** These are a static catalog from the project's original search preferences, not terms extracted from a visitor's CV. They intentionally remain available but unselected. Every title/keyword field accepts custom values outside the catalog, and those custom selections persist across page changes just like suggested values. Saving, replacing, or removing a CV does not rewrite the catalog or automatically select criteria.

**Persistence:** Parameters are session-only, just like CVs and the queue. Page navigation and completed searches do not reset them. App reboot, browser-session reset, or session expiry starts fresh, with no selected criteria. Date posted defaults to Past month and the session job cap remains 50.

**Company presets and region:** Accenture, HCLTech, Razer, Prudential Malaysia, and Accord Innovations are hand-maintained examples originally requested by the project owner; they are not automatic CV recommendations or live-verified lookup results. New names use [Gemini Google Search grounding](https://ai.google.dev/gemini-api/docs/generate-content/google-search), not model memory. Malaysian city selections look up careers serving Malaysia; other typed locations require evidence for that location. Verification may fail on blocked/JavaScript-only sites or ambiguous company names. Explicit domains remain user-provided sources, not independently verified regional destinations. Successful and failed lookups are cached per session, so page changes do not repeatedly call Gemini. Grounded lookups have separate Google Search usage/quota and may incur charges under your Google plan; they do not consume SerpAPI discovery requests.

Automatic lookup conservatively requires a brand-matching corporate domain, a company-owned careers host, live citations, an official careers link, and readable regional evidence on both referring and destination pages. Shared ATS hosts, differently branded corporate domains, and inaccessible pages require an explicit domain instead. These evidence checks reduce mistakes; they are not a legal ownership certification. Discovery searches the verified company-owned hostname rather than a landing-page path, and still applies the selected job location.

Selected areas are OR alternatives, but geography still constrains title/description discovery. Country selections cover cities in that country; region presets expand into country alternatives inside existing search requests. Country names/codes and supported city names are matched case-insensitively using the same geographic checks before scoring and in deterministic scoring. Readable JobPosting addresses or platform location labels supply observed location; known mismatches are skipped. Missing or insufficient geography remains unverified with remarks, never invented from the search query.

**Regional coverage:** ASEAN includes its eleven members, including Timor-Leste ([ASEAN admission announcement](https://asean.org/forging-a-new-era-timor-leste-admitted-into-asean/)). APAC has no universal hiring-market definition; this app uses the explicitly listed country/economy preset in [Geographic Scopes](docs/LOCATION_SCOPES.md). Country suggestions come from the ISO dataset packaged by [pycountry](https://github.com/pycountry/pycountry); Malaysian city suggestions still use CountriesNow with a fallback. JobStreet searches its regional subdomains; Foundit includes Malaysia, Indonesia, Singapore, and India. Other countries may have incomplete platform coverage. Public LinkedIn fallback uses separate country/city requests within the twelve-request ceiling, so broad-region coverage is partial, not an exhaustive scan. SerpAPI uses grouped country alternatives without increasing the request ceiling.

**Why five company sites?** It is an app safeguard for the shared twelve-request discovery budget, runtime, and API usage, not a GitHub/Streamlit/platform restriction. New company-name verification also permits at most five company/region pairs per selection: Kuala Lumpur and Malaysia share one region, while Jakarta adds Indonesia. ASEAN/APAC each use one regional verification, not a separate Gemini call for every member country. Each verified region is cached and shown; an unverified region blocks search rather than being silently ignored. Use known careers domains or narrow locations when this budget is exceeded. Resolved domains are deduplicated and capped at five.

**What fifty means:** The app collects up to fifty unique candidates in discovery order, then checks, filters, scores, and ranks them. It is not the fifty most suitable jobs across the internet and does not guarantee fifty strong matches. Skipped jobs still consume checking capacity; the queue contains the retained scored results and ranks those by suitability. Broadening locations does not increase this ceiling or allocate fifty jobs per area.

If company lookup reports unavailable Gemini quota, check the API key's Google AI Studio project and its model/Google Search grounding limits. A working scoring connection does not establish available grounding quota. Wait for the applicable reset or use a known careers domain; the app cannot verify company names without an available grounded request and never guesses a replacement domain.

### 4. Review And Apply

The queue defaults to **Actionable** jobs, excluding already-applied and marked-expired entries. Use **All** or **Already applied** to change the view, then filter by match decision. Rows show scoring engine/model, description/date evidence, expiry and its evidence, quick-apply evidence, reasons, and remarks, with one primary source.

Select a job, expand **Posting date & expiry**, enter a date you can actually verify and choose Unknown / Not expired / Expired, then click **Save posting details**. Corrections persist in this session and are labelled user-entered, not platform-verified; they do not rescore jobs. Clear the date for Unknown; future dates are rejected. Expired jobs remain in All and Apply is disabled; choose All to correct/reopen one. Source `JobPosting.validThrough` expiry is checked before scoring. A stale posting date does not prove expiry, and Unknown is not expired.

Location extraction tries selected-vacancy structured addresses, recognized platform header elements, public card labels, and recognized Indeed result-title location slots, never description mentions or your query city. Some platforms block server requests even when browser access works. If every visible result lacks verified location, Location is hidden; otherwise it stays and unknown rows say Unknown.

### Gemini Model And Quota

The default is `gemini-3.8-flash`, unless Streamlit secrets `GEMINI_MODEL` overrides it ([Google model catalog](https://ai.google.dev/gemini-api/docs/models)). Earlier releases inherited a 2.5 default; it was not a requirement of this app or discovery provider. Search jobs shows the configured model; Check Gemini connection shows the actual model, and queue rows record their scoring model. Unavailable-model recovery may use another supported Flash model; runtime model/key availability still applies.

Discovery happens before Gemini scoring. The activity log shows each API query's web-result count, accepted job-link count, and excluded link count. Zero discoveries show a warning rather than claiming scored jobs exist. Authentication, allowance/rate-limit, malformed-response, and failed-search errors have sanitized messages without API keys or raw provider responses. If every discovery request fails, the run is Failed, not an empty success. Some indexed pages are search/category pages rather than individual vacancies, so web-result counts can exceed accepted links.

AI Studio Usage charts show activity and error types, not remaining quota. Success rate 100% is not 100% quota remaining. 429 means a rate/resource limit was exceeded; 404 is an unavailable model/resource, and 503 is service unavailability. Check Rate Limit for your selected project/model: requests/minute, input tokens/minute, daily requests, and grounding capacity differ. Limits apply per project, not per key ([Google rate-limit documentation](https://ai.google.dev/gemini-api/docs/rate-limits)). A working scoring call does not establish grounding capacity.

### Test Your Criteria

For the [Indeed reference posting](https://malaysia.indeed.com/viewjob?jk=9e3ad6434cb74fde), try Criteria-based search; title `Data Analyst`; required `Power BI`; bonus `SQL`; location `Kuala Lumpur`; platform `Indeed`; empty hard skips, company sites, and application filters; Date posted `Any time` because the readable reference page has no posting date. To test a hard skip, keep those values but add `Power BI` to Hard skip keywords: matching discoveries must be skipped irrespective of capitalization. Use separate fresh sessions to avoid old queued results confusing independent runs.

See [Positive And Negative Test Cases](docs/TEST_CASES.md) for expected outcomes, location/suitability negatives, and access/indexing limitations. Search cannot guarantee discovery of a specific URL within fifty candidates. Never invent a missing posting date.

Select a job and click **Apply** to open the safest official destination. Login, CAPTCHA, required questions, review, and submission stay on that platform. Opening Apply never changes application status. After submitting, explicitly select **I have applied to this job**; the record is labelled as manually recorded, not platform-verified.

## API Setup

Create `.streamlit/secrets.toml` locally or add these values in Streamlit Community Cloud secrets:

```toml
SERPAPI_API_KEY = "your-serpapi-key"
GEMINI_API_KEY = "your-gemini-api-key"
GEMINI_MODEL = "gemini-3.8-flash"
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
| `src/job_hunter/company_lookup.py` | Grounded company-name lookup, official regional careers evidence, safe citation resolution |
| `src/job_hunter/session_workspace.py` | Session-only CV, jobs, application records, and active run identity |
| `src/job_hunter/job_identity.py` | Canonical links, provider IDs, fingerprints, and source consolidation |
| `src/job_hunter/queue.py` | Backward-compatible local SQLite queue for CLI use |
| `config/preferences.example.yaml` | Public criteria template |
| `docs/` | Product, architecture, scoring, pipeline, and release documentation |
| `tests/` | Unit, integration, cancellation, privacy, and Streamlit regression tests |

The Streamlit app uses session memory. The SQLite queue and older command-line helpers remain for local backward compatibility.
