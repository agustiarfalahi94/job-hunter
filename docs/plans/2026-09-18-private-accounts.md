# Private Accounts Implementation Plan

> Execute the approved account design in this isolated feature branch using test-first changes and independent review.

**Goal:** Add optional personal Google login with encrypted, durable CV, settings, queue and application-history saving.

**Architecture:** Native Streamlit OIDC validates identity. An allowlisted Google subject owns an encrypted JSON snapshot in a private Supabase table, accessed only by server-side RPC. Keep SessionWorkspace, caches and background controllers session-local; save accepted results on the Streamlit thread.

**Tech Stack:** Streamlit 1.63, Authlib, requests, cryptography Fernet, Supabase Postgres/PostgREST.

**Spec:** [Account Saving Design](../ACCOUNT_SAVING_DESIGN.md).

## Execution Record

- Tasks 1-3 implemented with test-first config, identity, encryption, snapshot, persistence, lifecycle and app regressions. Native identity/HTTP fixtures are synthetic; no private backend calls have been made.
- Account mode is disabled by default. Owner OAuth/Supabase configuration and real sign-in/save/reboot checks remain external prerequisites.
- Independent review found stale configuration authorization, failed-reload cancellation and empty plaintext handling. Regression tests reproduced all three before fixes; independent re-check found no remaining concrete findings in them.
- Local full suite passes (338 tests; one PostgreSQL class skipped because server tools are absent). Initial feature CI passed 345 tests with no skips, including all eight real PostgreSQL migration tests. The upload-limit follow-up passes all 346 tests on both feature and main CI.
- Verified code commit: `5d621539c51f3638d573a12f9713f001bade9738`. [Feature CI](https://github.com/agustiarfalahi94/job-hunter/actions/runs/35263450639) and [main CI](https://github.com/agustiarfalahi94/job-hunter/actions/runs/35263569793) passed. Documentation follow-ups do not change the gated account behavior.
- Production guest-mode browser smoke passed on 2026-09-18: app imports, empty selected criteria, criteria/CV mode navigation and the new matching-mode help text loaded. Account mode remains off; no live OAuth/account-storage calls or search-provider quota were used for this smoke check. Local browser verification also passed; its temporary server was stopped afterwards.
- Setup guide, blank credential template, SQL migration, dependency floors, v1.18.0 and changelog are prepared. Generate secrets only in the owner's terminal; nothing is printed in chat or committed.

The detailed checklist below defines the planned acceptance criteria. Live-provider checks must not be marked complete by synthetic tests.

## Constraints

- Accounts are off by default. Enabled but invalid configuration fails closed.
- Google issuer + subject determine ownership; verified email gates access.
- No hosted local disk, shared SQLite, public CV bucket, stored provider cookies/tokens or committed credentials.
- Native Google identity does not create Supabase auth.uid(). Deny anon/authenticated access; enforce owner parameters in authenticated server code.
- Keep the current discovery/scoring/cancellation ceilings and criteria-mode CV non-disclosure.
- Use revision compare-and-swap and deletion tombstones to stop stale tabs recreating removed data.
- Real login/restart persistence requires owner-configured OAuth and backend; mocked checks do not establish deployment readiness.

## Task 1: Account Configuration And Identity

Files: create src/job_hunter/account_config.py, tests/test_account_config.py.

Interfaces: AccountConfig, AccountIdentity, load_account_config(secrets), identity_from_claims(claims, config, now=None).

- [x] Write tests for disabled defaults, incomplete enabled setup, secret redaction, trusted HTTPS Supabase endpoint, Google-only metadata/issuer, verified-email allowlist, stable ownership and expired identity.
- [x] Run the new tests and confirm missing functionality fails.
- [x] Implement strict validation and safe fixed error messages. Use repr=False for secret fields.
- [x] Run identity/config regressions before moving to storage.

## Task 2: Private Snapshot And Atomic Backend

Files: create src/job_hunter/account_snapshot.py, src/job_hunter/account_store.py, tests/test_account_snapshot.py, tests/test_account_store.py, config/supabase_accounts.sql; modify session_workspace.py.

Interfaces: encode_snapshot(owner_id, workspace, settings, mode), decode_snapshot(owner_id, content); SupabaseAccountStore.load(identity), save(identity, revision, payload), clear(identity, revision).

- [x] Write failing round-trip tests for CV and manually recorded applications, retained custom criteria/mode, duplicate rediscovery preserving Applied, empty state, owner mismatch, unknown schema, malformed records and size limits.
- [x] Write failing transport tests for encryption, bounded timeout, no redirects, secret-key header, owner-scoped RPC, invalid replies, sanitized errors and revision conflicts.
- [x] Implement authenticated Fernet snapshots using a deployment-only encryption key; never persist caches or controllers.
- [x] Implement service-only SQL RPCs. Initial insert is conflict-safe; updates and clear require the current revision. Clear increments revision and nulls payload, preserving a tombstone.
- [x] Validate migration syntax, grants, anonymous denial, CAS and tombstones against a local disposable Postgres if available. Document any external tests not performed.

## Task 3: Account Lifecycle And UI

Files: create src/job_hunter/account_session.py, src/job_hunter/account_ui.py, tests/test_account_session.py, tests/test_account_ui.py; modify src/app.py.

Interfaces: AccountSession restores before rendering settings, flushes only changed snapshots and remembers last successful revision; account_ui.prepare_account(state, secrets), persist_account(state), clear_session(state).

- [x] Write failing tests for account round trips after simulated restart; failed load cannot save; unchanged reruns cannot write; conflict cannot overwrite; explicit retry/reload; delete confirmation; logout cancels workers and clears private state; disabled accounts preserve guest behavior.
- [x] Show Google login only with complete enabled setup. Denied identities cannot reach the workspace/backend. No guest bypass when private accounts are enabled.
- [x] Restore workspace/settings/mode once per identity. Save settings callbacks, CV save/remove, posting/application edits, and accepted background results. Show actual Saved/Unsaved/conflict/error status.
- [x] Add explicit reload/retry and confirmed account-data deletion. Do not silently discard unsaved changes or continue a stale controller after logout/reload.
- [x] Add a private-storage notice before account CV upload. Keep Profile & CV hidden in criteria mode.
- [x] Verify the app imports and navigation in disabled, signed-out, denied and signed-in mocked states.

## Task 4: Release And Owner Setup

Files: update requirements.txt, pyproject.toml, init version, README, AGENTS, CHANGELOG, architecture/deployment/development docs; add docs/ACCOUNT_SETUP.md and safe account-secrets example.

- [x] Add Authlib and cryptography dependency floors, bump to 1.18.0, and document backend encryption-key backup/retention limits and recovery.
- [x] Provide exact Google callback, Supabase SQL migration, secret-key type and private enablement checklist. Provide local secret-generation commands for owner use; never run them into chat/logs or commit their output.
- [x] Run the full check script, compileall, dependency consistency and diff checks; obtain independent security/correctness review and fix findings.
- [x] Push the feature branch, verify CI, fast-forward main, push and verify main CI.
- [x] Smoke-test production guest mode while credentials are absent. Report real Google login and durable save/reboot tests as blocked on owner setup, not passed.
