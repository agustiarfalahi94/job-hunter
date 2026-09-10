# Application Pipeline

## v1.13 Flow

```text
Optional private CV
        |
        v
Editable titles + keywords + location + sources + date limit
        |
        v
Public or SerpAPI-backed search with live progress
        |
        v
Local-only, closed-job, and known-date freshness checks
        |
        v
Deterministic scoring + cross-platform deduplication
        |
        v
SQLite queue with posting date and application status
        |
        v
Official HTTPS Apply destination discovery
        |
        v
Open destination in a new browser tab
        |
        v
User login / CAPTCHA / required answers / review / submit
        |
        v
User marks the retained job as Applied
```

## Search Rules

- CV upload is optional. A saved CV shows a direct Continue to Search jobs action.
- Search and scoring use the same unified criteria values shown in the app.
- A run checks at most 50 results.
- The strong-match goal is a planning goal, not a stop condition.
- Search defaults to the past month; users may choose 24 hours, one week, or any time.
- A provider date filter is a first pass, not proof that every returned result is fresh.
- A known posting date older than the selected limit is skipped and explained in the activity log.
- Posting dates are checked in known provider fields, JSON-LD, page metadata,
  posting-time elements, embedded job data, and labeled visible text.
- A missing or unparseable posting date becomes `Unknown`, never `New`.
- An unavailable posting date is stated in the activity log.
- Local-only and Malaysian-only variants are excluded before active-queue insertion.
- Visible closed, filled, expired, or unavailable postings are skipped.
- If a trusted page blocks the availability check, the job remains available for human review and the log states that availability could not be confirmed.
- Enrichment follows at most three HTTPS redirects on supported job or
  applicant-tracking domains and rejects untrusted destinations.
- Duplicate title/company/location combinations produce one queue row across sources.

## Apply Rules

- The app may discover and open a same-site or recognized ATS HTTPS application destination.
- Unknown cross-site Apply links are ignored in favor of the original posting.
- When a separate Apply URL cannot be discovered, the original safe posting is used.
- Opening the link does not change an application status and is not described as submission.
- The user can explicitly mark a retained job as Applied or Not applied.
- Applied jobs remain visible in the queue.
- The user reviews and submits on the destination site.
- The app does not store credentials, cookies, CAPTCHA answers, or identity documents.
- The app does not automate LinkedIn activity because LinkedIn prohibits that use.

## Production Test

1. Open **Search jobs** without uploading a CV.
2. Confirm one Search criteria panel contains the title, keyword, location,
   source, date, goal, and maximum-results controls.
3. Run a small search and watch the progress bar and activity log.
4. Open **Job queue** with the button shown after the run.
5. Confirm the queue shows `Posted` and `Application status`.
6. Choose a job and click **Apply**.
7. Confirm the safest available HTTPS destination opens in a new tab.
8. Complete any login, CAPTCHA, required questions, review, and submission manually on that site.
9. Mark the job as applied and confirm it remains visible after rerun.

Optional API search requires `SERPAPI_API_KEY` in Streamlit secrets. Public fallback search can be incomplete or blocked.
