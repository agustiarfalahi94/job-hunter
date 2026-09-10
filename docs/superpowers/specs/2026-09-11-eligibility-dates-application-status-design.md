# Eligibility, Posting Dates, and Application Status Design

## Goal

Make the Job Hunter queue trustworthy by excluding restricted jobs, recovering posting dates that are visible on supported job pages, and letting users record whether they have already applied without removing those jobs from their results.

## Scope

This release changes the existing automated search and queue workflow. It does not add account login automation, CAPTCHA handling, form submission, or a headless browser to Streamlit Cloud.

## Eligibility Restrictions

The current hard-skip matcher compares literal substrings. A configured value such as `locals/malaysian only` therefore does not match a title such as `Senior Business Intelligence Specialist (Local Applicant Only)`.

The replacement matcher will:

1. compare case-insensitively;
2. normalize punctuation, slashes, repeated whitespace, and parentheses;
3. recognize common local-only variants, including `local applicant only`, `local applicants only`, `local candidates only`, `locals only`, `Malaysian only`, and `Malaysians only`;
4. inspect the title, search snippet, fetched job description, and location before the result is accepted;
5. preserve the user's editable hard-skip phrases and report the phrase that caused an exclusion.

New restricted results will not be inserted into the active queue. Existing restricted rows will be excluded from the active queue when current criteria are applied, but retained in SQLite so the release does not silently delete user data.

## Posting-Date Enrichment

Date discovery will use the following ordered sources:

1. structured date fields returned by the search provider;
2. JSON-LD `datePosted` values on the job page;
3. job-specific metadata and `<time datetime>` elements;
4. embedded structured job data;
5. visible posting-age text tied to posting labels, including hours, days, weeks, months, and years.

Relative values such as `2 months ago` and `1 year ago` will be normalized to ISO `YYYY-MM-DD` dates using the search date. Hours and days use their literal duration, weeks use seven days, months use 30 days, and years use 365 days so recency filtering remains deterministic. The parser will avoid treating unrelated page text as the posting date by requiring a recognized job-date element, field, or nearby posting label.

If a page reveals its date only after client-side execution, login, or a CAPTCHA, the hosted app may still report **Unknown**. The activity log will distinguish this source limitation from a parsing failure. Known dates older than the user's posting-age limit remain excluded.

Page enrichment may follow at most three HTTPS redirects when every destination remains on a supported job platform or recognized applicant-tracking domain. Arbitrary redirect destinations are rejected.

## Application Status

The queue will gain a dedicated `application_status` field with two values:

- `Not applied`, the default for new and migrated records;
- `Applied`, explicitly selected by the user.

The queue table will include an **Application status** column. The selected-job panel will provide a checkbox to mark or unmark a job as applied. Applied jobs remain in the queue and retain their score, decision, posting date, and Apply link.

Opening an Apply link does not change the status automatically because Job Hunter cannot verify that the user completed submission on the third-party page. Automatic account-history lookup is out of scope because the supported sources do not provide one consistent, authorized application-history interface to this Streamlit app.

## Storage And Compatibility

SQLite migration will add a non-null `application_status` column with a `not_applied` default. Existing records and the legacy internal `status` column remain intact. New queue methods will validate application-status values and update only the selected record.

The public repository will continue to exclude CV files, secrets, cookies, and private queue databases.

## User Flow

1. The user runs an automated search.
2. Job Hunter enriches each candidate with readable page metadata.
3. Restricted and stale jobs are excluded before active-queue insertion.
4. Accepted jobs are scored and shown in the queue with posting date and application status.
5. The user opens a selected job's Apply link, completes the external application, then marks the queue record as applied.

## Error Handling

- A failed page fetch will preserve provider metadata and log that page enrichment was unavailable.
- An unrecognized date remains **Unknown** instead of being guessed.
- Invalid application-status updates will be rejected without changing the record.
- Database migration is additive and idempotent.
- Search continues when one result cannot be enriched.

## Testing

Automated coverage will include:

- local-only variants in titles and descriptions;
- punctuation and case normalization;
- restricted-result exclusion before queue insertion;
- relative years and months;
- structured, metadata, time-element, and visible-text date extraction;
- stale-date filtering after page enrichment;
- SQLite migration for old and new databases;
- application-status validation and persistence;
- queue table output and selected-job checkbox behavior;
- regression coverage for CV-optional search, scoring, and Apply links.

Verification will include the complete test suite, Python compilation, dependency checks, Streamlit AppTest, a local browser smoke test, GitHub Actions, and production verification after deployment.

## Release And Documentation

The implementation will be released as version `1.13.0` from branch `codex/eligibility-dates-applied-v1-13`. It will update the README, changelog, scoring documentation, application pipeline, architecture, project specification, development plan, package version, and relevant examples.
