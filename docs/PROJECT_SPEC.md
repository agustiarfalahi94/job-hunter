# Project Spec

## Purpose

Job Hunter turns editable preferences and, optionally, a session CV into a ranked list of real public job postings. It reduces repetitive research without inventing experience, mislabelling freshness, sharing one visitor's data with another, or pretending an opened page was submitted.

## Supported Workflow

With optional v1.18.0 private accounts enabled, authenticate with the allowlisted Google account first; restore the encrypted saved workspace and save changes automatically. Guests remain session-only. Live account operation requires [owner setup and verification](ACCOUNT_SETUP.md), not just code deployment.

1. Choose Criteria-based or CV-based search.
2. Optionally save a PDF, DOCX, or best-effort DOC CV in the current session.
3. Edit title, description, bonus, semantic hard-skip, location, source, and freshness criteria.

New guest sessions/accounts have empty selected criteria and no selected location. Returning private accounts restore their saved settings. Criteria mode remains empty until edited. CV mode merges configured roles/hard skips and detected supported CV skills once per saved CV without overwriting existing selections; later manual edits remain authoritative. Location and sources always remain user choices. Guests start fresh after session loss, while configured private accounts restore settings and the applied-CV fingerprint after reboot. Date posted retains Past month protection.

A run requires Location, at least one selected platform, and Date posted. These three controls carry red asterisks. Title, required-description, bonus, hard-skip, company-site, and application-filter values are optional. When both discovery signal lists are empty, the planner generates one bounded broad signal pass for selected sources; direct LinkedIn may expand selected locations within the same ceiling. Empty platforms mean no source, not every source; company sites are optional additions rather than a substitute for a platform.

Location supports persistent OR selections across cities, countries, ASEAN, and an explicitly documented APAC country/economy preset. Country/region membership uses observed posting geography, not query hints. Regional searches remain bounded and are not exhaustive. Company-name verification has a five company/region pair ceiling in addition to five resolved sites. Fifty unique candidates is a pre-scoring ceiling, not the fifty most suitable jobs online. See [Geographic Scopes](LOCATION_SCOPES.md).

Company source presets display their domains and start unselected. Unknown company names use Gemini Google Search plus verification of official regional pages and an official careers link; explicit domains remain supported as user-provided sources. Failed or ungrounded resolution does not guess a domain.
4. Search title and description signals independently across selected sources.
5. Enrich up to 50 unique jobs with descriptions, dates, and safe Apply destinations.
6. Exclude restricted, known-stale, and visibly closed postings.
7. Score with Gemini or a visibly labelled deterministic fallback.
8. Review actionable, applied, or marked-expired jobs via their primary source; optionally correct posting dates/expiry with user provenance.
9. Apply externally and record status manually.

## Included

- Session-isolated hosted CV, queue, cache, and application records.
- Optional personal Google accounts with encrypted durable CV/settings/history, visible save failures and revision conflicts, confirmed reload/deletion, and sign-out cleanup.
- Criteria-only mode that never sends CV text.
- Profile & CV is hidden in criteria mode; changing modes retains the saved session CV.
- CV-based evidence matching with no unsupported claims.
- SerpAPI discovery plus a limited public fallback.
- LinkedIn, JobStreet, Indeed, Foundit, named company-page presets, and validated custom domains.
- Title OR description discovery, a fixed 50-unique-job target, bounded concurrency, progress, and Stop.
- Full/snippet/unavailable description provenance.
- Job-specific date provenance and user-selected age filtering.
- Conservative intent matching for local-only/Malaysian-only and mandatory-Mandarin requirements, including non-literal wording without treating optional language skills as mandatory.
- Conservative primary URL/provider/fingerprint identity matching, without alternate-source storage.
- Gemini structured scoring, session cache, bounded retry, sanitized errors, and fallback.
- Explicit manual application evidence and safe external Apply links.
- Backward-compatible local SQLite/CLI modules.

## Not Included

- Public multi-user profiles or automatic job-board history synchronization.
- Guaranteed access to every public job page or complete search coverage.
- Automatic third-party application-history lookup.
- Login automation, CAPTCHA bypass, credential storage, or auto-submit.
- Claims that an unknown posting date means a job is new.

## Success Criteria

- No hosted visitor can read another visitor's CV, jobs, cache, or application records.
- Criteria mode works without a CV and cannot include CV text in its model payload.
- CV mode is disabled until readable CV text is saved.
- Search shows current activity, running progress against the 50-job ceiling, a working Stop control, and an unmistakable full-bar terminal status even when fewer than 50 jobs are available.
- Removing a session CV clears both saved CV data and the visible uploader selection.
- Review Job queue performs a full page transition from the polling fragment.
- The Apply job dropdown is sorted by numeric ID; queue result ranking remains score-based.
- No more than the documented request, result, worker, scoring, or deadline ceilings are crossed.
- Full descriptions replace snippets when safely available; limitations remain visible otherwise.
- Known stale, closed, or hard-skipped roles never enter the active queue.
- Applied records remain available under Already applied with fixed manual evidence.
- A fresh clone passes tests and starts Streamlit without import errors.
- No private data or secrets enter Git.

## Reference Projects

Relevant structure and documentation patterns were studied from `kopi-kompas`, `random-recall`, `tiny-tapsters`, and `agustiar-data-pipeline`. Unrelated code was not copied.
