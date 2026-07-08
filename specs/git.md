# Git Workflow

## Sources

- `specs/constitution.md`
- `specs/requirements.md`
- `specs/technical.md`
- `specs/evaluation.md`
- `specs/skeleton.md`
- `pyproject.toml`
- current repository layout under `docs/`, `specs/`, `.sdd/`, `src/`, and `tests/`

## Branch Naming

| Change class | Path globs that trigger it | Branch pattern | Base branch |
| --- | --- | --- | --- |
| Documentation | `docs/**` only | `docs/pk-staged-count` | `main` |
| Specification | `specs/**`, `.sdd/**` only | `specs/pk-staged-count` | `main` |
| Implementation | any of `src/**`, `tests/**`, `pyproject.toml` | `feat/pk-staged-count` | `main` |
| Git/workflow maintenance | `.github/**`, `.gitignore`, `specs/git.md` only | `chore/git-workflow` | `main` |

## Mixed-Change Rule

Use the highest-precedence class present in the diff:

1. Implementation
2. Specification
3. Documentation
4. Git/workflow maintenance

If implementation paths are present, use `feat/pk-staged-count` even when docs or specs are also changed. If only specs and docs are changed, use `specs/pk-staged-count`. If only docs are changed, use `docs/pk-staged-count`.

When the target branch already exists locally, reuse it. When it exists only on the remote, create a local branch tracking the remote branch. Do not force-push.

## Commit Convention

Commit messages use:

```text
<type>(pk): <imperative summary>

Spec-Source: <primary spec path>
```

Allowed types:

| Type | Use when |
| --- | --- |
| `docs` | Only `docs/**` changed. |
| `specs` | Only generated specs or `.sdd/**` changed. |
| `feat` | Production behavior under `src/**` changed. |
| `fix` | A bug fix changes existing behavior without adding a new capability. |
| `test` | Only `tests/**` changed. |
| `chore` | Workflow, packaging, or maintenance-only changes. |

For this spec set, the default implementation commit is:

```text
feat(pk): implement staged count pipeline

Spec-Source: specs/technical.md
```

The default specs-only commit is:

```text
specs(pk): regenerate staged count specifications

Spec-Source: specs/product.md
```

## Push & PR Policy

Push only after the pre-commit gates pass or after documenting why a gate could not run.

Use:

```text
git push -u origin <branch>
```

Open a PR for any pushed branch that changes `docs/**`, `specs/**`, `.sdd/**`, `src/**`, `tests/**`, or `pyproject.toml`.

PR target branch is `main`. PR title matches the commit subject. PR body format:

```text
## Summary
- <one to three bullets>

## Verification
- <gate result or reason not run>

Spec-Source: <primary spec path>
```

Use `gh pr view --head <branch>` to check for an existing PR. If no PR exists, use `gh pr create --base main --head <branch> --title "<commit subject>" --body "<body>"`. If an open PR already exists for the branch, update that PR instead of opening a duplicate.

## Pre-Commit Gates

Run these checks in order before committing implementation changes:

1. `python3 -m compileall src/oppp`
2. `ruff check src tests`
3. `ruff format --check src tests`
4. `pytest -q`
5. `git diff --check`

For specs-only or docs-only changes, run:

1. `git diff --check`

If a command cannot run because an optional local dependency is missing, record the exact command and failure in the PR verification section.

## Never Commit

- `.env`
- `.venv/**`
- `__pycache__/**`
- `.pytest_cache/**`
- `.ruff_cache/**`
- build outputs such as `build/**` and `dist/**`
- local credentials, API tokens, TERMite keys, PharmaPendium tokens, OpenAI keys, or Portkey keys
- generated private reports containing live PharmaPendium data unless explicitly requested by the user
- workbook replacements for `docs/PPPK.xlsx` unless the user explicitly asks to update the gold source

## Safety & Idempotency

- Start with `git status --short` and inspect the diff before staging.
- Do not revert unrelated user changes.
- Stage only files that belong to the current change.
- If there is nothing to commit, report that state and do not create an empty commit.
- If a branch exists, reuse it instead of creating a duplicate branch.
- If a push is rejected because the remote has moved, stop and report the rejection; do not force-push.
- If a PR already exists for the branch, update or reference the existing PR; do not open another.
