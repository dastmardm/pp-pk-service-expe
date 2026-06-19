---
name: "git"
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
specs/git.md  (the rules)  ──▶  /git  ──▶  git / gh commands
```

### Steps

1. **Read the rules.** Read `specs/git.md`.
   Stop with an error if it does not exist — run `/technical` first to produce it.
   Treat every section (Branch Naming, Mixed-Change Rule, Commit Convention, Push & PR Policy, Pre-Commit Gates, Never Commit, Safety & Idempotency) as binding. Do not invent rules it does not state; do not skip rules it does state.

2. **Inspect the changes.** Run `git status --porcelain` and `git rev-parse --abbrev-ref HEAD` to see the changed paths and the current branch. If a path scope was given in $ARGUMENTS, restrict to matching paths. If there is nothing to commit, stop and say so (per the Safety & Idempotency rule).

3. **Classify the change.** Match the changed paths against the path globs in the Branch Naming table to determine the change class and the target branch name (filling any `<name>` slot from $ARGUMENTS or a concise derived name). If the changeset spans multiple classes, apply the Mixed-Change Rule exactly as written.

4. **Run the pre-commit gates.** Execute every check in the Pre-Commit Gates section. If any fails, stop and report which gate failed and its output — do not commit. Verify nothing in the "Never Commit" list is staged.

5. **Create / switch to the branch.** Follow the Branch Naming and base-branch rules. Honour Safety & Idempotency: if the branch already exists, reuse it rather than erroring; never commit directly to a protected base branch.

6. **Commit.** Stage the in-scope changes and commit using the exact Commit Convention format from `specs/git.md`, including any mandatory trailer it requires.

7. **Push / open a PR.** Follow the Push & PR Policy. Only push or open a PR if the rules say to. Use `gh` for PRs with the title/body format and target branch the policy specifies, including any required PR-body trailer. If a PR is already open for the branch, update rather than duplicate (per Safety & Idempotency).

8. **Report.** State: the change class detected, the branch used (created or reused), the commit SHA and message, whether a push/PR happened (with the PR URL if so), and any gate that blocked the action.

### Rules

- **Obey `specs/git.md` literally.** Every branch name, commit shape, and PR decision comes from that file — you apply, you do not improvise.
- **Confirm before outward-facing actions.** Pushing a branch or opening a PR publishes work; do it because `specs/git.md` directs it, and surface the result. If the rules are ambiguous for the current diff, ask rather than guess.
- **Be idempotent.** Re-running `/git` on an unchanged tree, an existing branch, or an open PR must be a safe no-op or an update — never a duplicate or an error.
- **Never bypass a gate.** A failing pre-commit gate or a "Never Commit" hit stops the commit; report it instead of forcing the change through.
