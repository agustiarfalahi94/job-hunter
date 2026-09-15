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
| `job_identity.py` | Tracking cleanup, provider IDs, fingerprints, alternate source identity |
| `source_validation.py` | Public HTTPS custom-domain validation |
| `eligibility.py` | Shared normalized hard-skip matching |
| `app_ui.py` | Queue filtering, row presentation, and application destinations |
| `queue.py` | Additive local SQLite compatibility path |

## Data Boundaries

Hosted private data lives inside one Streamlit session object. It is not persisted across session loss or app restart. Workers receive plain immutable request values, use a controller-owned session cache, and publish immutable events/results; they do not call Streamlit.

Public repository data includes source code, tests, generic criteria templates, allowlists, and contact-free documentation. CVs, extracted text, personal details, secrets, credentials, cookies, application records, and local databases are excluded.

## Network Boundaries

SerpAPI is preferred for dependable discovery and required for custom domains. Public fallback coverage may be incomplete. Page requests accept supported platform domains, known ATS domains, and only the custom domains that passed validation. Redirects remain HTTPS and trusted.

Gemini receives one mode-specific candidate payload and one job payload. Criteria mode cannot carry CV text. Errors are classified into sanitized user-facing fallback reasons; raw API errors and keys are not logged.

## Cancellation Boundary

The controller schedules at most two jobs at a time and checks cancellation before every new discovery, fetch, and scoring stage. It cannot forcibly interrupt an already executing third-party request, so those calls have bounded timeouts and a short settlement window. A new run activates a new ID; late completed values from an older ID are ignored.

## Local SQLite Compatibility

Local queues use additive columns for posting date, Apply URL, application status, recorded time, and manual evidence. Existing rows are retained. This path does not participate in hosted multi-user state.
