---
name: "evaluation"
description: "Audit the code against the EVAL-NNN criteria in specs/evaluation.md and write a numbered gap report. Use as the evaluation step of the spec pipeline, after /implement and before /fix."
argument-hint: "Path to the evaluation criteria (default: specs/evaluation.md); optional scope filter"
user-invocable: true
disable-model-invocation: false
---

## User Input

```text
$ARGUMENTS
```

$ARGUMENTS may give the path to the evaluation criteria file and/or a scope filter. Default: `specs/evaluation.md`.

## Outline

You are the **`evaluation`** step:

```
technical → implement → evaluation → fix
```

This is the **HOW** half of the evaluation contract. `/technical` produces `specs/evaluation.md` — the **WHAT**: the authoritative, objectively-decidable list of criteria (`EVAL-NNN`) to verify. Your job is to apply each of those criteria to the codebase and produce an objective gap report. Every finding is a concrete, actionable discrepancy tied to a criterion ID — not an opinion, and never a check you invented outside `specs/evaluation.md`.

The criteria are the single source of truth for *what* gets checked: you do **not** re-derive requirements from the other specs. If a criterion is ambiguous or unverifiable, that is a defect in `specs/evaluation.md` — record it as a `BLOCKED` finding (see step 4) rather than guessing intent. `BLOCKED` is an **evaluation-side escape hatch** for defective criteria, not a verdict the criteria schema in `specs/evaluation.md` declares (the verdict/severity vocabularies are defined in `../CONVENTIONS.md`).

### Steps

1. Read the evaluation criteria file in $ARGUMENTS (default `specs/evaluation.md`).
   Stop with an error if it does not exist — run `/technical` first to produce it.
   Read its `## Sources` lineage only as supporting context to interpret a criterion's evidence column — never to add checks beyond the listed `EVAL-NNN`.

2. Explore the codebase to find the implementation files each criterion's `Evidence to look for` points at.

3. Determine the next report number (see `../CONVENTIONS.md` → Report numbering):
   - List files matching `specs/evaluation/report*.md`
   - Next number = highest existing report index + 1, zero-padded to 2 digits
     (so the first report is `report01.md`; deleting an interim report never causes a collision)
   - `mkdir -p specs/evaluation` if needed

4. For **each `EVAL-NNN` criterion** in `specs/evaluation.md` (filtered to the scope, if given), inspect the codebase for the evidence it names and record exactly one verdict:
   - `PASS` — the named evidence is present and satisfies the criterion exactly
   - `PARTIAL` — partially satisfied; describe precisely what is missing
   - `FAIL` — the criterion is not met; describe the exact discrepancy
   - `N/A` — the criterion's Out-of-Scope condition applies; cite it
   - `BLOCKED` — the criterion itself is ambiguous, unverifiable, or contradicts another; the defect is in `specs/evaluation.md`, not the code

   Carry each criterion's `Severity` (BLOCKER/MAJOR/MINOR) through to the finding — it drives the fix order. Evaluate every criterion; do not skip silently. A criterion with no matching code is a `FAIL`, not an omission.

5. Write `specs/evaluation/report{NN}.md`:

   ```
   # Evaluation Report {NN}

   **Date**: {YYYY-MM-DD}
   **Criteria**: specs/evaluation.md ({total} EVAL criteria)
   **Scope**: {all | scope filter}

   ## Summary
   | Status  | Count |
   |---------|-------|
   | PASS    | N     |
   | PARTIAL | N     |
   | FAIL    | N     |
   | N/A     | N     |
   | BLOCKED | N     |

   **Coverage**: {evaluated}/{total} criteria assessed.
   <!-- MUST equal total unless a scope filter was applied; list any unassessed IDs and why. -->

   ## Findings
   <!-- Each finding cites the EVAL-NNN it came from and carries its Severity. -->

   ### FAIL
   #### F01 — {EVAL-NNN} — {short title}  ·  Severity: {BLOCKER|MAJOR|MINOR}
   **Criterion**: {verbatim Criterion text from specs/evaluation.md}
   **Found**: {what the code actually does}
   **File**: {path:line}
   **Fix**: {one-sentence description of the fix needed}

   ### PARTIAL
   #### P01 — {EVAL-NNN} — {short title}  ·  Severity: {BLOCKER|MAJOR|MINOR}
   **Criterion**: {verbatim Criterion text}
   **Found**: {what is implemented vs. missing}
   **File**: {path:line}
   **Fix**: {what remains}

   ### BLOCKED
   #### B01 — {EVAL-NNN} — {short title}
   **Criterion**: {verbatim Criterion text}
   **Why blocked**: {ambiguous / unverifiable / contradicts EVAL-MMM — defect is in specs/evaluation.md}

   ### PASS
   <!-- bullet list: EVAL-NNN | criterion | evidence (file:line) -->

   ### N/A
   <!-- bullet list: EVAL-NNN | Out-of-Scope reason cited from specs/evaluation.md -->

   ## Recommended Fix Order
   <!-- ordered finding IDs: BLOCKER-severity FAIL/PARTIAL first, then MAJOR, then MINOR.
        BLOCKED items go to the top of a separate "Fix the criteria first" note,
        since they must be resolved in specs/evaluation.md before re-evaluation. -->
   ```

6. Report: path written, PASS/PARTIAL/FAIL/N/A/BLOCKED counts, coverage ({evaluated}/{total}), and top BLOCKER findings. If any criteria are BLOCKED, flag that `specs/evaluation.md` needs fixing (re-run `/technical`) before the report is fully actionable. Next step: `/fix specs/evaluation/report{NN}.md`.
