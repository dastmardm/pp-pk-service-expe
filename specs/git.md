# Git Workflow

## Sources
- `specs/constitution.md` quality gates and secret-handling principles.
- Repository layout: `docs/**`, `specs/**`, `src/**`, `tests/**`, `inputs/**`,
  `utils/**`, `.claude/**`, `.env.example`, `pyproject.toml`.
- Existing ignore policy: real `.env` files are ignored; generated caches are not
  committed.

## Branch Naming
First matching row wins. Base branch is always `main`.

| Change class | Path globs that trigger it | Branch pattern | Base branch |
|--------------|----------------------------|----------------|-------------|
| Specs | `specs/**` | `specs/<slug>` | `main` |
| Source fix | `src/**`, `utils/**` when addressing evaluation/spec gaps | `fix/<slug>` | `main` |
| Source feature | `src/**`, `utils/**` otherwise | `feat/<slug>` | `main` |
| Tests | `tests/**` without `src/**` | `test/<slug>` | `main` |
| Data/gold | `inputs/**`, `docs/sme_stage_cases.csv` | `data/<slug>` | `main` |
| Docs | `docs/**` except `docs/sme_stage_cases.csv` | `docs/<slug>` | `main` |
| Harness/config | `.claude/**`, `.env.example`, `pyproject.toml`, `.gitignore`, `*.toml` | `chore/<slug>` | `main` |

`<slug>` is kebab-case, five words or fewer.

## Mixed-Change Rule
Use the highest-precedence class in this order:
`specs` > `source fix` > `source feature` > `tests` > `data` > `docs` > `harness/config`.
Tests that directly verify source changes travel with the source branch. Split
unrelated docs/spec/source changes when they are not part of one coherent unit.

## Commit Convention
- Format: Conventional Commits, `type(scope): subject`.
- Allowed types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `perf`,
  `build`.
- Scope is optional and should name the main area: `specs`, `docs`, `pipeline`,
  `stages`, `eval`, `ui`, `cli`, `runtime`.
- Subject is imperative, no trailing period, 72 characters or fewer.
- Required trailer:
  ```text
  Co-Authored-By: OpenAI Codex <noreply@openai.com>
  ```

## Push & PR Policy
- Never commit directly to `main`.
- Push the branch with upstream tracking: `git push -u origin <branch>`.
- Open a PR to `main` after the Pre-Commit Gates pass.
- PR title is the primary commit subject.
- PR body includes: summary, specs/requirements/evaluation IDs addressed, gates
  run, and `Generated with Codex.`

## Pre-Commit Gates
Run in order:
1. `python3 -m compileall src/oppp`
2. `ruff check src tests`
3. `ruff format --check src tests`
4. `pytest -q`

Docs/specs-only changes with no Python changes may skip gates 1-4 only when the
commit message or PR body explicitly says `Docs/specs only; code gates skipped`.

## Never Commit
- `.env` or any real credential file.
- API keys, TERMite credentials, tokens, or private certificates.
- `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, build outputs, and
  local report scratch files.
- Large or binary files except intentionally tracked project artifacts such as
  `docs/agent-dag.png`.
- Do not use `git add .`, `git add -A`, or `git add --all`; stage explicit paths.

## Safety & Idempotency
- If the branch already exists, reuse it.
- If there is nothing to commit, report a clean tree and exit without an empty
  commit.
- If a PR already exists for the branch, update it rather than creating a
  duplicate.
- No force-push, rebase, history rewrite, or hard reset.
- Operate only inside this repository.
