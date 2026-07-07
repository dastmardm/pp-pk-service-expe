# Tasks

## Overview
The WBS fixes the product path, removes public stage options/no-op bypasses, and
adds row-level runtime closed-set post-filtering.

```text
W1 (root) - Fixed TERMite runtime closed-set pipeline
  W1.1 (summary) - Contracts, config, and normalization
    W1.1.1 (leaf) - Runtime contracts
    W1.1.2 (leaf) - Required configuration
    W1.1.3 (leaf) - Fixed normalizer policy
  W1.2 (summary) - Service and registry boundaries
    W1.2.1 (leaf) - Registry limited to non-stage use
    W1.2.2 (leaf) - Service schema
    W1.2.3 (leaf) - Service configs
  W1.3 (summary) - Fixed stages and execution
    W1.3.1 (leaf) - Fixed LLM expansion
    W1.3.2 (leaf) - Required TERMite enhancement
    W1.3.3 (leaf) - Fixed LLM decomposition
    W1.3.4 (leaf) - Input and runtime translation
    W1.3.5 (leaf) - Aggregation and post-filtering
    W1.3.6 (leaf) - Count and row execution
    W1.3.7 (leaf) - Stage exports
  W1.4 (summary) - Orchestration and surfaces
    W1.4.1 (leaf) - Pipeline fixed path
    W1.4.2 (leaf) - CLI fixed controls
    W1.4.3 (leaf) - Streamlit fixed controls
    W1.4.4 (leaf) - Diagram export
  W1.5 (summary) - Evaluation and tests
    W1.5.1 (leaf) - Per-step evaluation
    W1.5.2 (leaf) - Evaluation harness
    W1.5.3 (leaf) - Gold comparison and judge
    W1.5.4 (leaf) - Test fakes and fixtures
    W1.5.5 (leaf) - Pipeline tests
    W1.5.6 (leaf) - Stage tests
    W1.5.7 (leaf) - Runtime post-filter tests
    W1.5.8 (leaf) - Eval harness tests
    W1.5.9 (leaf) - Per-step tests
    W1.5.10 (leaf) - Normalizer tests
    W1.5.11 (leaf) - Service tests
    W1.5.12 (leaf) - Taxonomy tests
    W1.5.13 (leaf) - CLI tests
    W1.5.14 (leaf) - Diagram tests
```

## Nodes

### W1 - Fixed TERMite runtime closed-set pipeline
- **Type**: root
- **Parent**: none
- **Children**: W1.1, W1.2, W1.3, W1.4, W1.5
- **Owns**: none
- **After**: none
- **Review**: `python3 -m compileall src/oppp`, `ruff check src tests`,
  `ruff format --check src tests`, and `pytest -q` pass; public help/UI no
  longer expose stage method or normalizer choices; mocked row execution reports
  runtime closed-set metadata and filtered datapoints.
- **Done-when**: every child reports success and the Review assertions hold.

### W1.1 - Contracts, config, and normalization
- **Type**: summary
- **Parent**: W1
- **Children**: W1.1.1, W1.1.2, W1.1.3
- **Owns**: none
- **After**: none
- **Review**: core imports work without optional packages; runtime contracts,
  required settings, and fixed normalization helpers import cleanly.
- **Done-when**: all children resolve and the Review holds.

### W1.1.1 - Runtime contracts
- **Type**: leaf
- **Parent**: W1.1
- **Children**: none
- **Owns**: `src/oppp/models.py`
- **REQ**: REQ-001, REQ-013, REQ-014, REQ-015, REQ-016
- **After**: none
- **Done-when**: `models.py` exposes typed row execution, runtime closed-set,
  runtime translation/post-filter, and extended `PipelineResult` contracts
  without removing existing machine-query fields.

### W1.1.2 - Required configuration
- **Type**: leaf
- **Parent**: W1.1
- **Children**: none
- **Owns**: `src/oppp/config.py`, `.env.example`
- **REQ**: REQ-003, REQ-025
- **After**: none
- **Done-when**: config reads TERMite/model secrets lazily at invocation, full-run
  missing config produces actionable errors, and `.env.example` is keys-only and
  labels TERMite/model settings as required for full runs.

### W1.1.3 - Fixed normalizer policy
- **Type**: leaf
- **Parent**: W1.1
- **Children**: none
- **Owns**: `src/oppp/normalize/base.py`, `src/oppp/normalize/strategies.py`, `src/oppp/normalize/__init__.py`
- **REQ**: REQ-005, REQ-010
- **After**: none
- **Done-when**: normalization is exposed as one fixed field/bucket policy with
  no public `noop` or normalizer registry selection, and valid class labels remain
  protected from fuzzy correction.

### W1.2 - Service and registry boundaries
- **Type**: summary
- **Parent**: W1
- **Children**: W1.2.1, W1.2.2, W1.2.3
- **Owns**: none
- **After**: W1.1
- **Review**: services remain configurable by data, while stage modules no longer
  depend on registries for public method selection.
- **Done-when**: all children resolve and the Review holds.

### W1.2.1 - Registry limited to non-stage use
- **Type**: leaf
- **Parent**: W1.2
- **Children**: none
- **Owns**: `src/oppp/registry.py`
- **REQ**: REQ-005, REQ-018
- **After**: none
- **Done-when**: registry documentation and use support service configuration or
  internal factories only, and no public stage method selection relies on it.

### W1.2.2 - Service schema
- **Type**: leaf
- **Parent**: W1.2
- **Children**: none
- **Owns**: `src/oppp/services/base.py`, `src/oppp/services/__init__.py`
- **REQ**: REQ-018
- **After**: none
- **Done-when**: `ServiceConfig`/`FieldSpec` expose buckets, runtime open-field
  metadata, facets, display columns, entity routing, invariants, and serializers
  needed by the fixed pipeline.

### W1.2.3 - Service configs
- **Type**: leaf
- **Parent**: W1.2
- **Children**: none
- **Owns**: `src/oppp/services/safety.py`, `src/oppp/services/pk.py`, `src/oppp/services/rtb.py`
- **REQ**: REQ-018
- **After**: W1.2.2
- **Done-when**: Safety, PK, and RTB define their field buckets, TERMite type
  maps, entity routes, facets, display columns, invariants, and RTB serializer
  without moving service-specific maps into shared stages.

### W1.3 - Fixed stages and execution
- **Type**: summary
- **Parent**: W1
- **Children**: W1.3.1, W1.3.2, W1.3.3, W1.3.4, W1.3.5, W1.3.6, W1.3.7
- **Owns**: none
- **After**: W1.2
- **Review**: fixed stage functions import cleanly; no stage file exports a public
  no-op backend; row execution and runtime post-filter helpers operate on typed
  contracts.
- **Done-when**: all children resolve and the Review holds.

### W1.3.1 - Fixed LLM expansion
- **Type**: leaf
- **Parent**: W1.3
- **Children**: none
- **Owns**: `src/oppp/stages/expand.py`
- **REQ**: REQ-002, REQ-005, REQ-024
- **After**: none
- **Done-when**: expansion has one product method, preserves `original`, reports
  LLM unavailability as an issue/error, and tests can inject a fake structured
  model without a public no-op expander.

### W1.3.2 - Required TERMite enhancement
- **Type**: leaf
- **Parent**: W1.3
- **Children**: none
- **Owns**: `src/oppp/stages/enhance.py`
- **REQ**: REQ-003, REQ-005, REQ-024, REQ-025
- **After**: none
- **Done-when**: Stage 0 exposes required TERMite enhancement only, raises clear
  configuration/dependency errors, and supports fake TERMite clients in tests
  without a public no-op enhancer.

### W1.3.3 - Fixed LLM decomposition
- **Type**: leaf
- **Parent**: W1.3
- **Children**: none
- **Owns**: `src/oppp/stages/decompose.py`
- **REQ**: REQ-004, REQ-005, REQ-006, REQ-011, REQ-024
- **After**: W1.3.2
- **Done-when**: decomposition has one product LLM path, remains vocab-free,
  uses TERMite annotations for reconciliation, and removes public gazetteer
  selection while keeping private test fakes possible.

### W1.3.4 - Input and runtime translation
- **Type**: leaf
- **Parent**: W1.3
- **Children**: none
- **Owns**: `src/oppp/stages/translate.py`
- **REQ**: REQ-006, REQ-007, REQ-008, REQ-009, REQ-010, REQ-011, REQ-014, REQ-015, REQ-016, REQ-023
- **After**: W1.3.3
- **Done-when**: Stage 2 exposes fixed input and runtime translation functions,
  implements the closed-set resolution order with membership feedback/retry, and
  never emits values outside the supplied input or runtime closed set.

### W1.3.5 - Aggregation and post-filtering
- **Type**: leaf
- **Parent**: W1.3
- **Children**: none
- **Owns**: `src/oppp/stages/aggregate.py`
- **REQ**: REQ-006, REQ-009, REQ-012, REQ-016, REQ-017
- **After**: W1.3.4
- **Done-when**: Stage 3 aggregates only valid input translations, validates the
  first query, applies service invariants/output requests, and filters datapoints
  only for valid runtime selections.

### W1.3.6 - Count and row execution
- **Type**: leaf
- **Parent**: W1.3
- **Children**: none
- **Owns**: `src/oppp/execute.py`
- **REQ**: REQ-013, REQ-017, REQ-026
- **After**: W1.3.5
- **Done-when**: `execute_count` remains compatible and `execute_rows` returns
  typed datapoint rows or structured unavailable/error results with bounded fetch
  options.

### W1.3.7 - Stage exports
- **Type**: leaf
- **Parent**: W1.3
- **Children**: none
- **Owns**: `src/oppp/stages/__init__.py`
- **REQ**: REQ-005
- **After**: W1.3.6
- **Done-when**: package stage exports expose fixed stage helpers only and do not
  export public registries or no-op/product-alternate backends.

### W1.4 - Orchestration and surfaces
- **Type**: summary
- **Parent**: W1
- **Children**: W1.4.1, W1.4.2, W1.4.3, W1.4.4
- **Owns**: none
- **After**: W1.3
- **Review**: pipeline, CLI, UI, and diagram surfaces expose the fixed path and
  runtime metadata without stage backend or normalizer selectors.
- **Done-when**: all children resolve and the Review holds.

### W1.4.1 - Pipeline fixed path
- **Type**: leaf
- **Parent**: W1.4
- **Children**: none
- **Owns**: `src/oppp/pipeline.py`
- **REQ**: REQ-001, REQ-005, REQ-013, REQ-014, REQ-015, REQ-016, REQ-017, REQ-024, REQ-026
- **After**: none
- **Done-when**: `run_pipeline` accepts service/execution/fetch controls only,
  always runs the fixed stage path, defers open filters for row mode, derives
  runtime closed sets, translates runtime filters, post-filters rows, and returns
  all metadata.

### W1.4.2 - CLI fixed controls
- **Type**: leaf
- **Parent**: W1.4
- **Children**: none
- **Owns**: `src/oppp/cli.py`
- **REQ**: REQ-005, REQ-019, REQ-026
- **After**: W1.4.1
- **Done-when**: CLI commands run fixed methods, show row/runtime metadata, and
  no command help exposes old `--enhancer`, `--decomposer`, `--translator`,
  `--aggregator`, or `--normalizer` selectors.

### W1.4.3 - Streamlit fixed controls
- **Type**: leaf
- **Parent**: W1.4
- **Children**: none
- **Owns**: `src/oppp/ui/app.py`
- **REQ**: REQ-005, REQ-020, REQ-026
- **After**: W1.4.1
- **Done-when**: the UI shows fixed-path stage output, execution status, runtime
  closed sets, invalid runtime filters, and filtered datapoint count without
  backend selector widgets.

### W1.4.4 - Diagram export
- **Type**: leaf
- **Parent**: W1.4
- **Children**: none
- **Owns**: `src/oppp/dag.py`
- **REQ**: REQ-021
- **After**: W1.4.1
- **Done-when**: diagram export mirrors the draw.io fixed pipeline and contains
  no pluggable-backend legend or registry-derived stage method list.

### W1.5 - Evaluation and tests
- **Type**: summary
- **Parent**: W1
- **Children**: W1.5.1, W1.5.2, W1.5.3, W1.5.4, W1.5.5, W1.5.6, W1.5.7, W1.5.8, W1.5.9, W1.5.10, W1.5.11, W1.5.12, W1.5.13, W1.5.14
- **Owns**: none
- **After**: W1.4
- **Review**: all promised tests pass under `pytest -q` without `.env`, network,
  model credentials, or TERMite credentials; tests use fakes/fixtures rather than
  public product bypasses.
- **Done-when**: all children resolve and the Review holds.

### W1.5.1 - Per-step evaluation
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `src/oppp/eval/per_step.py`
- **REQ**: REQ-022, REQ-023, REQ-027
- **After**: none
- **Done-when**: per-step comparators account for TERMite, decomposition,
  translation, machine-query, per-field, and runtime post-filter metadata while
  preserving typed judge hooks for semantic ties.

### W1.5.2 - Evaluation harness
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `src/oppp/eval/harness.py`
- **REQ**: REQ-017, REQ-022, REQ-026
- **After**: W1.5.1
- **Done-when**: `oppp eval --no-execute` and count execution continue to report
  valid/executed/exact/within-tolerance metrics, and row-mode metadata does not
  break report export.

### W1.5.3 - Gold comparison and judge
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `src/oppp/eval/compare.py`, `src/oppp/eval/judge.py`
- **REQ**: REQ-022, REQ-027
- **After**: W1.5.1
- **Done-when**: per-field gold comparison understands runtime/post-filter
  metadata and the typed judge remains injectable for hermetic tests.

### W1.5.4 - Test fakes and fixtures
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/conftest.py`
- **REQ**: REQ-024
- **After**: none
- **Done-when**: shared fixtures provide fake LLM, fake TERMite, fake row/count
  API, and fixed-pipeline helpers without invoking external services.

### W1.5.5 - Pipeline tests
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/test_pipeline.py`
- **REQ**: REQ-001, REQ-002, REQ-005, REQ-013, REQ-014, REQ-015, REQ-016, REQ-017, REQ-024, REQ-026
- **After**: W1.5.4
- **Done-when**: pipeline tests cover fixed-path orchestration, missing config
  errors, count-only compatibility, row-mode runtime metadata, and no public
  method selectors.

### W1.5.6 - Stage tests
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/test_stages.py`
- **REQ**: REQ-002, REQ-003, REQ-004, REQ-005, REQ-006, REQ-007, REQ-008, REQ-009, REQ-010, REQ-011, REQ-023, REQ-024
- **After**: W1.5.4
- **Done-when**: stage tests cover required TERMite, fixed LLM seams with fakes,
  closed-set failure handling, Q7 OR retrieval, Q18 MTD, Q20 Ames Test, Q23
  Monkeys, Q24 ADC, and Q25 Columvi.

### W1.5.7 - Runtime post-filter tests
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/test_runtime_post_filters.py`
- **REQ**: REQ-013, REQ-014, REQ-015, REQ-016, REQ-026
- **After**: W1.5.4
- **Done-when**: mocked datapoint rows prove runtime closed-set derivation,
  valid post-filtering, invalid-no-narrowing behavior, and row execution failure
  reporting.

### W1.5.8 - Eval harness tests
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/test_eval.py`
- **REQ**: REQ-017, REQ-022, REQ-024
- **After**: W1.5.2, W1.5.4
- **Done-when**: eval tests prove report export, no-execute metrics, count
  compatibility, and hermetic fake execution.

### W1.5.9 - Per-step tests
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/test_per_step_eval.py`
- **REQ**: REQ-022, REQ-023, REQ-027
- **After**: W1.5.1, W1.5.4
- **Done-when**: per-step tests load `docs/sme_stage_cases.csv`, exercise
  comparator behavior, and stub any judge path.

### W1.5.10 - Normalizer tests
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/test_normalize.py`
- **REQ**: REQ-010, REQ-024
- **After**: W1.5.4
- **Done-when**: normalizer tests prove fixed policy behavior, class-label
  preservation, typo correction, and no public normalizer selection.

### W1.5.11 - Service tests
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/test_services.py`
- **REQ**: REQ-018, REQ-024
- **After**: W1.5.4
- **Done-when**: service tests verify Safety/PK/RTB configs, invariants, entity
  routes, and absence of service-specific maps in shared stages.

### W1.5.12 - Taxonomy tests
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/test_taxonomy.py`
- **REQ**: REQ-007, REQ-008, REQ-011, REQ-024
- **After**: W1.5.4
- **Done-when**: taxonomy tests verify exact/fuzzy lookup, class labels,
  colloquial groups, candidate windows, and subset-grounding helpers.

### W1.5.13 - CLI tests
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/test_cli.py`
- **REQ**: REQ-005, REQ-019, REQ-024, REQ-026
- **After**: W1.5.4
- **Done-when**: CLI tests assert old method-selection flags are absent and fixed
  commands show row/runtime output with faked pipeline/execution.

### W1.5.14 - Diagram tests
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/test_dag.py`
- **REQ**: REQ-021, REQ-024
- **After**: W1.5.4
- **Done-when**: diagram tests assert the export reflects the fixed draw.io flow
  and contains no pluggable-backend legend or registry-derived method list.

## Cross-tree dependencies
None. Same-parent `After` edges express the required order.
