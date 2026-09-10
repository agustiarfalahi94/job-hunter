# Architecture

## Shape

Job Hunter is a small Python package behind a Streamlit interface. Public code contains deterministic search and scoring logic; private CV files, queue data, local preferences, and secrets remain outside Git.

```text
optional private CV       editable search/scoring criteria
         |                              |
         v                              v
   profile signals              provider queries
                                        |
                                        v
                              search result adapters
                                        |
                       +----------------+----------------+
                       |                |                |
                       v                v                v
                 closed check      date parsing     Apply URL discovery
                       |                |                |
                       +----------------+----------------+
                                        |
                                        v
                              deterministic scoring
                                        |
                                        v
                         additive SQLite job queue
                                        |
                                        v
                       Streamlit review + HTTPS Apply link
                                        |
                                        v
                         user's browser and final submit
```

## Components

| Component | Responsibility |
|---|---|
| `src/app.py` | Three-page Streamlit journey and live search feedback |
| `profile.py` | Public, contact-free candidate evidence |
| `cv_store.py` | Private CV save, replace, remove, and status |
| `cv_parser.py` | PDF/Word extraction and primary/bonus signal detection |
| `preferences.py` | Public template plus ignored local preference override |
| `locations.py` | Malaysia city lookup and local fallback |
| `runtime_config.py` | SerpAPI key loading from Streamlit secrets or environment |
| `search.py` | Provider queries, trusted-source parsing, freshness, availability, metadata, and progress |
| `scoring.py` | Explainable deterministic fit score and remarks |
| `queue_types.py` | Shared queue input contract |
| `queue.py` | Additive SQLite migration, persistence, and duplicate detection |
| `app_ui.py` | Queue row formatting, filtering, and safe application destination selection |
| `tests/` | Product behavior, privacy, migration, and Streamlit regression coverage |

Legacy CLI, draft, packet, and workflow modules remain for compatibility with earlier local versions. They are not part of the v1.11 Streamlit journey.

## Data Boundary

Public:

- source code, tests, documentation, and preference templates;
- contact-free candidate strengths already supported by the CV;
- provider domain allowlists and generic sample configuration.

Private:

- CV files and extracted text;
- contact and identity data;
- local preferences and queue databases;
- platform credentials, cookies, and application answers;
- Streamlit secrets.

## Search Boundary

SerpAPI is preferred when configured. Otherwise, the app attempts public LinkedIn cards and public web-result pages. Provider filters narrow posting age, while parsed dates supply a second verification layer. Search cards and trusted destination pages are checked for closed-job markers.

Availability fetches use short timeouts and trusted source domains. A blocked page yields an unknown-availability message rather than a false open/closed conclusion.

## Apply Boundary

Readable destination HTML is inspected for a link clearly labelled as an application action. Relative links are resolved against the source URL. Only HTTPS destinations with a hostname are stored or shown.

The Streamlit server does not control the visitor's browser session. The Apply control opens the discovered destination, or the original posting as a fallback, in a new tab. Login, CAPTCHA, required questions, review, and submission remain in the user's browser. This boundary also avoids implementing LinkedIn automation that the platform prohibits.

## SQLite Migration

`posted_date` and `apply_url` are added with `ALTER TABLE` only when missing. Existing rows are retained and receive empty values, which the interface renders as `Unknown` or falls back from safely.

When a later search finds the same job again, missing date and Apply metadata
are backfilled without replacing non-empty values already stored on the row.
