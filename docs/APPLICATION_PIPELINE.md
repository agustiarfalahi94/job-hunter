# Application Pipeline

## v0.1 Flow

```text
Job description
      |
      v
Deterministic scoring
      |
      v
shortlist / review / reject
      |
      v
Human review
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

## Later Browser Layer

Browser automation should be designed as a separate phase. It must handle:

- Logged-in job-board sessions without storing credentials in Git.
- Rate limits and anti-abuse policies.
- Captchas and identity checks by handing control back to the user.
- Audit logs of what was filled and what was submitted.
- A dry-run mode before any real submission.

The first safe target is assisted form filling, not fully autonomous
submission.
