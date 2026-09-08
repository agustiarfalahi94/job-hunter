# AGENTS.md - Instructions for AI Coding Agents

## Start Here

Job Hunter is a local-first job matching and application planning assistant.
v0.1 is intentionally conservative: score jobs, prepare application decisions,
and document the workflow before any browser automation or auto-submit logic.

Read this file, then `README.md`, then the files in `docs/`.

## Working Agreement

1. Keep the repository safe to make public.
2. Never commit the actual CV, contact details, job-board credentials, cookies,
   browser profiles, API keys, or private preferences.
3. Do not invent candidate experience. Candidate claims must come from
   `docs/CANDIDATE_PROFILE.md` or a private local source provided by the user.
4. Browser automation must be human-reviewed by default. Do not build
   auto-submit behavior without a separate explicit design and approval.
5. Run `./tool/check.sh` before every commit.
6. If verification cannot run, report it as unverified instead of guessing.

## Git Flow

- Use short feature branches for changes after the initial commit.
- Keep commit messages meaningful and scoped.
- Public remote should be `https://github.com/agustiarfalahi94/job-hunter.git`
  once GitHub authentication is available.

## Validation

```sh
./tool/check.sh
```

The check runs the Python tests with bytecode writes disabled.

## Safety Rules

- `config/preferences.example.yaml` is public and generic.
- `config/preferences.local.yaml` is private and git-ignored.
- `data/private/`, `data/raw/`, local databases, and generated exports are
  git-ignored.
- The scoring engine may say "review" or "reject"; it must not fabricate
  missing qualifications to improve a match.
