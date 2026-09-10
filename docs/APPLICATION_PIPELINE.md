# Application Pipeline

## v1.11 Flow

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
Closed-job and known-date freshness checks
        |
        v
Deterministic scoring + cross-platform deduplication
        |
        v
SQLite queue with real posting date or Unknown
        |
        v
Official HTTPS Apply destination discovery
        |
        v
Open destination in a new browser tab
        |
        v
User login / CAPTCHA / required answers / review / submit
```

## Search Rules

- CV upload is optional. Search and scoring use the editable criteria shown in the app.
- A run checks at most 50 results.
- The strong-match goal is a planning goal, not a stop condition.
- Search defaults to the past month; users may choose 24 hours, one week, or any time.
- A provider date filter is a first pass, not proof that every returned result is fresh.
- A known posting date older than the selected limit is skipped and explained in the activity log.
- A missing or unparseable posting date becomes `Unknown`, never `New`.
- Visible closed, filled, expired, or unavailable postings are skipped.
- If a trusted page blocks the availability check, the job remains available for human review and the log states that availability could not be confirmed.
- Duplicate title/company/location combinations produce one queue row across sources.

## Apply Rules

- The app may discover and open a safe official HTTPS application destination.
- When a separate Apply URL cannot be discovered, the original safe posting is used.
- Opening the link does not change an application status and is not described as submission.
- The user reviews and submits on the destination site.
- The app does not store credentials, cookies, CAPTCHA answers, or identity documents.
- The app does not automate LinkedIn activity because LinkedIn prohibits that use.

## Production Test

1. Open **Search jobs** without uploading a CV.
2. Confirm the title, keyword, location, source, date, goal, and cap controls are editable.
3. Run a small search and watch the progress bar and activity log.
4. Open **Job queue** with the button shown after the run.
5. Confirm the queue shows `Posted` and does not show application status.
6. Choose a job and click **Apply**.
7. Confirm the safest available HTTPS destination opens in a new tab.
8. Complete any login, CAPTCHA, required questions, review, and submission manually on that site.

Optional API search requires `SERPAPI_API_KEY` in Streamlit secrets. Public fallback search can be incomplete or blocked.
