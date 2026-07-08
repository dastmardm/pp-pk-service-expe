---
name: "mdgit"
description: "Apply the project's git/gh workflow from specs/git.md to the current changes. Use after a pipeline step changed files, or when asked to branch, commit, push, or open a PR."
argument-hint: "Optional: a short name for the change, or a path scope (default: act on the whole working-tree diff)"
user-invocable: true
disable-model-invocation: false
---

## User Input

```text
$ARGUMENTS
```

$ARGUMENTS is optional. It may give a short human name for the change (used to fill the `<short-kebab-name>` slot in a branch) and/or a path scope to limit which changes you act on. If empty, act on the entire working-tree diff and derive the name yourself.

## Outline

You are the **git** step. You do **not** decide the workflow — `specs/git.md` does. Your only job is to read those rules and apply them to the current changes with `git` and `gh` commands. `specs/git.md` is the **WHAT**; you are the **HOW**.

```
specs/git.md  (the rules)  ──▶  /mdgit  ──▶  git / gh commands
```

### Steps

1. **Read the rules.** Read `specs/git.md`.
   Stop with an error if it does not exist — run `/mdtechnical` first to produce it.
   Treat every section (Branch Naming, Mixed-Change Rule, Commit Convention, Push & PR Policy, Pre-Commit Gates, Never Commit, Safety & Idempotency) as binding. Do not invent rules it does not state; do not skip rules it does state.

2. **Inspect the changes.** Run `git status --porcelain` and `git rev-parse --abbrev-ref HEAD` to see the changed paths and the current branch. If a path scope was given in $ARGUMENTS, restrict to matching paths. If there is nothing to commit, stop and say so (per the Safety & Idempotency rule).

3. **Sweep for junk files and update `.gitignore`.** Run this **every time**, before classifying — never assume the working tree is clean.
   - List candidates with `git status --porcelain --ignored` (the `??` untracked entries and the `!!` already-ignored entries) plus `git ls-files --others --exclude-standard`.
   - Classify each untracked path as **source** (intended for the repo) or **junk** (machine-generated, environment-local, or otherwise never meant to be tracked). Junk includes, but is not limited to: language caches and build artefacts (`__pycache__/`, `*.py[cod]`, `*.egg-info/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `node_modules/`, `dist/`, `build/`, `target/`), virtualenvs (`.venv/`, `venv/`), coverage and tooling output (`.coverage`, `htmlcov/`, `.tox/`), OS/editor cruft (`.DS_Store`, `Thumbs.db`, `desktop.ini`, `*.swp`, `*.swo`, `*~`, `.idea/`, `.vscode/`), and stray logs/temp/backup files (`*.log`, `*.tmp`, `*.bak`). When unsure whether a path is source or junk, treat it as source and leave `.gitignore` alone.
   - For every junk path **not already matched** by an existing `.gitignore` entry, add the narrowest correct pattern (prefer a directory/glob like `**/__pycache__/` over an absolute one-off path) to `.gitignore`, grouping it under the relevant existing comment block or a new one. Do not duplicate or reorder existing entries; this step is idempotent — a tree with no new junk leaves `.gitignore` untouched.
   - The "Never Commit" list governs secrets, not junk: if a candidate is a secret it must be ignored **and** must never be staged, regardless of this sweep.
   - If `.gitignore` changed, it is now part of the changeset and feeds the next step. Per the Mixed-Change Rule, a `.gitignore` hygiene fix that rides along with infra/spec work stays on the infra/spec branch; it only forces a `security/<name>` branch when the gitignore fix is the primary concern.

4. **Classify the change.** Match the changed paths against the path globs in the Branch Naming table to determine the change class and the target branch name (filling any `<name>` slot from $ARGUMENTS or a concise derived name). If the changeset spans multiple classes, apply the Mixed-Change Rule exactly as written.

5. **Run the pre-commit gates.** Execute every check in the Pre-Commit Gates section. If any fails, stop and report which gate failed and its output — do not commit. Verify nothing in the "Never Commit" list is staged, and that no junk file flagged in the sweep slipped into the staged set.

6. **Create / switch to the branch.** Follow the Branch Naming and base-branch rules. Honour Safety & Idempotency: if the branch already exists, reuse it rather than erroring; never commit directly to a protected base branch.

7. **Commit.** Stage the in-scope changes and commit using the exact Commit Convention format from `specs/git.md`, including any mandatory trailer it requires.

8. **Push / open a PR.** Follow the Push & PR Policy. Only push or open a PR if the rules say to. Use `gh` for PRs with the title/body format and target branch the policy specifies, including any required PR-body trailer. If a PR is already open for the branch, update rather than duplicate (per Safety & Idempotency).

9. **Report.** State: the change class detected, the branch used (created or reused), any `.gitignore` updates made by the junk sweep, the commit SHA and message, whether a push/PR happened (with the PR URL if so), and any gate that blocked the action.

### Rules

- **Obey `specs/git.md` literally.** Every branch name, commit shape, and PR decision comes from that file — you apply, you do not improvise.
- **Confirm before outward-facing actions.** Pushing a branch or opening a PR publishes work; do it because `specs/git.md` directs it, and surface the result. If the rules are ambiguous for the current diff, ask rather than guess.
- **Be idempotent.** Re-running `/mdgit` on an unchanged tree, an existing branch, or an open PR must be a safe no-op or an update — never a duplicate or an error. The junk sweep is part of this: a tree with no new junk must leave `.gitignore` byte-for-byte unchanged.
- **Always sweep for junk first.** Every run checks for new machine-generated/junk files and extends `.gitignore` before classifying or committing — never let caches, build artefacts, virtualenvs, or OS/editor cruft reach the staged set. When a path's nature is ambiguous, treat it as source and leave `.gitignore` alone.
- **Never bypass a gate.** A failing pre-commit gate or a "Never Commit" hit stops the commit; report it instead of forcing the change through.
