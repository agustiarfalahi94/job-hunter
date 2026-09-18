# Positive And Negative Test Cases

## Later-Page Discovery And Export Diagnosis

The `test_search_pagination.py` fixtures publish the reference URL only on a later provider page. Assert that it reaches scoring after initial title/description queries, without claiming live index coverage. Other tests verify twelve requests, fifty candidates, repeated/empty pages, Stop and safe continuation reconstruction. Indeed role text with internal separators must remain intact; a trailing recognized city supplies location, not an employer.

For a live narrow positive search of the reference, use target title `Senior Data Analyst (Analytics & Business Intelligence)`, primary keyword `Power BI`, optional bonus `SQL`, Location `Kuala Lumpur`, Indeed only, Any time, and empty hard-skip/quick-apply filters. The narrower title may improve discovery ranking but cannot guarantee retrieval. Keep the posting date unknown unless verified. A negative suitability test uses the same search with `Power BI` as a hard skip; any discovered posting containing that term must be skipped.

An exported queue contains retained jobs only. To diagnose a missing reference, inspect the search activity log/provider history: absence from provider results is discovery coverage, whereas a logged restriction/date/location skip is filtering. Gemini quota errors happen after discovery and explain labelled fallback scoring, not an absent provider result. Browser readability does not establish app-server access. Keep private exports/logs out of Git.

## Reference Posting

[Indeed reference](https://malaysia.indeed.com/viewjob?jk=9e3ad6434cb74fde): Senior Data Analyst (Analytics & Business Intelligence), Integrated Health Plans (Malaysia) Sdn Bhd, Kuala Lumpur. The readable posting mentions SQL, Power BI, dashboards, reporting, databases, pipelines, and stakeholder work. No readable posting date was found. Its authorization/sponsorship question is not proof of local-only eligibility or visa sponsorship availability.

On 2026-09-17 the app's direct server fetch returned HTTP 401, even though web-readable content was available. This is an access limitation, not proof the vacancy is closed. The app must not bypass login/challenges or pretend it read inaccessible content. Source metadata/snippets can provide limited evidence; remarks must disclose that limitation.

## Positive Discovery

Use a fresh Criteria-based session. Target job titles: Data Analyst. Required description keywords: Power BI. Bonus keywords: SQL. Hard skips: empty. Location: Kuala Lumpur. Platforms: Indeed. Company sites: empty. Platform application filters: empty. Date posted: Any time for this unknown-date example.

Expected: if discovered, readable role/skill/location evidence supports a strong match; posting date may remain Unknown. Deterministic fixtures verify this evidence combination is shortlisted. Gemini scores can differ with supplied evidence, and unreadable full descriptions yield limited/snippet-based scores. Search ranking/indexing/access and fifty-candidate limits mean this exact URL is not guaranteed to appear, so its absence alone does not establish a scoring defect.

## Negative Checks

- Hard skip: retain positive values but add Power BI to Hard skip keywords. Any discovery containing it must be skipped; capitalization does not matter. Inspect the activity log, not a guaranteed queue row for skipped results.
- Geography: replace Kuala Lumpur with Jakarta. A posting observed in Kuala Lumpur must be skipped, not relabelled Jakarta. Missing posting geography remains unverified rather than fabricated.
- Suitability: for the same synthetic reference content, Accountant / SAP / Berlin earn low deterministic suitability. Running discovery with those criteria may find different matching jobs because title OR description is intentional; it is not a controlled comparison of the same vacancy.
- Quick apply: choose LinkedIn Easy Apply. A LinkedIn posting must expose vacancy-associated Easy Apply evidence; Apply alone, related-vacancy controls, descriptions mentioning Easy Apply, and inaccessible pages do not qualify. An Indeed posting is unaffected by this LinkedIn-specific choice.
- Expiry: a past source validThrough date skips before scoring. Unknown expiry stays unknown regardless of posting age. Mark a retained result Expired, save, and use All to see it with Apply disabled; choose Not expired/Unknown to correct it.
- Manual date: edit a real observed date and save. Date details must say User-entered, never platform-verified. It survives page navigation and rediscovery without borrowing verification from another date. Clearing restores Unknown; future dates are invalid.

## Isolation And Budget

Use independent fresh browser sessions for separate discovery runs so earlier queue rows do not confuse results. Session reset clears CV, queue and parameters. Automated fixtures isolate matching and parsing without live indexing or API quota; live discovery additionally depends on provider availability. Fifty means unique candidates before scoring, not best fifty or fifty per location. Five company sites and twelve discovery requests remain guards for runtime/API usage.
