---
name: "fix"
description: "Repair the FAIL/PARTIAL findings in an evaluation report (or the code-divergence findings in a critique report), then re-evaluate and propagate the change into the docs via /docs. Use after /evaluation, or when /critique dispatches code-level findings."
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

8. Report (**always emit this, even when nothing was re-evaluated**): produce a
   structured summary of what changed. This summary is consumed later to update the
   project documents, so make it self-contained and specific — do not assume the
   reader has the report or the diff in front of them. Include:
   - **Findings fixed** — by finding ID (F01/P01 for an evaluation report,
     B01/M01/MI01 for a critique report), each with a one-line description of the
     gap and how it was resolved.
   - **Findings not fixed** — with the reason (design constraint, external
     dependency, etc.).
   - **`BLOCKED` criteria-defects** surfaced for `/technical`, if any.
   - **Change summary** — a concise, behaviour-level account of what the code now
     does differently: new/changed functions or symbols, new migrations, new env
     vars, altered interfaces or contracts, and any other change that the project
     documentation would need to reflect. Group it so it can be mapped onto the
     affected docs/specs.
   - **Files modified** — the list of files touched.

9. **Propagate the change into the documentation.** Every fix this skill applies
   changes behaviour that the human-facing docs must end up reflecting — so hand the
   **Change summary** from step 8 to `/docs`. Build a self-contained, docs-focused
   prompt from that summary (not the raw report or diff): describe what the code now
   does differently in behaviour-level terms, so `/docs` can locate the right
   `docs/**` files and update them. Then emit, as the **last line of output** (see
   `../CONVENTIONS.md` → EXECUTE_COMMAND):

   ```
   EXECUTE_COMMAND: docs <one-paragraph, self-contained description of the behaviour change to document>
   ```

   **Ordering — only the last line of output fires.** The harness intercepts a single
   `EXECUTE_COMMAND` directive (the last line). To run both the re-evaluation (step 7)
   and the docs propagation, **chain them**: emit the step-7 `EXECUTE_COMMAND: evaluation`
   directive *only* when re-evaluation is warranted, and make the docs hand-off happen
   **after the chain settles** rather than competing for the same final line —
   - When re-evaluation IS warranted: do **not** emit the docs directive on this turn.
     Instead, end this turn with `EXECUTE_COMMAND: evaluation`, and state in the report
     that once evaluation confirms the fixes hold, the change must be documented via
     `/docs` using the Change summary above. (The re-evaluation chain reaches `/docs`
     once it converges; documentation should describe the *final* fixed state, not an
     interim one.)
   - When re-evaluation is **skipped** (no fixable code findings re-ran, per step 7):
     there is no competing directive, so emit `EXECUTE_COMMAND: docs <summary>` as the
     last line directly — but only if at least one fix actually changed behaviour. If
     nothing changed (e.g. only `BLOCKED` criteria-defects or `QUESTION`/spec-level
     findings), there is nothing to document — skip the docs directive and say why.

   Skip the docs hand-off entirely when no code fix was applied — there is no behaviour
   change to reflect.
