---
name: "issue"
description: "Fix a bug the user found while testing the running system themselves, verify it, get the user to confirm it is truly fixed, then reflect the change into docs/ via /docs. Use when the user reports something they observed is broken or behaves wrong and asks for it to be fixed — e.g. \"I tried X and it did Y, should be Z\", \"this is broken\", \"found a bug\", \"fix this issue\"."
argument-hint: "A description of the problem found while testing: what you did, what you expected, and what actually happened (plus repro steps / command / service if relevant)"
user-invocable: true
disable-model-invocation: false
---

## User Input

```text
$ARGUMENTS
```

`$ARGUMENTS` is a free-text **bug report from the user's own testing** — what they
did, what they expected, and what actually happened. It is not an evaluation report;
the user is the person who observed the problem, so **the user — not a passing test
suite — is the authority on whether it is fixed.** If `$ARGUMENTS` is empty or too
vague to act on, ask once, up front, for the missing detail (repro steps, the exact
command/UI action, the service, the observed vs expected behaviour) before changing code.

## Outline

You are the **`issue`** skill. It is a small, human-in-the-loop repair loop that sits
**beside** the spec pipeline (it is not a forward-chain step):

```
user finds a bug while testing
        │
        ▼
   diagnose → fix → verify → ASK THE USER TO CONFIRM
        ▲                              │
        └────── not fixed ─────────────┤
                                       │ confirmed
                                       ▼
                                    /docs   (reflect the change in human-facing docs)
```

Repair the reported defect at its root, prove the symptom is gone, **pause and get the
user's explicit confirmation**, and only then propagate the now-true behaviour into the
documentation via `/docs`. This skill writes **source code, the env template, and tests**
and **never runs git** (`../CONVENTIONS.md` → Worker discipline / Write scopes); staging
is `/git`'s job. The chain handoff to `/docs` is the only `EXECUTE_COMMAND` it emits, and
**only after the user confirms** (`../CONVENTIONS.md` → EXECUTE_COMMAND).

This is an **interactive** skill (`../CONVENTIONS.md` → Interactive vs autonomous): it is
*designed* to converse with the user mid-run. See **Autonomous-mode fallback** below for
how it must behave when it cannot reach the user (under `/flow`, in a dispatched subagent,
or when told "don't stop to ask").

### Phase A — diagnose, fix, verify, then ask (runs on `/issue`)

1. **Understand the report.** Read `$ARGUMENTS`. Restate the defect in one line:
   *action → expected → actual*. If a required detail is missing and the bug cannot be
   located without it, ask the user **once** now (do not guess the repro).

2. **Reproduce first.** Before editing anything, reproduce the reported behaviour with
   the smallest real exercise that triggers it — run the relevant CLI command, the offline
   pipeline, the UI path, or a focused script. Capture the wrong output as the *before*
   evidence. **If you cannot reproduce it**, say so plainly and ask the user for exact
   repro steps rather than fixing a symptom you cannot see — a fix you cannot verify is not
   a fix.

3. **Find the root cause.** Read the implicated code and trace it to the actual cause, not
   the surface symptom. Grep for callers/usages of any symbol you suspect so you understand
   the blast radius before touching it.

4. **Fix it — minimal and at the root.** Change the smallest set of files that removes the
   cause. Honour the project's rules while you do (`specs/constitution.md`): typed Pydantic
   boundaries (CONST-3), grounding over generation (CONST-1), per-service data lives in
   config not stage code (CONST-12), the offline doubles stay hermetic (CONST-8), etc. Do
   **not** refactor unrelated code, add abstractions, or add backwards-compat shims. If the
   fix introduces a new env var, add it (keys only) to the env template named in
   `specs/technical.md` → Configuration and Secrets. **Never run git.**

5. **Lock the bug down with a test.** Add or extend an **offline** test under `tests/` that
   fails on the old behaviour and passes on the fixed one, so the defect cannot silently
   return (CONST-8/9: no network, no model creds in the default suite). If the bug is
   genuinely not unit-testable offline (e.g. a live-API or external-NER-only path), say so
   and rely on the user's confirmation instead.

6. **Verify.** Run the project's Quality Gates (`specs/constitution.md` → Quality Gates):
   `ruff check src tests`, `ruff format --check src tests`, `pytest -q`. Then **re-run the
   repro from step 2** and confirm the wrong output is gone. Report the *before → after*
   evidence and every file you changed.

7. **Ask the user to confirm — and STOP.** Pose a clear, direct question: *"I believe this
   is fixed — here's the before/after. Can you re-test on your side and confirm the issue is
   truly resolved?"* Do **not** emit any `EXECUTE_COMMAND`, do **not** run `/docs`, and do
   **not** assume confirmation. End the turn and wait for the user's reply. (A passing suite
   is necessary but not sufficient — the user observed the bug, so the user closes it.)

### Phase B — on the user's reply

Phase A ended with a question, so the next user message is their verdict. Read it:

- **Confirmed fixed** ("yes", "works now", "confirmed") → the behaviour the docs describe
  has changed, so reflect it. Emit, as the **last line** of your output, the dispatch
  directive (`../CONVENTIONS.md` → EXECUTE_COMMAND) with a concise description of the
  behaviour change for the docs to capture:

  ```
  EXECUTE_COMMAND: docs <one-line description of the fixed/changed behaviour>
  ```

  `/docs` will update `docs/**` only. (If the user explicitly says the fix needs no doc
  change — e.g. it was a pure internal defect with no user-visible behaviour change — skip
  the directive and say why; offer `/git` to commit instead.)

- **Not fixed / partially fixed / different now** → treat their feedback as new evidence.
  Return to Phase A step 2 with the added detail: reproduce the *remaining* problem, adjust
  the fix, re-verify, and **ask again**. Loop until the user confirms. Do not advance to
  `/docs` while the user says the issue persists.

## Autonomous-mode fallback

When this skill is run **unattended** — under `/flow`, inside a dispatched subagent, or
when the user said "don't stop to ask" — it cannot block on the Phase A step 7 confirmation.
In that case: do steps 1–6 (diagnose, fix, test, verify), then **stop before `/docs`** and
report the fix as **unconfirmed**, listing the before/after evidence and the exact
confirmation question a human still needs to answer. **Never auto-run `/docs` without
confirmation** — documentation must reflect behaviour a human has verified, not a fix the
model only believes works. (`../CONVENTIONS.md` → Autonomous-mode contract.)

## Notes

- **Scope.** This skill fixes a *reported* defect and then documents it. It does not
  re-derive the specs. If the confirmed change is a genuine product/behaviour change that
  should ripple into `specs/` and beyond, the path after `/docs` is the normal chain:
  `/technical` → `/implement` (mention this as a suggestion; do not run it here).
- **It never commits.** Branch/commit/PR is `/git`'s job, run separately after the docs
  change lands.
- **One question budget in Phase A.** Ask up front only for what you truly need to locate
  the bug; everything else is the confirmation question at the end.
