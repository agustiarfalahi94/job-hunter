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

## Optional Private Accounts

v1.18.0 gates the workspace behind native Google OIDC when `accounts.enabled` is true. Verified email gates access; canonical Google issuer + stable subject hashes to the owner ID. Invalid setup, signed-out/denied/expired identities and failed initial loads cannot reach the workspace. Account mode is off by default.

The account adapter restores a versioned snapshot before widget creation, and saves only changed snapshots after settings callbacks, CV changes, posting/application edits and accepted background results. Snapshot contents are Fernet-encrypted CV bytes/text, settings/mode and JobRecords. Controllers, caches, API keys and provider tokens stay session-local. Native OIDC identity is not Supabase `auth.uid()`; server-only Supabase secret-key RPCs operate with service-role privileges, with app owner checks plus revoked anon/authenticated table/function access.

Database writes use atomic compare-and-swap revisions. Conflicting tabs stop saving until explicit reload; failed loads never permit writes/clear. Deletion increments revision and nulls the payload rather than removing its tombstone. Logout/account changes cancel controllers and clear all session/widget state. Account save errors remain visible; retries are explicit after failure. Backend requests have bounded timeouts and never follow redirects. See [Account Setup](ACCOUNT_SETUP.md) for trust boundaries, limits, encryption-key recovery and real deployment checks.

## Components

| Component | Responsibility |
|---|---|
| `src/app.py` | Session UI, matching modes, criteria, fragment polling, queue, and Apply |
| `session_workspace.py` | Session-only CV and queue lifecycle, active run ID, application evidence |
| `account_config.py` / `account_ui.py` | Validated native identity, personal access gate, restore/save controls and sign-out cleanup |
| `account_snapshot.py` / `account_session.py` | Validated private snapshots, change detection, failure/conflict lifecycle |
| `account_store.py` / `config/supabase_accounts.sql` | Encrypted server-only owner RPCs, revisions and deletion tombstones |
| `search_runner.py` | Coordinator, two-worker pool, ceilings, cancellation, events, completed matches |
| `search.py` | Query planning, provider parsers, safe page loading, dates, descriptions, availability |
| `matching.py` | Mode validation, Gemini adapter, structured output, retry, cache, fallback |
| `company_lookup.py` | Live grounded company discovery, official regional evidence verification, safe citation redirects |
| `job_identity.py` | Tracking cleanup, provider IDs, primary URL/fingerprint identity |
| `source_validation.py` | Friendly company-name resolution and public HTTPS custom-domain validation |
| `eligibility.py` | Shared normalized and conservative semantic hard-skip matching |
| `app_ui.py` | Queue filtering, row presentation, and application destinations |
| `queue.py` | Additive local SQLite compatibility path |

## Data Boundaries

Hosted live data lives inside one Streamlit session object. Guests do not persist across session loss or app restart; configured private accounts additionally save encrypted snapshots in Supabase. Workers receive plain immutable request values, use a controller-owned session cache, and publish immutable events/results; they do not call Streamlit or save account data.

Web search selections live in a non-widget `search_settings` dictionary. Disposable underscore-prefixed widget keys copy changes into it using callbacks, and render from saved values. This prevents Streamlit's off-page widget cleanup from resetting criteria or queue hard-skip filtering. New sessions select nothing; CLI defaults remain CLI-only selections and web suggestion catalogs.

Company lookup sends only company/region, enables Google Search without JSON response mode to retain grounding metadata across model versions, and verifies cited public HTTPS official/regional pages plus an official careers link and readable regional careers destination. Automatic verification requires a brand-matching corporate domain and company-owned destination; shared ATS hosts and differently branded domains require explicit user input rather than an inferred tenant scope. Citation/link comparisons retain query parameters. A lookup has at most two generation attempts, six relevance-prioritized cited source resolutions, three distinct evidence-page fetches, and bounded redirects/timeouts. Cached success/failure entries are keyed by normalized name, requested region and configured model in session memory. Search suggestions and citations accompany successful lookups. Discovery uses a company-owned hostname, not a potentially unrelated landing-page path, with the selected location still required.

Public repository data includes source code, tests, generic criteria templates, allowlists, and contact-free documentation. CVs, extracted text, personal details, secrets, credentials, cookies, application records, and local databases are excluded.

## Network Boundaries

SerpAPI is preferred for dependable discovery and required for custom domains. Public fallback coverage may be incomplete. Page requests accept supported platform domains, known ATS domains, and only the custom domains that passed validation. Redirects remain HTTPS and trusted.

General search candidates have no observed location merely because the query includes an area. Structured records are associated with the selected vacancy URL; unrelated vacancies are not merged, and multiple ambiguous records remain unverified. JobPosting addresses override platform card evidence. Shared geographic matching uses pycountry ISO aliases and explicit regional membership for OR city/country/ASEAN/APAC selections; confirmed mismatches skip before scoring, and missing or country-only city evidence remains empty with a remark. Multiple addresses are accepted when at least one verifies a selected scope. See [Geographic Scopes](LOCATION_SCOPES.md).

Multi-location company lookup deduplicates selected cities into verification regions, caches each region independently, and resolves all verified regional hosts through source validation. Source validation checks the five company/region pair ceiling before provider calls and the five resolved-site ceiling before search. Broad presets use one regional grounded verification rather than one call per member country. Web queries group source, keyword, and location OR clauses; regional alternatives do not multiply SerpAPI requests. Direct LinkedIn fallback expands country requests and interleaves other platform queries inside the twelve-request ceiling.

Gemini receives one mode-specific candidate payload and one job payload. Criteria mode cannot carry CV text. Errors are classified into sanitized user-facing fallback reasons; raw API errors and keys are not logged.

On model-not-found only, the adapter lists at most 100 provider model entries and selects a supported text-generation Flash model, preferring stable versions. Recovery consumes the existing second generation attempt, never an unbounded retry. Results carry the actual model name. Authentication/quota failures do not perform discovery.

## Cancellation Boundary

The controller schedules at most two jobs at a time and checks cancellation before every new discovery, fetch, and scoring stage. It cannot forcibly interrupt an already executing third-party request, so those calls have bounded timeouts and a short settlement window. A new run activates a new ID; late completed values from an older ID are ignored.

The progress fragment does not mutate the already-rendered page widget. It writes a pending page request and triggers a full app rerun; the request is consumed before the page control is created. Completed searches render as terminally full even when the source pool contains fewer than 50 unique candidates.

## Posting Evidence And Application Filters

Europe/ASEAN/APAC use explicit country/economy presets; Global removes location constraints and location-score bonuses. Explicit countries override city inference, and structured locality roles are retained for tri-state city checks. Associated records missing addresses can use recognized header fallback; ambiguous/unrelated structured records cannot.

Optional quick-apply filters are own-platform and strict. LinkedIn discovery includes f_AL and web signals; Indeed/Foundit use their method signals. Actual eligibility requires observed button/link evidence, with conflicting vacancy IDs rejected and description/related-job nodes excluded. Missing evidence skips with a reason. These are discovery filters, not login or submission automation.

Hosted JobInput/JobRecord carry quick_apply, availability, and availability_evidence. Source validThrough dates determine known expiry before scoring; unknown expiry is not inferred from posting age. User edits to date/expiry are explicitly unverified; they also persist across sessions for configured private accounts. Unchanged source evidence is preserved. Duplicate date/provenance merges are atomic. Expired jobs are retained in All with Apply disabled. Location columns are omitted only when all visible records lack observed location. Alternate source fields/storage/runner alias publication are removed; primary URL/provider/fingerprint checks remain.

## Local SQLite Compatibility

Local queues use additive columns for posting date, Apply URL, application status, recorded time, and manual evidence. Existing rows are retained. This path does not participate in hosted multi-user state.
