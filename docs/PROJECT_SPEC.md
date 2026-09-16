# Project Spec

## Purpose

Job Hunter turns editable preferences and, optionally, a session CV into a ranked list of real public job postings. It reduces repetitive research without inventing experience, mislabelling freshness, sharing one visitor's data with another, or pretending an opened page was submitted.

## Supported Workflow

1. Choose Criteria-based or CV-based search.
2. Optionally save a PDF, DOCX, or best-effort DOC CV in the current session.
3. Edit title, description, bonus, semantic hard-skip, location, source, and freshness criteria.
4. Search title and description signals independently across selected sources.
5. Enrich up to 50 unique jobs with descriptions, dates, and safe Apply destinations.
6. Exclude restricted, known-stale, and visibly closed postings.
7. Score with Gemini or a visibly labelled deterministic fallback.
8. Review actionable or already-applied jobs and alternate source links.
9. Apply externally and record status manually.

## Included

- Session-isolated hosted CV, queue, cache, and application records.
- Criteria-only mode that never sends CV text.
- Profile & CV is hidden in criteria mode; changing modes retains the saved session CV.
- CV-based evidence matching with no unsupported claims.
- SerpAPI discovery plus a limited public fallback.
- LinkedIn, JobStreet, Indeed, Foundit, named company-page presets, and validated custom domains.
- Title OR description discovery, a fixed 50-unique-job target, bounded concurrency, progress, and Stop.
- Full/snippet/unavailable description provenance.
- Job-specific date provenance and user-selected age filtering.
- Conservative intent matching for local-only/Malaysian-only and mandatory-Mandarin requirements, including non-literal wording without treating optional language skills as mandatory.
- Conservative identity matching and alternate source preservation.
- Gemini structured scoring, session cache, bounded retry, sanitized errors, and fallback.
- Explicit manual application evidence and safe external Apply links.
- Backward-compatible local SQLite/CLI modules.

## Not Included

- Durable hosted user accounts or cross-session history.
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
