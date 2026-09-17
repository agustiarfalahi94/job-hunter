# Persistent Criteria And Company Lookup Implementation Plan

**Goal:** Preserve search parameters during navigation, start new web sessions empty, and resolve company names to grounded official regional career sites.

**Architecture:** Keep durable session selections separate from disposable Streamlit widget keys. Keep the existing CLI defaults and CV evidence catalog, but never use them as selected web criteria. Resolve unknown company names with Gemini Google Search, require source-backed official careers and regional evidence, validate public HTTPS destinations, and cache results by company and region within the session.

**Tech Stack:** Streamlit 1.63, Google GenAI SDK, existing safe job-page fetching and unittest/AppTest.

**Approval:** User's requested behavior and standing instruction to implement, test, document, branch, and push without routine approval prompts.

## Constraints

- No CV data in criteria mode or company-lookup prompts.
- No public or shared-server persistence of criteria, CVs, or keys.
- Preserve the 50-job, 12-job-discovery-request, two-worker search ceilings.
- At most five company sources; two Gemini lookup attempts per company and session caching of successes/failures to prevent repeat calls on reruns.
- No inferred domains when live grounding/official regional evidence cannot be verified.
- Keep explicit domains supported without Gemini; clearly label them as user-provided.
- Keyword values are case-insensitive alternatives, bonus values are optional scoring signals, and location/source/date constraints still apply.

## Tasks

- [x] Reproduce widget-state cleanup and empty-default failures with AppTest; add Azure case and optional bonus regression tests.
- [x] Add permanent search-setting storage and disposable widget keys for all eight criteria/source/date controls. Use empty selected lists and no selected location in new web sessions; retain Past month freshness protection.
- [x] Test grounded company lookup with mocked provider replies: missing grounding, wrong region, corporate ownership scope, unsafe URLs, bounded retries, and no CV data.
- [x] Implement company lookup, regional verification, session cache, consistent domain labels, evidence links and Google Search suggestions; retain explicit-domain fallback.
- [x] Update README/tutorial, specifications, architecture, scoring docs, changelog and release version to v1.16.0.
- [x] Review changes and run the full test gate, compile check, dependency check, and diff check. Verify local UI round trips.
- [ ] Commit/push feature branch, verify feature CI, integrate main, verify main CI and deployed empty defaults/company lookup separately.

## Verification

```sh
PYTHON_BIN=/Users/lilianyoctoria/Documents/job-hunter/.venv/bin/python ./tool/check.sh
python -m compileall -q src tests
python -m pip check
git diff --check
```

Automated tests mock external providers. Production lookup smoke testing uses only a public company name and region, never a CV and never a real job-discovery run.
