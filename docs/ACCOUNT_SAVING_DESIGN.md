# Account Saving Design

Status: proposed next release. No Google login, backend migration, or durable account saving is implemented in v1.17.2. Existing hosted sessions remain session-only. This document does not configure or transmit any private data.

## Intended Experience

Sign in to Job Hunter with Google, restore the saved CV and search settings, search and review jobs, then mark submitted applications in the app. Save CV replacement/removal, criteria changes, queue results and application records to the signed-in account. Restore them after app reboot or a new browser session. Criteria mode still hides Profile & CV without deleting it and must never send stored CV text to scoring.

Personal mode should allow only a configured, verified Google account. Job Hunter sign-in is separate from signing in to LinkedIn, Indeed or other job boards. Applied status remains a manual record with its timestamp and provenance, not an assertion that a platform independently confirmed submission.

## Recommended Approach

- Use Streamlit's native Google OIDC login, rather than collecting passwords or writing a custom login protocol.
- Keep `SessionWorkspace` as the live UI/background-event boundary. Add an account-storage adapter to load and save only after authentication and access checks.
- Use durable private Supabase storage rather than hosted local files or the CLI SQLite database. Restrict all account data and CV access. A public GitHub repository must never contain records, CVs or credentials.
- Derive ownership from the validated Google issuer and stable subject claim, never a widget, URL parameter, or unverified email. A verified-email allowlist can gate personal access but must not replace stable ownership.
- Native Streamlit identity is not a Supabase Auth session. Do not assume Google's subject is Supabase `auth.uid()`. If using server-side database credentials, deny browser/anonymous table and bucket access, keep credentials server-only, and enforce owner-scoped operations in the adapter. Supabase service credentials bypass RLS, so RLS alone does not isolate this server path.
- Detect conflicting writes from multiple tabs instead of overwriting newer account data. Never overwrite an account after a failed load. Save failures must remain visible and must not be labelled Saved.
- Keep caches, network clients, controllers and running work session-local. Never persist API keys, login cookies, provider tokens or unfinished worker state in account records.

## Setup From The App Owner

1. Create/configure a Google OAuth web client and consent screen in the owner's Google Cloud project. Register `https://jobs-hunter.streamlit.app/oauth2callback` as the authorized redirect URI and configure the intended personal test user/access.
2. Create a private durable backend project, recommended Supabase. Select a region appropriate for the CV and application data. Review its current plan, retention and backup arrangements before uploading private data.
3. Configure the OAuth client ID/client secret, strong cookie secret, backend credentials and allowed Google account in Streamlit Secrets, using the implementation's eventual template. These are not Gemini or SerpAPI keys. No account secrets template is active yet.

Creating credentials and agreeing to provider account terms remain owner actions. App code and mocked tests can be built before credentials exist; actual Google sign-in and restart persistence cannot be verified until the services are configured. Existing session data is not automatically recoverable after a restart; any session-to-account import must be explicit and must never replace an existing account silently.

## Privacy And Release Gate

Provide a clear storage notice before saving a CV to the backend, CV replacement/removal, and an explicit delete-account-data flow with retention/backup limitations documented. Never log CV text, tokens, contact details or raw credential-bearing errors. Sign-out/account switching must cancel session work and clear account state before another user can access it.

Test allowed/denied and signed-out accounts; stable ownership and cross-account isolation; upload/replace/remove; criteria-mode CV non-disclosure; settings and application-history round trips; duplicate rediscovery preserving Applied status; invalid snapshots; storage outages; stale/concurrent writes; logout during a search; and absence of private data in commits/logs. Run the full verification gate, independent review, feature/main CI, and real production sign-in/reboot tests before announcing durable saving. Version and changelog the implementation separately from this proposal.

## Primary References

- [Streamlit authentication](https://docs.streamlit.io/develop/concepts/connections/authentication)
- [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect)
- [Supabase database access and RLS](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [Supabase private buckets](https://supabase.com/docs/guides/storage/buckets/fundamentals)
