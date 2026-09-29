# Remembered Sign-In

## Approved Scope

Use Streamlit's native 30-day remembered login instead of Job Hunter's extra
Google ID-token expiry check. Keep saved CVs, criteria and application history
available through that login, and update release metadata and documentation.

## Decision

Trust native `st.user.is_logged_in` before reading claims at the page gate and
every private callback. Retain issuer/audience, verified-email allowlist and
stable subject ownership checks. Remove ID-token expiry from the internal
identity/storage/browser contract; do not extend tokens or create a sliding
30-day timer. This supersedes the short-token expiry policy in the private-account
and Browserbase implementation plans.

Streamlit validates OIDC on login and owns cookie validation and lifetime. Its
remembered cookie expires after 30 days, while existing active sessions follow
native behavior. Logout in one tab does not revoke other open sessions. Document
that limitation and shared-device precautions; do not claim a hard active-tab
deadline. Source: [Streamlit authentication](https://docs.streamlit.io/develop/concepts/connections/authentication).

Browserbase still requires authorized UI heartbeats and consent, with a separate
15-minute timeout, 60-second heartbeat lease and sign-out/denial cleanup. Google
login to Job Hunter does not authenticate job platforms.

## Verification And Release

1. Reproduce remembered-login rejection with an expired Google ID token.
2. Verify restore/save with synthetic CV/history and native login still true;
   retained valid claims must not bypass native signed-out status.
3. Verify allowlist/owner guards, browser consent, timeout and heartbeat cleanup.
4. Run full local checks, independent review, feature CI and main CI for v1.19.2.
5. Smoke-test the public sign-in page without private credentials. The owner can
   refresh and check continued access after the former short-token cutoff;
   automated tests do not simulate Google's live redirect or 30 days of real use.

No database migration or secret rotation. Reverting this code release restores
the shorter token cutoff without changing stored snapshots or encryption keys.
