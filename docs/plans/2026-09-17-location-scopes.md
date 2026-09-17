# v1.17 Multi-Area Search Plan

## Scope

Approved user request: multiple cities with OR, country-wide choices, and ASEAN/APAC presets. Explain rather than increase the existing five-company and fifty-candidate limits.

Follow-up approved scope: Europe/Global, configured/actual Gemini model visibility and quota clarification, strict platform-specific quick-apply filters, manual date/expiry evidence, visible location fallback/conditional columns, primary-only deduplication, and documented reference-job positive/negative checks.

## Implementation

1. Add failing tests for geographic membership, regional queries, saved multi-location navigation, company-region budgets, and background filtering.
2. Introduce shared ISO-country and documented regional-scope matching. Keep unknown evidence unverified and legacy single-string CLI criteria supported.
3. Convert web Location to a saved multiselect; migrate single-city settings. Group source/keyword/location alternatives in discovery and fairly bound direct-platform expansion.
4. Verify company names per unique selected region with cache reuse; enforce five lookup pairs before network calls and five resolved sites before discovery.
5. Update release version, changelog, README tutorial, engineering rules, and relevant specifications.

## Verification And Release

Run the full unit/Streamlit test gate, dependency/import checks, and whitespace checks. Obtain an independent code review and address actionable findings. Push the feature branch and verify CI, fast-forward clean main and verify its gate/CI, then inspect production controls and navigation without consuming job-discovery quota. Preserve unrelated worktrees and user changes.

Rollback trigger: import/startup failure, lost saved selections, escaped OR constraints, or incorrect verified-geography filtering. Roll back via a new revert commit, not destructive history rewriting.
