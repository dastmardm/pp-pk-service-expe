# Git Workflow

## Sources
- `specs/constitution.md` → Quality Gates, CONST-10 (never commit secrets), CONST-11.
- Repository layout (`src/oppp/`, `tests/`, `inputs/`, `docs/`, `specs/`, `utils/`,
  `.claude/`) and observed history (Conventional-Commits-style subjects:
  `feat: …`, `feat(docs): …`, `feat(cli): …`; default branch `main`).
- `.gitignore` (already ignores `.env`).

## Branch Naming
First matching row wins (top to bottom). Base branch is always `main`.

| Change class | Path globs that trigger it | Branch pattern | Base |
|--------------|----------------------------|----------------|------|
| Docs | `docs/**` (excluding `docs/sme_stage_cases.csv`) | `docs/<slug>` | `main` |
| Specs | `specs/**` | `specs/<slug>` | `main` |
| Data / gold sets | `inputs/**`, `docs/sme_stage_cases.csv` | `data/<slug>` | `main` |
| Harness/config | `.claude/**`, `pyproject.toml`, `.gitignore`, `*.toml`, `.env.example` | `chore/<slug>` | `main` |
| Tests only | `tests/**` (and no `src/**`) | `test/<slug>` | `main` |
| Source — fix | `src/**` or `utils/**` when the work repairs an evaluation/critique finding | `fix/<slug>` | `main` |
| Source — feature | `src/**` or `utils/**` otherwise | `feat/<slug>` | `main` |

`<slug>` = kebab-case of the change summary (≤ 5 words), e.g. `feat/per-step-eval`,
`docs/streamlit-ui`, `specs/initial-blueprint`.

## Mixed-Change Rule
For a changeset spanning multiple classes, pick the branch by **highest
precedence**, top of this list winning:
`specs` > `src (fix)` > `src (feature)` > `data` > `docs` > `tests` > `chore`.
Rationale: route by the most review-sensitive surface touched. A changeset mixing
`src/**` and its own `tests/**` is a single `feat/`/`fix/` branch (tests travel
with their code). If a changeset mixes truly unrelated classes (e.g. `docs/**` +
`src/**` feature), prefer **splitting** into separate branches/commits; only
combine when the changes are interdependent.

## Commit Convention
- **Format:** Conventional Commits — `type(scope): subject`.
- **Types:** `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `perf`, `build`.
- **Scope (optional):** the touched area — `cli`, `stages`, `eval`, `services`,
  `taxonomy`, `ui`, `specs`, `docs`, `data`.
- **Subject:** imperative, ≤ 72 chars, no trailing period.
- **Mandatory trailer** on every commit:
  ```
  Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
  ```

## Push & PR Policy
- Never commit directly to `main`; always work on a branch per the table above.
- Push the branch with upstream tracking (`git push -u origin <branch>`).
- Open a PR (`gh pr create`) targeting `main` when the change is a complete unit of
  work and the Pre-Commit Gates pass.
- **PR title:** the primary commit subject (`type(scope): subject`).
- **PR body:** a short summary, the spec/eval items addressed (e.g. `REQ-023`,
  `EVAL-024`), how it was verified (gates run), and the trailer:
  ```
  🤖 Generated with [Claude Code](https://claude.com/claude-code)
  ```
- Spec-only or docs-only changes still go via a branch + PR for review trace.

## Pre-Commit Gates
Ordered; all MUST pass before a commit (mirror `constitution.md` → Quality Gates):
1. `ruff check src tests`
2. `ruff format --check src tests`
3. `pytest -q`  (offline; no network, no model credentials)

If a commit touches only `docs/**` or `specs/**` (no `src/**`/`tests/**`), gate 3
MAY be skipped (nothing executable changed); gates 1–2 still run if any `*.py`
changed.

## Never Commit
- `.env` and any real credential file (only `.env.example`, keys-only, is committed).
- Secrets/tokens of any kind (Portkey keys, TERMite credentials).
- Generated/cache artefacts: `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`,
  `.venv/`, build outputs.
- Large/binary blobs except the intentionally-tracked `docs/agent-dag.png`.
- Never use `git add -A`/`git add .`; stage explicit paths so ignored secrets
  cannot be swept in.

## Safety & Idempotency
- **Branch exists:** reuse it (checkout) rather than failing; do not force-recreate.
- **Nothing to commit:** report "clean" and exit 0; do not create an empty commit.
- **PR already open** for the branch: update it (`gh pr edit`/push) instead of
  opening a duplicate.
- **No force-push, no history rewrite** (`--force`, `-f`, `--force-with-lease`,
  `rebase`, `filter-branch`, `reset --hard origin/*` are denied in
  `.claude/settings.json`).
- Operate only within this repository; never touch other repos or the global git
  config.
