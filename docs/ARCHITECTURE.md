# Architecture

## Shape

Job Hunter starts as a small Python package plus documentation. The core rule
is local-first: private files stay on the user's Mac, while the public
repository holds templates, deterministic logic, a Streamlit dashboard, and
tests.

```text
config/preferences.local.yaml   docs/CANDIDATE_PROFILE.md
             |                            |
             v                            v
       preferences                 public evidence
             |                            |
             +------------+---------------+
                          v
                   scoring engine
                          |
                          v
                  SQLite job queue
                          |
                          v
                  draft assistant
                          |
                          v
              dry-run application packet
                          |
                          v
                 daily workflow summary
                          |
                          v
              shortlist / review / reject

data/private/cv/current_cv.pdf stays outside Git and is managed separately by
the Streamlit profile page. Extracted CV text is saved beside the PDF and used
for Streamlit signal display.
```

## Components

| Component | Responsibility |
|---|---|
| `profile.py` | Stores a public, contact-free candidate profile summary |
| `scoring.py` | Scores one job dictionary against preferences |
| `queue.py` | Stores scored jobs locally and prevents duplicates |
| `cv_store.py` | Saves, replaces, removes, and reports local private CV status |
| `cv_parser.py` | Extracts CV text and detects primary/bonus keyword signals |
| `search.py` | Builds public search queries, parses result pages, and ingests candidates |
| `cli.py` | Provides add/import/list commands for the local workflow |
| `drafts.py` | Builds local application drafts and warnings from supported evidence |
| `application_packet.py` | Builds dry-run packets for human-reviewed application steps |
| `workflow.py` | Summarises submitted count, remaining target, status counts, and next action |
| `config/` | Holds public template and private local override path |
| `src/app.py` | Streamlit dashboard over the local queue |
| `docs/` | Captures product and safety decisions |
| `tests/` | Protects scoring behavior and privacy boundary |

## Data Boundary

Public:

- Project docs.
- Generic preference schema.
- Non-contact candidate strengths supported by the CV.

Private:

- CV file.
- Contact details.
- Local preferences.
- Application records.
- Job-board credentials/session data.

## Provider Boundary

No LLM provider is required in v0.1. Future LLM usage should sit behind a
small adapter so Gemini, OpenAI, or another provider can be swapped without
changing application workflow code.

## Search Boundary

The v1.4 search provider reads public LinkedIn job cards when available and
public search-result pages for the remaining selected platforms. It scores the
visible title/company/location/snippet/source URL. This is production-testable
on Streamlit Cloud without credentials, but it is intentionally weaker than
authenticated job-board integration. Authenticated search and auto-apply flows
must be added as explicit provider modules with user-controlled credentials,
rate limits, site-specific permission checks, and human confirmation before
submission.
