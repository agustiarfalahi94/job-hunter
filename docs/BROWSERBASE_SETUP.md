# Browserbase Setup

Browserbase adds a user-operated application browser to Job queue. It is off by
default. The external Apply link always remains available. This integration does
not guarantee that LinkedIn, Indeed, JobStreet, Foundit or every employer accepts
remote browsers; test each destination and respect its access restrictions.

## Owner Setup

1. Complete [private Google account setup](ACCOUNT_SETUP.md), including Supabase
   storage and the verified-email allowlist. Confirm account reload works. Guest
   visitors cannot consume Browserbase sessions using the owner's API key.
2. Create a project at [Browserbase](https://www.browserbase.com/). Get its API key
   and Project ID from project settings. Review its plan limits and privacy policy.
3. Add the following **root-level** entries to Streamlit Cloud Secrets, above any
   `[search]`, `[accounts]` or `[auth]` sections. Keep the existing secrets intact.

   ```toml
   BROWSERBASE_ENABLED = true
   BROWSERBASE_API_KEY = "your-private-browserbase-api-key"
   BROWSERBASE_PROJECT_ID = "your-browserbase-project-id"
   ```

4. Restart if needed. Sign in to Job Hunter, select a non-expired job, consent to
   Browserbase processing, then select **Apply here**. No provider request occurs
   merely by viewing the queue. Do not share keys or temporary live-view links.
5. Verify the destination in the remote browser. Log in there yourself if needed.
   Job Hunter's Google login does not log in to a job platform.
6. Click the employer form's file field. When Job Hunter displays its document
   request, explicitly choose **Attach saved CV** or select another document and
   click **Attach selected document**. Check the requesting domain first. Only
   non-empty PDF, DOC and DOCX documents up to 5 MB are accepted. Upload fields
   that change, detach or navigate must be selected again. Each request expires
   after two minutes; click the file field again to request a fresh attachment.
7. Review and submit on the employer page yourself. Only after successful
   submission, use **I have applied to this job**. This remains a user-reported
   record, not automated evidence of employer receipt.
8. Close the application browser when finished to conserve browser minutes.

## Costs, Privacy And Lifecycle

- Browserbase is a separate service from SerpAPI/Gemini. Creating a browser uses
  its allowance, even if no application is submitted. The app does not upgrade
  plans, purchase credits or use an AI agent to operate the browser.
- The [current pricing page](https://www.browserbase.com/pricing) lists a free
  tier with one browser hour and a 15-minute session limit. Recheck current
  allowances before enabling; simultaneous app tabs can consume separate sessions.
- The app caps every session at 15 minutes or remaining Google identity lifetime,
  whichever is shorter. It maintains the CDP connection without paid keep-alive.
  The worker requests release after 60 seconds without queue heartbeat, on Close,
  or when account state is cleared. Closing your local tab may not end the remote
  session immediately. A process crash is bounded by the provider timeout.
- Sign-out, account switch, saved-data reload and deletion clear the local browser
  state and request remote release. Platform cookies are never saved as reusable
  Browserbase contexts. New remote sessions require their own login.
- Recording and session logging are disabled explicitly. This is **not** a claim
  of provider-wide zero retention: Browserbase still processes session traffic,
  credentials entered into the remote page and attached documents. Consult its
  privacy/retention terms. The app does not read or store job-platform passwords.
- In-flight requests may settle after Close. A failed or timed-out create request
  can leave an unobserved session until the provider timeout. Check Browserbase's
  Sessions dashboard before retrying. There are no automatic creation retries.
- Login rejection, verification challenges and site blocking require human action
  or the external link. No stealth/proxy fallback or automated CAPTCHA solver is
  enabled. Mobile keyboard support depends on Live View; desktop is the first
  supported test target.
- Some initial popup navigations cannot be inspected before the browser creates
  their frame. These are blocked with an original-page fallback; the existing
  application tab stays open. Complete popup-dependent sign-in or applications
  using the external Apply link, rather than bypassing destination checks.
- An active remote form is not a durable draft. Restart/disconnection can lose
  unsent answers. Job Hunter's saved CV, search criteria and manual application
  history remain separate from remote browser lifetime.

## Verification And Rollback

Automated tests use mocked Browserbase responses and an intercepted synthetic
form, not real accounts or applications. Run the browser integration locally:

```sh
PYTHONPATH=src JOB_HUNTER_TEST_CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  .venv/bin/python -m unittest discover -s tests -p test_application_browser_integration.py -v
```

On Linux CI, install Playwright Chromium and set `JOB_HUNTER_TEST_CHROME=bundled`.
Production connects to a remote browser, so it does not need a local Chromium
download. No real Browserbase session, platform login or application submission
is established by passing these tests.

Before using personal data, verify a live session starts, remains interactive
through Streamlit refreshes, and closes in the Browserbase dashboard. Confirm no
recording/logs were retained. Then test upload and submission yourself on an
intended application, checking the destination before attaching the CV. Verify
sign-out removes the view, denied accounts cannot start one, and timeout behavior
does not claim submission. Do not submit fake applications to real employers.

To disable the feature, set `BROWSERBASE_ENABLED = false`. Active rendered views
request closure; abandoned workers expire by heartbeat/provider timeout. Release
remaining sessions in Browserbase's dashboard when urgent. No data migration or
deletion is needed; search, queue and manual Applied history remain available.

## Provider References

- [Create session and privacy flags](https://docs.browserbase.com/reference/api/create-a-session)
- [Interactive Live View](https://docs.browserbase.com/platform/browser/observability/session-live-view)
- [File chooser upload integration](https://docs.browserbase.com/platform/browser/files/uploads)
- [Explicit session release](https://docs.browserbase.com/reference/api/update-a-session)
