# Application Pipeline

## v1.15 Flow

v1.17 retains this pipeline but allows OR city/country/regional Location selections. Geography is checked from posting evidence before scoring and with the shared matcher during fallback scoring. Regional discovery remains inside existing budgets; fifty candidates are collected before suitability is known, not selected as the best fifty. See [Geographic Scopes](LOCATION_SCOPES.md).

```text
Criteria only OR session CV + criteria
                |
                v
Title queries OR description queries
                |
                v
Up to 50 unique public job candidates
                |
                v
Description/date/availability enrichment
                |
                v
Hard skips, known-stale, and closed checks
                |
                v
Gemini match or labelled deterministic fallback
                |
                v
Session-only queue + primary-posting duplicate checks
                |
                v
Actionable / All / Already applied review
                |
                v
Safe external Apply page
                |
                v
User login, review, submit, and manual status record
```

## Search Rules

v1.18.0 optionally authenticates the owner with Google and restores encrypted account CV/settings/history before this flow. Save accepted results and manual posting/application edits on the Streamlit thread. Guest sessions remain session-only. Job Hunter login does not authenticate the user to a job platform; see [Account Setup](ACCOUNT_SETUP.md).

- Discovery treats title and description as separate signals rather than requiring both.
- Each run has at most 12 discovery requests, 50 unique candidates, 50 detail fetches, 50 scoring attempts, two job workers, and five minutes of new-work scheduling.
- Company career sites start unselected and show preset domains. User-entered company names use Gemini Google Search to verify official regional careers evidence; public HTTPS domains are user-provided sources. Five sites maximum, with SerpAPI required for discovery. Lookups are cached per region; verified company-owned hostnames are used in queries, not landing-page paths.
- Detail fetches use trusted provider, known ATS, or validated custom domains with bounded redirects and timeouts.
- Full descriptions come from `JobPosting.description` or recognized job-description containers. A snippet or unavailable state is retained honestly when full text cannot be read.
- Job-specific date fields beat generic update metadata. Unknown dates remain `Unknown`.
- Known stale jobs, closed jobs, and semantic hard-skip requirements are excluded before matching.
- Confident duplicate identities share one primary record; alternate sources are not stored/displayed. Generic Apply redirects are never vacancy identity.

## Progress And Stop

Background workers publish immutable events; only the Streamlit thread accepts completed matches into session state. Stop prevents new work after cancellation is observed. In-flight requests retain their bounded timeout and may settle briefly. Completed matches are kept, pending work is cancelled, and stale results from an older run ID are rejected. During a run, progress is measured against the 50-job ceiling. A normal terminal completion fills the bar and labels the actual checked count separately, so source exhaustion is not mistaken for ongoing work.

## Apply Rules

- Apply prefers a same-site or recognized ATS HTTPS URL and otherwise uses the safe original posting.
- Opening a link never changes status and is not described as submission.
- The user explicitly records Applied or Not applied.
- Applied records include a UTC time and the fixed evidence text: `Marked manually by the user; not verified with the job platform.`
- Login, CAPTCHA, questions, review, and submission remain on the destination platform.
