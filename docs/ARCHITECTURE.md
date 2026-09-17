# Architecture

## Hosted Shape

```text
Streamlit session
  |-- SessionWorkspace: CV, jobs, application records
  |-- SearchRunController: run ID, cancellation, session score cache
  |
  +--> bounded discovery queries
         +--> two-worker detail enrichment
                +--> deterministic exclusions
                +--> Gemini / deterministic fallback
                +--> immutable events and CompletedMatch values
                         +--> Streamlit thread accepts active run only
```

The hosted app never creates `JobQueue` or `CVStore`. SQLite and disk-backed CV helpers remain only for backward-compatible local CLI use.

## Components

| Component | Responsibility |
|---|---|
| `src/app.py` | Session UI, matching modes, criteria, fragment polling, queue, and Apply |
| `session_workspace.py` | Session-only CV and queue lifecycle, active run ID, application evidence |
| `search_runner.py` | Coordinator, two-worker pool, ceilings, cancellation, events, completed matches |
| `search.py` | Query planning, provider parsers, safe page loading, dates, descriptions, availability |
| `matching.py` | Mode validation, Gemini adapter, structured output, retry, cache, fallback |
| `company_lookup.py` | Live grounded company discovery, official regional evidence verification, safe citation redirects |
| `job_identity.py` | Tracking cleanup, provider IDs, fingerprints, alternate source identity |
| `source_validation.py` | Friendly company-name resolution and public HTTPS custom-domain validation |
| `eligibility.py` | Shared normalized and conservative semantic hard-skip matching |
| `app_ui.py` | Queue filtering, row presentation, and application destinations |
| `queue.py` | Additive local SQLite compatibility path |

## Data Boundaries

Hosted private data lives inside one Streamlit session object. It is not persisted across session loss or app restart. Workers receive plain immutable request values, use a controller-owned session cache, and publish immutable events/results; they do not call Streamlit.

Web search selections live in a non-widget `search_settings` dictionary. Disposable underscore-prefixed widget keys copy changes into it using callbacks, and render from saved values. This prevents Streamlit's off-page widget cleanup from resetting criteria or queue hard-skip filtering. New sessions select nothing; CLI defaults remain CLI-only selections and web suggestion catalogs.

Company lookup sends only company/region, enables Google Search without JSON response mode to retain grounding metadata across model versions, and verifies cited public HTTPS official/regional pages plus an official careers link and readable regional careers destination. Automatic verification requires a brand-matching corporate domain and company-owned destination; shared ATS hosts and differently branded domains require explicit user input rather than an inferred tenant scope. Citation/link comparisons retain query parameters. A lookup has at most two generation attempts, six relevance-prioritized cited source resolutions, three distinct evidence-page fetches, and bounded redirects/timeouts. Cached success/failure entries are keyed by normalized name, requested region and configured model in session memory. Search suggestions and citations accompany successful lookups. Discovery uses a company-owned hostname, not a potentially unrelated landing-page path, with the selected location still required.

Public repository data includes source code, tests, generic criteria templates, allowlists, and contact-free documentation. CVs, extracted text, personal details, secrets, credentials, cookies, application records, and local databases are excluded.

## Network Boundaries

SerpAPI is preferred for dependable discovery and required for custom domains. Public fallback coverage may be incomplete. Page requests accept supported platform domains, known ATS domains, and only the custom domains that passed validation. Redirects remain HTTPS and trusted.

Gemini receives one mode-specific candidate payload and one job payload. Criteria mode cannot carry CV text. Errors are classified into sanitized user-facing fallback reasons; raw API errors and keys are not logged.

On model-not-found only, the adapter lists at most 100 provider model entries and selects a supported text-generation Flash model, preferring stable versions. Recovery consumes the existing second generation attempt, never an unbounded retry. Results carry the actual model name. Authentication/quota failures do not perform discovery.

## Cancellation Boundary

The controller schedules at most two jobs at a time and checks cancellation before every new discovery, fetch, and scoring stage. It cannot forcibly interrupt an already executing third-party request, so those calls have bounded timeouts and a short settlement window. A new run activates a new ID; late completed values from an older ID are ignored.

The progress fragment does not mutate the already-rendered page widget. It writes a pending page request and triggers a full app rerun; the request is consumed before the page control is created. Completed searches render as terminally full even when the source pool contains fewer than 50 unique candidates.

## Local SQLite Compatibility

Local queues use additive columns for posting date, Apply URL, application status, recorded time, and manual evidence. Existing rows are retained. This path does not participate in hosted multi-user state.
