# Strict Location Filter Repair

## Problem And Evidence

The user selected Kuala Lumpur OR Jakarta but received a Latin America job. A synthetic reproduction showed that unverified geography was cleared and passed to scoring, producing a shortlist result. The tri-state matcher classified Latin America as unverified, and search only rejected confirmed mismatches. Saved queue entries were not rechecked against current locations. A separate regression showed a matching city name overriding a conflicting explicit country.

## Scope

1. Require positive geographic membership before scoring when a non-Global location is selected. Keep the classifier tri-state and share its acceptance policy across hosted search, legacy search and Actionable queue filtering.
2. Preserve observed labels for skip explanations. Structured vacancy addresses remain stronger than provider-card evidence; country-only labels cannot confirm a city. Any matching address still satisfies OR locations.
3. Preserve Global and legacy calls without location constraints. Hide old mismatches in Actionable without deleting records or changing All/Already applied location-independent history.
4. Update v1.19.3 documentation, regression tests and release metadata. Keep provider budgets, account storage and browser-application behavior unchanged.

Independent review added regressions for slash/pipe-separated addresses, decorated country codes such as `US (Remote)`, and filling a blank saved location on rediscovery. These prevent strict filtering from hiding valid multi-location jobs or permanently hiding an older blank-location record; manual application history remains unchanged.

Follow-up review reproduced loss of structured address boundaries. Keep a structured locality attached to its country, preserve semicolons between saved independent addresses, and only split slash/pipe alternatives with their own country evidence. Cover both search paths and Global extraction through saving and subsequent Actionable selection.

Final review added mixed-list and structured-field punctuation round trips. Parse complete country-qualified groups independently of later unverified labels, and normalize address-field delimiters to commas before serializing structured evidence, retaining embedded country-code components. Synthetic cases cover both hosted and legacy filtering and Global-to-city queue changes.

## Verification And Release

- Failing regressions reproduce unverified Latin America/remote/missing locations reaching scoring and explicit-country conflicts matching a city.
- Positive cases cover Kuala Lumpur, Jakarta, multiple structured addresses, provider-only geography, Global and unrestricted legacy input.
- Streamlit navigation tests switch location selections and queue views, checking both visibility and unchanged workspace records.
- Run the full check script, compilation, dependency and whitespace checks; obtain independent code review before integration.
- Verify feature-branch CI, fast-forward main, verify main CI and perform a public sign-in startup smoke test. Synthetic tests do not establish live discovery coverage or reproduce an unidentified real posting.
- No migration or new secret is required. A rollback is a revert of this patch, retaining all saved account data; it would restore the permissive location behavior, so investigate false exclusions before choosing that rollback.
