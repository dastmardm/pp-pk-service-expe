---
name: "fix"
description: "Repair the FAIL/PARTIAL findings in an evaluation report (or the code-divergence findings in a critique report), then re-evaluate. Use after /evaluation, or when /critique dispatches code-level findings."
argument-hint: "Path to an evaluation or critique report (default: most recent specs/evaluation/report*.md)"
user-invocable: true
disable-model-invocation: false
---

## User Input

```text
$ARGUMENTS
```

$ARGUMENTS is the path to the report to fix. If omitted, use the most recently created file matching `specs/evaluation/report*.md`.

## Outline

You are the **`fix`** step:

```
technical → implement → evaluation → fix
```

Repair the actionable findings in a report, then trigger a new evaluation to confirm the fixes hold.

You accept **two kinds of report** (the shared verdict/severity vocabularies are defined in `../CONVENTIONS.md`):

- **Evaluation report** (`specs/evaluation/report*.md`, the default) — fix every
  `FAIL` and `PARTIAL` finding, in the order given under its `## Recommended Fix Order`.
- **Critique report** (`specs/critique/report*.md`, handed over when `/critique` emits
  `EXECUTE_COMMAND: fix specs/critique/report{NN}.md`) — fix only the **code-level**
  findings, i.e. those with **Type: code divergence** or **constitution violation**
  (severities `BLOCKER`/`MAJOR`/`MINOR`), in the order given under its
  `## Recommended Resolution Order`. **Skip `QUESTION` findings and any purely
  spec-level finding** — those are not `/fix`'s job; `/critique` routes them elsewhere.

### Steps

1. Locate the report: use $ARGUMENTS if given, otherwise pick the highest-numbered
   `specs/evaluation/report*.md`.
   Stop with an error if no report exists — run `/evaluation` (or `/critique`) first.

2. Determine the report type from its path/heading (Evaluation Report vs Critique
   Report) and read it, plus the spec files it evaluated or audited against.

3. Read every file referenced in the findings you will act on (FAIL/PARTIAL for an
   evaluation report; code-divergence / constitution-violation findings for a critique report).

4. Fix the findings in the order the report lists them — `## Recommended Fix Order`
   (evaluation: every FAIL/PARTIAL) or `## Recommended Resolution Order` (critique:
   walk only the `code divergence` / `constitution violation` entries; skip QUESTION
   and spec-only findings):
   - Address the exact gap described in each finding — do not refactor surrounding code unless it is the root cause
   - Verify each fix does not break callers (grep for callers of any changed function/symbol)
   - If a fix requires a new migration, make it idempotent and follow the naming convention in `specs/skeleton.md` → Conventions
   - If a fix introduces a new env var, add it to the env template file specified in `specs/technical.md` → Configuration and Secrets

5. Do **not** attempt code fixes for `BLOCKED` findings (evaluation reports only —
   a critique report has no `BLOCKED` verdict; its `BLOCKER`-severity findings ARE
   fixed normally). A
   `BLOCKED` finding means the *criterion itself* is defective — the fix belongs in
   `specs/evaluation.md`, not the code. Surface it: state that `specs/evaluation.md`
   must be corrected via `/technical` before re-evaluation is meaningful, and do not
   guess the criterion's intent.

6. For any other finding that cannot be fixed (blocked by a design constraint or
   external dependency), document it clearly with the reason.

7. Trigger re-evaluation — **unless** there were no fixable code findings (e.g. the
   report contained only `BLOCKED` criteria-defects, or only `QUESTION`/spec-level
   critique findings). In that case skip the re-run and say why, so the chain does not
   re-audit against still-broken criteria. Otherwise emit (see `../CONVENTIONS.md`
   → EXECUTE_COMMAND):

   ```
   EXECUTE_COMMAND: evaluation
   ```

8. Report: findings fixed (by finding ID — F01/P01 for an evaluation report,
   B01/M01/MI01 for a critique report), findings not fixed (with reason), any
   `BLOCKED` criteria-defects surfaced for `/technical`, and files modified.
