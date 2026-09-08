# Development Plan

## v0.1 - Foundation

- Create public-safe repository structure.
- Add factual candidate profile.
- Add preference template.
- Add deterministic scoring module.
- Add tests and local check script.

## v0.2 - Local Job Queue

- Added SQLite storage for jobs, scores, decisions, and application status.
- Added import from pasted job descriptions or CSV.
- Added duplicate detection.
- Added CLI commands for scoring and queue review.

## v0.3 - Draft Assistant

- Added draft generation that cites candidate-profile evidence.
- Added a guard that flags unsupported claims.
- Added local draft exports for cover letters and form answers.

## v0.4 - Browser-Assisted Applications

- Added dry-run application packets.
- Added user-confirmation defaults before submit.
- Added audit-friendly packet exports.
- Kept real browser automation, captchas, logins, and missing required-field
  handling for a later explicit integration phase.

## v1.0 - Daily Application Workflow

- Combined queue, scoring, drafts, packets, status updates, and daily progress
  into a repeatable local workflow.
- Added daily progress tracking toward the user's target.
- Kept quality controls explicit: dry-run packets and human submission remain
  the boundary until browser automation gets a separate integration design.

## v1.1 - User Criteria

- Added the user's job-title, primary-keyword, bonus-keyword, hard-skip, and
  daily target criteria.
- Added private local preference loading from `config/preferences.local.yaml`.
- Added mandatory remarks for weak matches and hard skips.
