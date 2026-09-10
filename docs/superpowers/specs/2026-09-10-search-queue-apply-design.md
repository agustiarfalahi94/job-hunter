# Search, Queue, and Apply Design

## Goal

Make Job Hunter understandable and useful without requiring a CV: users can search by title, description keywords, location, platforms, and posting age; review ranked results with a real posting date; and continue to the safest official application destination.

## User Journey

1. Optionally upload a PDF or Word CV on **Profile & CV**.
2. Open **Search jobs** and edit titles, description keywords, scoring bonuses, hard skips, location, platforms, posting age, and the session cap.
3. Run the search while viewing live progress and activity.
4. Open **Job queue** to compare score, match evidence, remarks, and posting date.
5. Choose a job and click **Apply**. Job Hunter uses a discovered official apply URL when available, otherwise it opens the original job posting in a new tab.

## Simplified Navigation

The app has one workflow with three pages:

- **Profile & CV**: optional profile enhancement and private CV storage.
- **Search jobs**: the main search flow; CV upload is not required.
- **Job queue**: ranked results and application links.

The separate manual-scoring workflow, Add job page, Import CSV page, application status controls, draft export, and packet export are removed from the Streamlit interface. Existing database columns and old backend helpers may remain temporarily for compatibility with existing local data, but they are not part of the active product workflow.

## Posting Date

`Status = new` was an internal application-state value and did not describe freshness. It is removed from the queue interface.

Search adapters capture a posting date from, in priority order:

1. structured `datePosted` data on the job page;
2. platform search-card date metadata;
3. search-result date metadata or a recognizable relative date.

Dates are normalized to ISO `YYYY-MM-DD` where possible. Unknown dates are displayed as **Unknown**, never as **New**. A result with a known date older than the selected posting-age limit is skipped even if the search provider returned it.

## Apply Behavior

The hosted Streamlit app cannot take over the visitor's existing logged-in browser session, bypass CAPTCHA, or safely submit arbitrary third-party forms. Some platforms, including LinkedIn, also prohibit third-party automation.

Job Hunter therefore performs the supported portion of the workflow:

- discover a safe HTTPS application link on readable job pages;
- prefer that link over an aggregator result URL;
- otherwise fall back to the original safe HTTPS posting;
- open the selected destination in a new browser tab;
- require the user to review and submit on the destination site.

The interface must not report an application as submitted merely because a link was opened.

## Data Changes

Add nullable `posted_date` and `apply_url` fields to queue inputs and records. SQLite migration is additive so existing user data is retained.

## Safety

- Only HTTPS application destinations are exposed as Apply links.
- CV files remain under the ignored private data directory.
- No platform credentials, cookies, CAPTCHA responses, or application answers are stored by the public app.
- Search availability checks remain limited to trusted source domains.

## Verification

- Unit tests cover posting-date extraction and normalization, recency enforcement, safe apply-link discovery, database migration, UI row output, and keyword-only search.
- Streamlit AppTest covers navigation and queue actions.
- A local browser smoke test verifies the production-facing layout and Apply link behavior.
- The release updates README, changelog, architecture, product specification, application flow, development plan, and package version.
