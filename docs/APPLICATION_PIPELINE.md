# Application Pipeline

## v1.14 Flow

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
Session-only queue + alternate source consolidation
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

- Discovery treats title and description as separate signals rather than requiring both.
- Each run has at most 12 discovery requests, 50 unique candidates, 50 detail fetches, 50 scoring attempts, two job workers, and five minutes of new-work scheduling.
- Custom domains are HTTPS-only, public, limited to five, and require SerpAPI.
- Detail fetches use trusted provider, known ATS, or validated custom domains with bounded redirects and timeouts.
- Full descriptions come from `JobPosting.description` or recognized job-description containers. A snippet or unavailable state is retained honestly when full text cannot be read.
- Job-specific date fields beat generic update metadata. Unknown dates remain `Unknown`.
- Known stale jobs, closed jobs, and hard-skip wording are excluded before matching.
- Confident duplicate identities share one queue record while retaining alternate source links. Generic Apply redirects are never vacancy identity.

## Progress And Stop

Background workers publish immutable events; only the Streamlit thread accepts completed matches into session state. Stop prevents new work after cancellation is observed. In-flight requests retain their bounded timeout and may settle briefly. Completed matches are kept, pending work is cancelled, and stale results from an older run ID are rejected.

## Apply Rules

- Apply prefers a same-site or recognized ATS HTTPS URL and otherwise uses the safe original posting.
- Opening a link never changes status and is not described as submission.
- The user explicitly records Applied or Not applied.
- Applied records include a UTC time and the fixed evidence text: `Marked manually by the user; not verified with the job platform.`
- Login, CAPTCHA, questions, review, and submission remain on the destination platform.
