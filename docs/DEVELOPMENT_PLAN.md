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

- Combine queue, scoring, drafts, and assisted browser filling into a repeatable
  workflow.
- Track daily progress toward the user's target.
- Keep quality controls strong enough that volume does not turn into spam.
