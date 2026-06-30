# Tasks

## Overview
The WBS implements row-level runtime closed-set filtering without disturbing the
existing count-only path.

```text
W1 (root) - Runtime closed-set post-filtering
  W1.1 (summary) - Contracts, execution, and filtering
    W1.1.1 (leaf) - Typed runtime contracts
    W1.1.2 (leaf) - Row execution
    W1.1.3 (leaf) - Runtime translation
    W1.1.4 (leaf) - Post-filter aggregation
  W1.2 (summary) - Orchestration and surfaces
    W1.2.1 (leaf) - Pipeline two-pass orchestration
    W1.2.2 (leaf) - CLI row/runtime output
    W1.2.3 (leaf) - Streamlit runtime inspection
  W1.3 (summary) - Evaluation and tests
    W1.3.1 (leaf) - Per-step/runtime evaluation
    W1.3.2 (leaf) - Count harness compatibility
    W1.3.3 (leaf) - Runtime post-filter tests
    W1.3.4 (leaf) - Pipeline regression tests
    W1.3.5 (leaf) - Stage regression tests
    W1.3.6 (leaf) - Eval regression tests
    W1.3.7 (leaf) - Per-step comparator tests
```

## Nodes

### W1 - Runtime closed-set post-filtering
- **Type**: root
- **Parent**: none
- **Children**: W1.1, W1.2, W1.3
- **Owns**: none
- **After**: none
- **Review**: `python3 -m compileall src/oppp`, `ruff check src tests`,
  `ruff format --check src tests`, and `pytest -q` pass; an offline pipeline run
  still produces a valid count-only machine query; a mocked row run reports
  runtime closed-set metadata and filtered datapoints.
- **Done-when**: every child reports success and the Review assertions hold.

### W1.1 - Contracts, execution, and filtering
- **Type**: summary
- **Parent**: W1
- **Children**: W1.1.1, W1.1.2, W1.1.3, W1.1.4
- **Owns**: none
- **After**: none
- **Review**: runtime models import cleanly; row execution returns typed row
  results; runtime translation returns only selected values from supplied runtime
  closed sets; post-filtering records applied and invalid runtime filters.
- **Done-when**: all children resolve and the Review holds.

### W1.1.1 - Typed runtime contracts
- **Type**: leaf
- **Parent**: W1.1
- **Children**: none
- **Owns**: `src/oppp/models.py`
- **REQ**: REQ-001, REQ-011, REQ-012, REQ-013, REQ-014
- **After**: none
- **Done-when**: `models.py` exposes typed contracts for row execution, runtime
  closed sets, runtime translation/post-filter results, and extends
  `PipelineResult` without removing existing fields.

### W1.1.2 - Row execution
- **Type**: leaf
- **Parent**: W1.1
- **Children**: none
- **Owns**: `src/oppp/execute.py`
- **REQ**: REQ-011, REQ-015, REQ-024
- **After**: W1.1.1
- **Done-when**: `execute_count` remains compatible and `execute_rows` returns
  typed datapoint rows or a structured error, with bounded fetch options.

### W1.1.3 - Runtime translation
- **Type**: leaf
- **Parent**: W1.1
- **Children**: none
- **Owns**: `src/oppp/stages/translate.py`
- **REQ**: REQ-006, REQ-007, REQ-008, REQ-009, REQ-012, REQ-013, REQ-014, REQ-020
- **After**: W1.1.1
- **Done-when**: Stage 2 exposes a runtime translation entry point that accepts
  an open-field component plus runtime values, reuses the closed-set resolution
  order, returns only runtime-set members, and marks empty/out-of-set selections
  invalid.

### W1.1.4 - Post-filter aggregation
- **Type**: leaf
- **Parent**: W1.1
- **Children**: none
- **Owns**: `src/oppp/stages/aggregate.py`
- **REQ**: REQ-010, REQ-014, REQ-015
- **After**: W1.1.3
- **Done-when**: aggregation can hold open-set filters aside for row mode, apply
  valid runtime post-filters to datapoints, preserve zero-count probes for
  count-only mode, and emit validation issues for invalid runtime filters.

### W1.2 - Orchestration and surfaces
- **Type**: summary
- **Parent**: W1
- **Children**: W1.2.1, W1.2.2, W1.2.3
- **Owns**: none
- **After**: W1.1
- **Review**: pipeline, CLI, and UI all expose row/runtime metadata while
  existing payload-only, no-execute, and count execution workflows keep working.
- **Done-when**: all children resolve and the Review holds.

### W1.2.1 - Pipeline two-pass orchestration
- **Type**: leaf
- **Parent**: W1.2
- **Children**: none
- **Owns**: `src/oppp/pipeline.py`
- **REQ**: REQ-001, REQ-011, REQ-012, REQ-013, REQ-014, REQ-015, REQ-021
- **After**: none
- **Done-when**: `run_pipeline` can run count-only as today or row mode: defer
  open filters, aggregate valid input closed-set filters, fetch rows, build
  runtime closed sets, translate runtime filters, post-filter rows, and return
  all metadata.

### W1.2.2 - CLI row/runtime output
- **Type**: leaf
- **Parent**: W1.2
- **Children**: none
- **Owns**: `src/oppp/cli.py`
- **REQ**: REQ-017, REQ-021, REQ-024
- **After**: W1.2.1
- **Done-when**: CLI flags/output can request row/runtime mode and display row
  execution, runtime selections, invalid runtime translations, and final filtered
  count without breaking existing `--payload-only`, `--execute`, and
  `--no-execute` behavior.

### W1.2.3 - Streamlit runtime inspection
- **Type**: leaf
- **Parent**: W1.2
- **Children**: none
- **Owns**: `src/oppp/ui/app.py`
- **REQ**: REQ-018, REQ-021
- **After**: W1.2.1
- **Done-when**: the UI shows Stage -1 expansion, row execution status, runtime
  closed-set selections, invalid runtime filters, and filtered datapoint count
  when row mode is available.

### W1.3 - Evaluation and tests
- **Type**: summary
- **Parent**: W1
- **Children**: W1.3.1, W1.3.2, W1.3.3, W1.3.4, W1.3.5, W1.3.6, W1.3.7
- **Owns**: none
- **After**: W1.2
- **Review**: every test module owned by this subtree passes under `pytest -q`;
  per-step evaluation still reads `docs/sme_stage_cases.csv`; count harness
  metrics remain compatible.
- **Done-when**: all children resolve and the Review holds.

### W1.3.1 - Per-step/runtime evaluation
- **Type**: leaf
- **Parent**: W1.3
- **Children**: none
- **Owns**: `src/oppp/eval/per_step.py`
- **REQ**: REQ-019, REQ-020, REQ-023
- **After**: none
- **Done-when**: per-step comparators account for runtime post-filter metadata
  where available and preserve existing termite/decompose/translate/machine-query
  comparisons.

### W1.3.2 - Count harness compatibility
- **Type**: leaf
- **Parent**: W1.3
- **Children**: none
- **Owns**: `src/oppp/eval/harness.py`
- **REQ**: REQ-019, REQ-015
- **After**: none
- **Done-when**: `oppp eval --no-execute` and count execution continue to report
  valid/executed/exact/within-tolerance metrics, and row-mode metadata does not
  break report export.

### W1.3.3 - Runtime post-filter tests
- **Type**: leaf
- **Parent**: W1.3
- **Children**: none
- **Owns**: `tests/test_runtime_post_filters.py`
- **REQ**: REQ-011, REQ-012, REQ-013, REQ-014, REQ-015
- **After**: W1.3.1
- **Done-when**: mocked datapoint rows prove runtime closed-set derivation,
  valid post-filtering, invalid-no-narrowing behavior, and count-probe fallback.

### W1.3.4 - Pipeline regression tests
- **Type**: leaf
- **Parent**: W1.3
- **Children**: none
- **Owns**: `tests/test_pipeline.py`
- **REQ**: REQ-001, REQ-002, REQ-010, REQ-021
- **After**: W1.3.3
- **Done-when**: pipeline tests cover both existing offline count-only behavior
  and row-mode runtime metadata without network calls.

### W1.3.5 - Stage regression tests
- **Type**: leaf
- **Parent**: W1.3
- **Children**: none
- **Owns**: `tests/test_stages.py`
- **REQ**: REQ-003, REQ-004, REQ-005, REQ-006, REQ-007, REQ-008, REQ-009, REQ-020
- **After**: W1.3.3
- **Done-when**: stage tests cover closed-set failure handling, Q7 OR retrieval,
  Q18 MTD, Q20 Ames Test, Q23 Monkeys, Q24 ADC, and Q25 Columvi.

### W1.3.6 - Eval regression tests
- **Type**: leaf
- **Parent**: W1.3
- **Children**: none
- **Owns**: `tests/test_eval.py`
- **REQ**: REQ-019, REQ-021
- **After**: W1.3.2
- **Done-when**: eval tests prove report export and no-execute metrics remain
  stable after runtime metadata is added.

### W1.3.7 - Per-step comparator tests
- **Type**: leaf
- **Parent**: W1.3
- **Children**: none
- **Owns**: `tests/test_per_step_eval.py`
- **REQ**: REQ-019, REQ-020, REQ-023
- **After**: W1.3.1
- **Done-when**: per-step tests load the resolved `docs/sme_stage_cases.csv`,
  exercise comparator behavior, and stub any judge path so the suite is hermetic.

## Cross-tree dependencies
None. Same-parent `After` edges express the required order.
