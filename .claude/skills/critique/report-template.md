# `critique` — Report template

The structure for `specs/critique/report{NN}.md`. The numbering and severity
vocabulary are defined in `../CONVENTIONS.md`.

```
# Critique Report {NN}

**Date**: {YYYY-MM-DD}
**Scope**: {files audited}

## Summary

| Severity | Count |
|----------|-------|
| BLOCKER  | N     |
| MAJOR    | N     |
| MINOR    | N     |
| QUESTION | N     |

## Findings

### BLOCKER — must be resolved before any implementation proceeds

#### B01 — {short title}
**Type**: {contradiction | constitution violation | missing info | assumption | code divergence}
**Location**: {file:section or file:line}
**Description**: {what is wrong}
**Impact**: {what breaks or misleads if this is not fixed}
**Resolution**: {what needs to change — which file, which section}

<!-- repeat for each BLOCKER -->

### MAJOR — significant gap that will cause rework if ignored

#### M01 — {short title}
<!-- same structure as BLOCKER -->

### MINOR — low-impact inconsistency or polish issue

#### MI01 — {short title}
<!-- same structure -->

### QUESTION — cannot be resolved without information from the user

#### Q01 — {short title}
**Missing information**: {exactly what is not known}
**Why it matters**: {what decision depends on this answer}
**Affects**: {which spec files need updating once answered}
**Options** (if applicable):
| Option | Implication |
|--------|-------------|
| A — … | … |
| B — … | … |

<!-- repeat for each QUESTION -->

## Recommended Resolution Order
<!-- Ordered list: BLOCKERs first, then MAJORs, then MINORs.
     QUESTIONs are listed separately — they block their dependents.
     The code-level subset (Type: code divergence / constitution violation) is the
     part /fix consumes when this report is dispatched to it via EXECUTE_COMMAND. -->
```
