# Account Save Warning Fix

## Scope

Fix repeated save warnings and overlapping account writes without hiding failed saves or weakening revision checks. No changes to authentication, storage schema, encryption keys, scoring or search budgets.

## Evidence

- Search rendered save status in the sidebar, progress fragment and page footer; the signed-in regression reproduced three warnings for one failure.
- AccountSession did not coordinate overlapping network writes. A delayed first response allowed a second write to reuse the old revision and raise a false conflict.
- The reproduction establishes a code defect, not the exact sequence of requests in the owner's production session. Genuine conflicts still require explicit reload.

## Changes

1. Serialize save/load/clear through revision acknowledgement and discard saves queued before a successful reload/deletion.
2. Render account status once, in the sidebar after page saves. Expand recovery details only when there is an error.
3. On a new fragment save error, retain accepted results/logs and refresh the whole page once so recovery controls appear.
4. Update v1.19.1 release metadata, changelog, user guide, setup recovery notes and architecture.

## Verification And Release

- Reproduce overlap and duplicate warnings before implementation; rerun regression and full test suites afterward.
- Check stale-tab overwrite protection, confirmation before reload/deletion, queued-write invalidation and outage retry.
- Review the diff, verify feature-branch CI, fast-forward main, verify main CI and smoke-test the public sign-in page.
- Do not read deployment secrets or touch live account records. Owner verifies real parameter persistence after refreshing and resolving any existing conflict.
