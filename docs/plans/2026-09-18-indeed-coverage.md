# Indeed Coverage Follow-Up

## Evidence

The owner's private CSV contains ten snippet-scored fallback jobs, with no target URL. Eight company cells contain a city, and a parenthesized title is split at a hyphen. Keep the CSV outside Git. An export contains retained queue rows, not the original discovery responses or skip log, so it does not prove why this particular vacancy was absent.

The public reference job is readable through the browser/research service and lists relevant SQL/Power BI work in Kuala Lumpur. That does not establish that the app server can read Indeed or that Google returns it for a particular query.

Current hosted discovery requests only the first page of each signal query. SerpAPI documents `start` pagination; requesting `num=50` does not establish fifty returned results. Preserve title OR description discovery and all existing ceilings.

## Implementation

- Reproduce Indeed city/company confusion and parenthesized-title truncation. Parse the platform's title/city/footer conservatively; never infer an employer or location from query hints.
- Add validated provider-advertised pagination. Extract only a strictly advancing offset from an official SerpAPI link, then rebuild from the original query/key/filters. Never fetch a provider-supplied destination or accept replacement credentials/query parameters.
- Schedule all selected sources' initial queries before later pages. Later pages share the existing twelve-request, fifty-unique-candidate, cancellation and five-minute limits. Empty/exhausted pages stop; pagination is not an exhaustive search guarantee and consumes the same monthly allowance.
- Test discovery of a known fixture URL on a later page, ordering, caps, cancellation, duplicates, invalid pagination and location/title preservation. Fixtures are synthetic; real target discovery remains provider-dependent.
- Update v1.18.1, changelog/README/architecture/testing docs; independently review, run all checks and feature CI, integrate main and verify main/production separately.

## Primary Sources

- [Reference posting](https://malaysia.indeed.com/viewjob?jk=9e3ad6434cb74fde)
- [SerpAPI pagination](https://serpapi.com/search-api#api-parameters-pagination)
- [Provider-generated pagination offsets](https://serpapi.com/pagination)

## Verification Record

- Parser and pagination failures reproduced before fixes. Independent review identified variable organic-result offsets, distinct rejected-only pages and malformed rejected URLs; each received a failing regression followed by a passing fix.
- Eleven coverage tests pass, and the independent reviewer reports 72 focused tests passing with no remaining concrete findings in the scoped patch.
- Full local checks run 349 tests successfully; the SQL integration class is skipped without local PostgreSQL. Compilation, dependency consistency and diff whitespace checks pass. CI must run the eight real PostgreSQL tests before main integration.
- Feature/main CI and deployed search verification remain pending at this commit. Synthetic discovery of the reference URL does not establish live provider coverage.
