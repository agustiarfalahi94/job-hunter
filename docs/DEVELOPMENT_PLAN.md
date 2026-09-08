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

- Add prompt templates that cite candidate-profile evidence.
- Add a guard that flags unsupported claims.
- Add local draft exports for cover letters and form answers.

## v0.4 - Browser-Assisted Applications

- Add dry-run browser form filling.
- Add user confirmation before submit.
- Add audit logs.
- Add failure handling for captchas, logins, and missing required fields.

## v1.0 - Daily Application Workflow

- Combine queue, scoring, drafts, and assisted browser filling into a repeatable
  workflow.
- Track daily progress toward the user's target.
- Keep quality controls strong enough that volume does not turn into spam.
