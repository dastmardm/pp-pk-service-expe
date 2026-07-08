# Tasks

## Overview

Implement the staged PK count pipeline through the existing package boundaries, then update public surfaces and tests to use the shared `final_row_count` contract.

```text
W1 (root) - staged PK count pipeline
  W1.1 (summary) - contracts and field metadata
    W1.1.1 (leaf) - runtime result contracts
    W1.1.2 (leaf) - PK field buckets and threshold
  W1.2 (summary) - stage behavior
    W1.2.1 (leaf) - decomposition and field-scoped TERMite
    W1.2.2 (leaf) - staged translation
    W1.2.3 (leaf) - staged aggregation and row filters
  W1.3 (summary) - orchestration and execution
    W1.3.1 (leaf) - count and row execution helpers
    W1.3.2 (leaf) - production staged pipeline
  W1.4 (summary) - public surfaces and evaluation
    W1.4.1 (leaf) - CLI staged output
    W1.4.2 (leaf) - Streamlit staged UI
    W1.4.3 (leaf) - PK_Query exact-count evaluation
  W1.5 (summary) - tests
    W1.5.1 (leaf) - service and stage tests
    W1.5.2 (leaf) - pipeline and evaluation tests
```

## Nodes

### W1 - Staged PK count pipeline
- **Type**: root
- **Parent**: none
- **Children**: W1.1, W1.2, W1.3, W1.4, W1.5
- **Owns**: none
- **Contributors**: none
- **After**: none
- **Review**: The union of child outputs matches `specs/skeleton.md`, all owned files appear exactly once, and the quality gates in `specs/constitution.md` are run after implementation.
- **Done-when**: CLI, UI, and evaluation all consume the same staged pipeline result with `final_row_count`.

### W1.1 - Contracts and field metadata
- **Type**: summary
- **Parent**: W1
- **Children**: W1.1.1, W1.1.2
- **Owns**: none
- **Contributors**: none
- **After**: none
- **Review**: The runtime models and PK service metadata agree on bucket names, threshold value, `studyGroups` spelling, staged attempts, execution mode, and `final_row_count`.
- **Done-when**: Stage, orchestration, surface, and evaluation work can import the updated contracts without optional credentials.

### W1.1.1 - Runtime result contracts
- **Type**: leaf
- **Parent**: W1.1
- **Children**: none
- **Owns**: `src/oppp/models.py`
- **Contributors**: none
- **REQ**: REQ-003, REQ-011, REQ-017
- **After**: none
- **Done-when**: Models expose component fields, staged attempt/runtime fields, execution mode, and `final_row_count` with serializable defaults.

### W1.1.2 - PK field buckets and threshold
- **Type**: leaf
- **Parent**: W1.1
- **Children**: none
- **Owns**: `src/oppp/services/base.py`, `src/oppp/services/pk.py`
- **Contributors**: none
- **REQ**: REQ-005, REQ-006, REQ-007, REQ-023
- **After**: none
- **Done-when**: PK service metadata exposes `small_closed`, `closed`, `open`, `enum`, and `boolean`; threshold is `1000`; early fields and `studyGroups` match the requirements.

### W1.2 - Stage behavior
- **Type**: summary
- **Parent**: W1
- **Children**: W1.2.1, W1.2.2, W1.2.3
- **Owns**: none
- **Contributors**: none
- **After**: W1.1
- **Review**: Decomposition, enrichment, translation, and aggregation exchange the updated typed contracts and do not require pipeline orchestration to validate their local behavior.
- **Done-when**: Stage functions can produce early and non-early translated batches, staged aggregate queries, and row-filter results.

### W1.2.1 - Decomposition and field-scoped TERMite
- **Type**: leaf
- **Parent**: W1.2
- **Children**: none
- **Owns**: `src/oppp/stages/decompose.py`, `src/oppp/stages/enhance.py`
- **Contributors**: none
- **REQ**: REQ-002, REQ-003, REQ-004
- **After**: none
- **Done-when**: Decomposition runs before enrichment, and component-level TERMite enrichment receives each component's `field` and `nl_fragment`.

### W1.2.2 - Staged translation
- **Type**: leaf
- **Parent**: W1.2
- **Children**: none
- **Owns**: `src/oppp/stages/translate.py`
- **Contributors**: none
- **REQ**: REQ-008, REQ-009
- **After**: W1.2.1
- **Done-when**: Translation can return an early-only batch, deterministic non-early batches, and pending component metadata.

### W1.2.3 - Staged aggregation and row filters
- **Type**: leaf
- **Parent**: W1.2
- **Children**: none
- **Owns**: `src/oppp/stages/aggregate.py`
- **Contributors**: none
- **REQ**: REQ-010, REQ-011, REQ-015, REQ-016
- **After**: W1.2.2
- **Done-when**: Aggregation can run after any translation batch, validates PK payloads, applies invariants, and locally filters fetched rows with structured issues.

### W1.3 - Orchestration and execution
- **Type**: summary
- **Parent**: W1
- **Children**: W1.3.1, W1.3.2
- **Owns**: none
- **Contributors**: none
- **After**: W1.2
- **Review**: The pipeline orchestrator uses the execution helpers, stage outputs, strict count threshold, and final count contract without duplicating stage logic.
- **Done-when**: Both row-filter and full-API-count modes are reachable and observable in `PipelineResult`.

### W1.3.1 - Count and row execution helpers
- **Type**: leaf
- **Parent**: W1.3
- **Children**: none
- **Owns**: `src/oppp/execute.py`
- **Contributors**: none
- **REQ**: REQ-012, REQ-013, REQ-014
- **After**: none
- **Done-when**: Count and row retrieval helpers return structured results that can be recorded by staged pipeline attempts.

### W1.3.2 - Production staged pipeline
- **Type**: leaf
- **Parent**: W1.3
- **Children**: none
- **Owns**: `src/oppp/pipeline.py`
- **Contributors**: none
- **REQ**: REQ-001, REQ-012, REQ-013, REQ-014, REQ-017, REQ-025
- **After**: W1.3.1
- **Done-when**: `run_pipeline` executes the documented staged order and sets `final_row_count` from row filtering or the final API count.

### W1.4 - Public surfaces and evaluation
- **Type**: summary
- **Parent**: W1
- **Children**: W1.4.1, W1.4.2, W1.4.3
- **Owns**: none
- **Contributors**: none
- **After**: W1.3
- **Review**: CLI, UI, and evaluation use `PipelineResult.final_row_count` and do not call a separate count path that bypasses the production pipeline.
- **Done-when**: User-visible output and evaluation reports expose execution mode and final row count consistently.

### W1.4.1 - CLI staged output
- **Type**: leaf
- **Parent**: W1.4
- **Children**: none
- **Owns**: `src/oppp/cli.py`
- **Contributors**: none
- **REQ**: REQ-018
- **After**: none
- **Done-when**: `oppp run --execute` reports final row count and execution mode, and CLI stage labels match the documented order.

### W1.4.2 - Streamlit staged UI
- **Type**: leaf
- **Parent**: W1.4
- **Children**: none
- **Owns**: `src/oppp/ui/app.py`
- **Contributors**: none
- **REQ**: REQ-019
- **After**: none
- **Done-when**: The UI shows decomposition reasons, component TERMite annotations, staged attempts, execution mode, final count, and row-filter counts from the production result.

### W1.4.3 - PK_Query exact-count evaluation
- **Type**: leaf
- **Parent**: W1.4
- **Children**: none
- **Owns**: `src/oppp/eval/harness.py`, `src/oppp/eval/compare.py`
- **Contributors**: none
- **REQ**: REQ-020, REQ-021, REQ-022
- **After**: W1.4.1, W1.4.2
- **Done-when**: Evaluation loads only `PK_Query`, scores exact final counts, and exports count-only report columns.

### W1.5 - Tests
- **Type**: summary
- **Parent**: W1
- **Children**: W1.5.1, W1.5.2
- **Owns**: none
- **Contributors**: none
- **After**: W1.4
- **Review**: Tests cover service metadata, stages, orchestration, evaluation, offline behavior, and threshold boundaries without live credentials.
- **Done-when**: `pytest -q` passes with the updated count-only staged pipeline expectations.

### W1.5.1 - Service and stage tests
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/test_services.py`, `tests/test_stages.py`
- **Contributors**: none
- **REQ**: REQ-004, REQ-005, REQ-006, REQ-007, REQ-008, REQ-009, REQ-010, REQ-015, REQ-016, REQ-024
- **After**: none
- **Done-when**: Service and stage tests assert bucket metadata, field-scoped enrichment, staged translation, aggregation, and row-filter behavior using fakes.

### W1.5.2 - Pipeline and evaluation tests
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/test_pipeline.py`, `tests/test_eval.py`, `tests/test_per_step_eval.py`
- **Contributors**: none
- **REQ**: REQ-001, REQ-012, REQ-013, REQ-014, REQ-017, REQ-018, REQ-019, REQ-020, REQ-021, REQ-022, REQ-024, REQ-025
- **After**: none
- **Done-when**: Pipeline and evaluation tests cover stage order, `999`/`1000`/`1001`, final row count, public-surface expectations, and removal or repurposing of legacy per-step evaluation tests.

## Cross-tree dependencies

None.
