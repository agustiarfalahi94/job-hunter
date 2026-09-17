# Private Account Setup

v1.18.0 includes Google account saving, **disabled until the owner configures it**. Google login identifies you to Job Hunter, not to job boards. It does not authorize application submission or repair Gemini/SerpAPI quota.

## What You Need To Do

1. Create a Google OAuth **Web application** client in your Google Cloud project. Configure Google Auth Platform branding/audience and your intended account as a test user when using a testing audience. Add this exact authorized redirect URI: `https://jobs-hunter.streamlit.app/oauth2callback`. Retain the client ID and client secret privately. Follow the [official Streamlit Google setup](https://docs.streamlit.io/develop/tutorials/authentication/google).
2. Create a Supabase project in a region appropriate for your CV/history. Review the provider's current plan, retention and backup settings. In its SQL Editor, run [supabase_accounts.sql](../config/supabase_accounts.sql). It creates one private table and two service-only RPCs; it does not erase existing rows when rerun.
3. Copy the project HTTPS URL and a **server-only `sb_secret_...` key** from Supabase API settings. Do not use a publishable/anonymous key, a database password, or a Gemini key. See [Supabase key types](https://supabase.com/docs/guides/getting-started/api-keys). This privileged key bypasses RLS and must stay in Streamlit's server Secrets, never browser code, chat or Git.
4. Generate a separate cookie secret and Fernet encryption key locally using the commands below. Back up the encryption key privately: losing or replacing it makes saved data unreadable.
5. In Streamlit **Manage app > Settings > Secrets**, keep existing SerpAPI/Gemini settings **before any TOML table headings**, then append the account tables from [accounts.secrets.example.toml](../.streamlit/accounts.secrets.example.toml). Fill every blank and replace the example email with your verified Google account. Set `enabled = true` only when all setup is complete. Save and reboot the app.

Do not post keys here. You can tell the agent when OAuth, the migration and Secrets are ready, or share a sanitized error. Owner account creation/provider terms and private credential entry remain your actions. Code deployment alone cannot enable or verify login.

## Generate Deployment Secrets

After installing the app's dependencies, run locally:

```sh
python -c 'import secrets; print(secrets.token_urlsafe(48))'
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

The first output is `auth.cookie_secret`; the second is `accounts.encryption_key`. These outputs are real secrets: store them in your password manager and Streamlit Secrets, not a tracked file or chat. Do not generate new encryption keys for existing saved data. [Fernet's key-loss warning](https://cryptography.io/en/latest/fernet/) explains why the original key matters.

For local sign-in, also register `http://localhost:8501/oauth2callback` in the same Google client and use that callback in ignored `.streamlit/secrets.toml`. Production must retain the HTTPS production callback. The public examples are not active credentials.

## Verify Production

- Signed-out users see Google sign-in, not CV/search/history controls. A Google account outside `allowed_emails` cannot access the workspace.
- Sign in with the allowed account. A new account has empty criteria and no CV. Upload a synthetic, readable PDF/DOCX before testing your real CV; check the storage notice and account save status.
- Edit custom criteria, navigate to the queue and back, and confirm they remain. Switch modes: Criteria-based hides Profile & CV without deleting its saved contents.
- Search, review a job, manually record Applied, and correct posting date/expiry. Check that saving succeeds. Opening Apply alone must not record Applied.
- Sign out, sign in again, then reboot the app and sign in again. Confirm CV, criteria/mode, job records, manual Applied timestamp/evidence and posting corrections restore. These are the real durability tests; mocked tests are not a substitute.
- Replace and remove the CV; after another sign-in, removal must persist while application history remains.
- Use two tabs: change data in one, then edit stale data in the other. The stale tab must show a conflict and require confirmed reload, not overwrite the newer record.
- With synthetic data, confirm **Account > Saved data > Delete saved data** clears CV/settings/queue/history. A stale tab cannot resurrect them. No private data or credentials should appear in repository files/logs.

Until this checklist passes, real Google login and provider-backed persistence are **not verified**. Guest production can be smoke-tested without enabling accounts or spending search quota.

## Storage And Privacy

The allowlist restricts access by verified Google email; stable Google issuer/subject determines the actual data owner. Email changes do not create a new owner. OAuth identity expiry requires fresh sign-in even if Streamlit's browser cookie remains present.

CV bytes, extracted text, criteria and job/application records are encrypted together with Fernet before the server sends a snapshot to Supabase. Supabase receives ciphertext, an opaque hashed owner ID, revision and update time. Encryption protects backend records, not a compromised app server or stolen deployment key. CV-based Gemini matching separately sends readable CV text to Gemini; criteria-based matching does not. Provider tokens/cookies, API keys, caches and unfinished searches are not saved.

Limits: account CVs up to 5 MB, plaintext snapshot up to 12 MB, 5,000 jobs and up to 100 values per saved list. These do not increase the 50-job search ceiling. Exceeding limits shows Not saved; reduce data before assuming it is durable. No guest session is automatically imported when account mode is enabled, and old guest data is not recoverable after a reset.

Native Streamlit Google identity is not a Supabase Auth session. The table has RLS enabled and anonymous/authenticated access revoked; server role RPCs enforce atomic revisions, while the app enforces authenticated owner identity. No CV bucket is created and no public storage URL is used. Backend administration is privileged: do not share the Supabase key or enable public table policies.

Sign-out removes session state but keeps the saved snapshot. Confirmed deletion clears the current payload and retains its opaque owner/revision tombstone. Provider backups may retain previous data under their retention policy; app deletion cannot erase those backups immediately. A stale session keeps its local copy until sign-out/reload but cannot save over the deletion.

## Recovery

- **Setup incomplete / denied:** verify enabled account fields, OAuth callback, verified-email allowlist, modern Supabase secret key, SQL migration and grants. Invalid enabled setup deliberately has no guest bypass.
- **Not saved / outage:** leave the session open; choose Retry saving after connectivity returns. Avoid sign-out/reboot until saving succeeds. Automatic polling does not hammer a failed backend with retries.
- **Another tab changed data:** review which tab has the latest records; explicitly discard the stale tab's edits and reload saved data. There is no automatic overwrite/merge.
- **Cannot decrypt:** restore the original deployment encryption key from private backup. Do not rotate blindly, clear the account to bypass an error, or overwrite after a failed load. This release does not implement key rotation.
- **Expired sign-in:** sign out and sign in again. Saved records remain; unsaved changes cannot be guaranteed after reauthentication.

To temporarily roll back private mode, set `accounts.enabled = false`; guest sessions start separately and existing backend records remain private. Do not delete the backend or change encryption keys to roll back. Re-enable with the original keys after correcting setup.

## Verification Scope

Automated tests use synthetic identities/CVs and mocked HTTP for account/UI restart flows. CI also starts an isolated PostgreSQL cluster, applies the real migration, and checks grants, ownership scoping, atomic stale/concurrent writes, tombstones, sizes and reruns. Tests never contact the owner's backend or spend search/Gemini quota. They do not test Google's live OAuth redirect or Supabase's live API gateway.
