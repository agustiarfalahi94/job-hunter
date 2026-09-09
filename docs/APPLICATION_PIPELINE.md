# Application Pipeline

## v0.1 Flow

```text
Public search, pasted job, or CSV row
      |
      v
Posting-age filter
      |
      v
Closed-job availability check
      |
      v
Deterministic scoring
      |
      v
Local SQLite queue
      |
      v
shortlist / review / reject
      |
      v
Draft export with warnings
      |
      v
Dry-run application packet
      |
      v
Human review
      |
      v
Manual submit
      |
      v
Status update + daily progress
      |
      v
Application notes and draft
```

## Rules

- The system may recommend applying.
- The system may prepare a draft.
- The user decides whether to submit.
- The system must not invent experience to fit a job.
- The system must stop when a job asks for unsupported must-have experience.
- Duplicate jobs are detected before they can inflate the queue.
- Automated search defaults to jobs posted in the past month; the user may
  choose the past 24 hours, past week, or any time.
- Listings with visible closed, filled, unavailable, or expired wording are
  skipped before scoring and recorded in the search activity log.
- If a destination page blocks the availability check, the app keeps the job
  for human review and reports that its availability could not be confirmed.
- The progress bar is driven by real provider and job-processing events.
- Drafts are written locally under `exports/`, which is git-ignored.
- Application packets default to `Submit allowed: no`.
- The daily target is measured from local statuses, not assumed from generated
  drafts.

## Later Browser Layer

Browser automation should be designed as a separate phase. It must handle:

- Logged-in job-board sessions without storing credentials in Git.
- Rate limits and anti-abuse policies.
- Captchas and identity checks by handing control back to the user.
- Audit logs of what was filled and what was submitted.
- A dry-run mode before any real submission.

The first safe target is assisted form filling, not fully autonomous
submission.

## Production Testing Notes

In Streamlit Community Cloud, the current safe production path is:

1. Upload a PDF, DOCX, or legacy DOC CV file.
2. Confirm readable CV text signals appear.
3. Choose a Malaysia city, posting age, and selected platforms.
4. Run search and watch the live progress and activity log.
5. Use `Review Job queue` to open the ranked results.
6. Open application links manually and update status after human submission.

Optional API search requires `SERPAPI_API_KEY` in Streamlit secrets. Without it,
the app uses free public search fallbacks that can be blocked or incomplete.
