# Project Spec

## Purpose

Job Hunter helps the candidate process many job openings without losing the
human judgment needed for truthful applications. It should turn a CV-supported
profile and local preferences into a shortlisting decision, application queue,
and later, tailored drafts.

## v0.1 Scope

Included:

- Public documentation for the project.
- CV-supported candidate profile without contact details.
- Job preference template.
- Deterministic scoring engine.
- Tests and local verification script.

Not included yet:

- Job-board scraping.
- Browser automation.
- Auto-submission.
- LLM-generated cover letters.
- Storage beyond local templates and future database notes.

## Success Criteria

- A public GitHub repository can be created without exposing private data.
- A developer can run the tests on a fresh clone.
- The candidate profile does not include unsupported or private claims.
- The scoring rules are easy to inspect and adjust.
- The next development phase is clear.

## Reference Projects Studied

- `kopi-kompas`: strong README style, explicit public/private API-key boundary,
  `AGENTS.md` as a handover document, and a single check script.
- `tiny-tapsters`: clear project layout, explicit validation gate, and strong
  warnings around secrets and shipped artifacts.
- `agustiar-data-pipeline`: Python project structure, `pyproject.toml`,
  requirements files, config example pattern, tests, and GitHub Actions CI.
- `random_recall`: existing Flutter starter structure and GitHub remote naming.

Useful patterns were adapted; unrelated app code was not copied.
