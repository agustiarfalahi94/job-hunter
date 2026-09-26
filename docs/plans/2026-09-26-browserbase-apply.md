# Browserbase Inline Applications

Status: implementation approved in conversation, 2026-09-26.

## Scope

Keep Streamlit and add a user-operated Browserbase Live View to the existing
queue Apply section. Keep the external destination available. No automatic
login, CAPTCHA solving, form answering or submission. Opening a browser never
marks a job applied; the existing explicit manual record remains authoritative.

## Design

- Opt-in server configuration, disabled by default. Require the existing ready,
  authorized private account before creating or revealing a browser session.
- One remote session per app session, bounded to 15 minutes and identity expiry.
  Maintain the CDP connection in a dedicated worker, without paid keep-alive.
- Workers publish immutable snapshots only. No Streamlit calls, database writes,
  shared cache, browser-context persistence, or provider tokens in account snapshots.
- Disable recording, logging, CAPTCHA solving and proxies explicitly. Do not
  describe these flags as zero data retention by the provider.
- Validate the starting HTTPS destination and provider control URLs. Navigation
  uses the existing selected application destination, never arbitrary input.
- Handle actual file-chooser events. An explicit attachment command carries a
  short-lived request ID and file bytes to that exact input. Reject stale events,
  cross-owner requests, changed document/frame URLs, unsupported files and >5 MB.
- Keep a responsive live panel with starting, ready, upload, closing, failure and
  timeout states. Stop on sign-out/account switch. A short heartbeat lease bounds
  abandoned sessions; the provider timeout also covers process failure.
- Missing config, guest mode, expired postings and provider failures retain the
  external fallback. Do not silently start replacement sessions or spend quota
  during page rerenders.

## Implementation And Verification

1. Add configuration/provider and controller regressions, observe failures.
2. Implement bounded REST adapter, worker and attachment bridge.
3. Wire the signed-in queue UI and account cleanup, with Streamlit AppTest coverage.
4. Exercise a synthetic form locally without sending an application or personal data.
5. Review privacy/lifecycle/error paths; run all tests and dependency checks.
6. Update version, changelog, architecture, pipeline, README and setup instructions.
7. Commit on `codex/browserbase-inline-apply`, verify branch CI, merge/push main,
   verify main CI and the production shell. Live provider testing requires owner
   Browserbase credentials and completed account setup; report it separately.

## Verification Record

- 2026-09-27: 25 focused provider/controller/UI/browser tests pass locally.
- Full local suite: 386 tests, OK with one PostgreSQL integration class skipped
  because local database tools are absent. CI requires that database coverage.
- Dependency compatibility, Python compilation and whitespace checks pass.
- Synthetic Chrome forms verify explicit upload without submission, rejected
  private HTTP redirects and invalidation after same-document navigation.
- Desktop and phone-sized synthetic panels have no horizontal overflow; typed
  values survive fragment refreshes and Close removes the embedded view.
- Independent review findings about redirects, stale uploads and tab closure
  have regression coverage. CI gates are required before release.
- Real Browserbase creation, privacy flags, platform login and provider-side
  release remain unverified until owner credentials and account setup are available.

## References

- https://docs.browserbase.com/reference/api/create-a-session
- https://docs.browserbase.com/reference/api/session-live-urls
- https://docs.browserbase.com/reference/api/update-a-session
- https://docs.browserbase.com/platform/browser/observability/session-live-view
- https://docs.browserbase.com/platform/browser/files/uploads
