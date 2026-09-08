# Architecture

## Shape

Job Hunter starts as a small Python package plus documentation. The core rule
is local-first: private files stay on the user's Mac, while the public
repository holds templates, deterministic logic, and tests.

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
              shortlist / review / reject
```

## Components

| Component | Responsibility |
|---|---|
| `profile.py` | Stores a public, contact-free candidate profile summary |
| `scoring.py` | Scores one job dictionary against preferences |
| `queue.py` | Stores scored jobs locally and prevents duplicates |
| `cli.py` | Provides add/import/list commands for the local workflow |
| `config/` | Holds public template and private local override path |
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
