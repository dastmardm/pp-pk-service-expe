# Evaluation Criteria

## Sources

- `specs/product.md`
- `specs/technical.md`
- `specs/constitution.md`
- `specs/requirements.md`
- `specs/plan.md`
- `specs/skeleton.md`

## How to read this file

Each criterion is an objectively decidable check over the codebase and generated specs. `/mdevaluation` assigns PASS, PARTIAL, FAIL, N/A, or BLOCKED and cites file:line evidence. This file defines what must be true; it does not prescribe a worker execution order.

## Criteria

| ID | Source ref | Category | Criterion (objectively decidable) | Evidence to look for | Severity |
| --- | --- | --- | --- | --- | --- |
| EVAL-001 | REQ-001, CONST-2 | Requirement | The production PK orchestration runs expansion before decomposition, decomposition before field-scoped TERMite enrichment, early translation before the first count, and uses the `1000` count gate before row filtering or further translation. | `src/oppp/pipeline.py` control flow and `tests/test_pipeline.py` assertions for stage order. | BLOCKER |
| EVAL-002 | REQ-002, REQ-003, Data contract: Decomposition | Data contract | Decomposition components contain `field`, `nl_fragment`, `type`, `reason`, `source`, and optional boolean grouping, and expansion preserves the original question separately from expanded text. | `Component` and expansion/decomposition models in `src/oppp/models.py`; tests in `tests/test_stages.py`. | BLOCKER |
| EVAL-003 | REQ-004, CONST-4 | Requirement | TERMite enrichment used by the PK pipeline is component-scoped: each call receives the component `field` and `nl_fragment`, and production orchestration does not use global pre-decomposition TERMite hints. | `src/oppp/stages/enhance.py`, `src/oppp/pipeline.py`, tests with multiple fields/fragments in `tests/test_stages.py`. | BLOCKER |
| EVAL-004 | REQ-005, REQ-006, CONST-3, Data contract: Field Buckets | Data contract | PK service metadata exposes bucket values `small_closed`, `closed`, `open`, `enum`, and `boolean`; `EARLY_CONTRIBUTOR_THRESHOLD` is `1000`; early fields are exactly `species`, `routes`, `documentSource`, and `documentYear`; `drugs` is closed but not early. | `src/oppp/services/base.py`, `src/oppp/services/pk.py`, `tests/test_services.py`. | BLOCKER |
| EVAL-005 | REQ-007, CONST-3 | Requirement | Generated PK field names, facets, row filtering, CLI/UI display, and tests use documented `studyGroups`; any accepted singular `studyGroup` input is normalized or aliased to `studyGroups`. | `src/oppp/services/pk.py`, `src/oppp/stages/aggregate.py`, `src/oppp/cli.py`, `src/oppp/ui/app.py`, related tests. | MAJOR |
| EVAL-006 | REQ-008, REQ-009, CONST-5 | Requirement | Translation exposes deterministic staged selection: first batch contains all and only early filter components, later batches translate pending non-early components when the count remains `>= 1000`, and pending components are tracked. | `src/oppp/stages/translate.py`, `src/oppp/pipeline.py`, tests in `tests/test_stages.py` and `tests/test_pipeline.py`. | BLOCKER |
| EVAL-007 | REQ-010, CONST-5 | Requirement | Aggregation can run after every staged translation set, preserves boolean groups, applies PK invariant constraints, validates fields/facets, enforces the query budget, and records issues. | `src/oppp/stages/aggregate.py`, tests in `tests/test_stages.py`. | BLOCKER |
| EVAL-008 | REQ-011, Data contract: Advanced Search Payload | Data contract | `MachineQuery.to_payload()` emits required top-level keys `query`, `entityFilters`, `facets`, `sortColumns`, `displayColumns`, `leafOnly`, `mixtureExpansion`, and `limitation`, with field constraints normalized into the payload shape used for execution. | `src/oppp/models.py`, `src/oppp/stages/aggregate.py`, payload tests. | BLOCKER |
| EVAL-009 | REQ-012, REQ-013, REQ-014, CONST-6 | Requirement | Every staged count uses `execute_count`, records query and `countTotal`, branches to `execute_rows` plus local filtering for counts `< 1000`, and continues staged non-early translation for counts `>= 1000` while pending filters remain. | `src/oppp/pipeline.py`, `src/oppp/execute.py`, fake execution tests in `tests/test_pipeline.py`. | BLOCKER |
| EVAL-010 | REQ-013, REQ-015, REQ-016, Data contract: Row Filtering | Requirement | Local row filtering applies remaining filters after a `< 1000` count and records input row count, applied filters, output row count, and unsupported-filter warnings/errors. | `src/oppp/stages/aggregate.py` or row-filter helper, `src/oppp/pipeline.py`, row-filter tests. | BLOCKER |
| EVAL-011 | REQ-017, CONST-7, Data contract: Runtime Execution | Data contract | `PipelineResult` exposes expanded query, decomposition, field-scoped annotations, translated subqueries, staged attempts, per-attempt counts, execution mode, fetched/filtered rows when used, `final_row_count`, validation issues, and execution issues. | `src/oppp/models.py`, serialization tests in `tests/test_pipeline.py`. | BLOCKER |
| EVAL-012 | REQ-018 | Requirement | `oppp run --execute` uses the production staged pipeline and displays `final_row_count` and execution mode; stage labels no longer describe TERMite as pre-decomposition Stage 0. | `src/oppp/cli.py`, CLI tests or Typer runner assertions. | MAJOR |
| EVAL-013 | REQ-019 | Requirement | The Streamlit UI consumes the production pipeline result and displays decomposition reasons, component TERMite annotations, staged count attempts, execution mode, final row count, and row-filter counts when available. | `src/oppp/ui/app.py`, UI code assertions or tests. | MAJOR |
| EVAL-014 | REQ-020, REQ-021, CONST-8 | Requirement | Evaluation reads only `docs/PPPK.xlsx` sheet `PK_Query`, uses columns `Quety number`, `Query`, and `Expected Count`, and scores only exact `final_row_count == Expected Count`; `execute=False` is offline/debug and not scored as exact-count evaluation. | `src/oppp/eval/harness.py`, `src/oppp/eval/compare.py`, `tests/test_eval.py`. | BLOCKER |
| EVAL-015 | REQ-022 | Requirement | Evaluation report exports contain count-only case columns: query number, question, expected count, final row count, execution mode, exact match, issues, and execution error; tolerance/per-step score columns are not required for scored output. | `src/oppp/eval/harness.py`, report tests in `tests/test_eval.py`. | MAJOR |
| EVAL-016 | REQ-023, CONST-10 | Non-functional | Importing package modules does not read live PharmaPendium, OpenAI/Portkey, or TERMite credentials; missing credentials fail only when the corresponding live stage is invoked. | `src/oppp/config.py`, stage modules, import/config tests. | MAJOR |
| EVAL-017 | REQ-024, NFR-003, CONST-10 | Non-functional | The default test suite uses deterministic fakes or monkeypatching and does not require network access, LLM credentials, TERMite credentials, PharmaPendium credentials, Streamlit, matplotlib, or openpyxl except where tests explicitly skip optional dependencies. | Tests under `tests/`, optional imports guarded by skips. | MAJOR |
| EVAL-018 | REQ-025, CONST-9 | Architecture | Staged execution is implemented through the existing `oppp` package modules and no second PK-only runner, service process, database, or alternate production pipeline stack is introduced. | Repo tree, `src/oppp/pipeline.py`, absence of new duplicate runner/service modules. | MAJOR |
| EVAL-019 | REQ-026 | Requirement | Existing CSV/XLSX report export and stage inspection commands remain available when optional dependencies are installed and do not alter the count-only scored metric. | `src/oppp/cli.py`, `src/oppp/eval/harness.py`, report tests. | MINOR |
| EVAL-020 | NFR-001, CONST-12 | Non-functional | The required quality gates pass: `python3 -m compileall src/oppp`, `ruff check src tests`, `ruff format --check src tests`, and `pytest -q`. | Command results from the implementation branch. | BLOCKER |
| EVAL-021 | NFR-004, CONST-6 | Non-functional | Tests cover boundary counts `999`, `1000`, and `1001`, proving `< 1000` enters row filtering and `>= 1000` continues staged translation or final API count. | `tests/test_pipeline.py` fake count tests. | BLOCKER |
| EVAL-022 | CONST-1 | Constitution | Implementation behavior that affects product semantics traces to docs-derived specs rather than source-only assumptions; no source or test expectation contradicts `specs/product.md` on staged flow, field buckets, or evaluation scope. | Comparison of source/tests with `specs/product.md` and `specs/requirements.md`. | MAJOR |
| EVAL-023 | CONST-11 | Constitution | Pipeline runtime state preserves expanded text, decomposition reasons, per-component TERMite annotations, translated subqueries, staged attempts, execution mode, row-filter counts, and issues for debugging. | `src/oppp/models.py`, `src/oppp/pipeline.py`, UI/CLI display code. | MAJOR |
| EVAL-024 | Skeleton/Structure | Skeleton/Structure | Every file listed in `specs/skeleton.md` exists at the documented path and has exactly one matching owner in `specs/tasks.md`; no owned file appears twice. | `specs/skeleton.md`, `specs/tasks.md`, filesystem paths. | BLOCKER |
| EVAL-025 | Plan | Skeleton/Structure | The implementation follows the plan's boundary decisions: contracts before stages, stages before orchestration, orchestration before public surfaces/evaluation, and tests updated for the new expectations. | `specs/plan.md`, git diff ordering or final file changes. | MINOR |

## Coverage Map

| Source item | Covered by |
| --- | --- |
| REQ-001 | EVAL-001, EVAL-009, EVAL-011 |
| REQ-002 | EVAL-002 |
| REQ-003 | EVAL-002 |
| REQ-004 | EVAL-003 |
| REQ-005 | EVAL-004 |
| REQ-006 | EVAL-004 |
| REQ-007 | EVAL-005 |
| REQ-008 | EVAL-006 |
| REQ-009 | EVAL-006 |
| REQ-010 | EVAL-007 |
| REQ-011 | EVAL-008 |
| REQ-012 | EVAL-009 |
| REQ-013 | EVAL-009, EVAL-010 |
| REQ-014 | EVAL-009, EVAL-021 |
| REQ-015 | EVAL-010 |
| REQ-016 | EVAL-010 |
| REQ-017 | EVAL-011, EVAL-023 |
| REQ-018 | EVAL-012 |
| REQ-019 | EVAL-013 |
| REQ-020 | EVAL-014 |
| REQ-021 | EVAL-014 |
| REQ-022 | EVAL-015 |
| REQ-023 | EVAL-016 |
| REQ-024 | EVAL-017 |
| REQ-025 | EVAL-018 |
| REQ-026 | EVAL-019 |
| NFR-001 | EVAL-020 |
| NFR-002 | EVAL-016 |
| NFR-003 | EVAL-017 |
| NFR-004 | EVAL-021 |
| NFR-005 | EVAL-010 |
| NFR-006 | EVAL-011 |
| CONST-1 | EVAL-022 |
| CONST-2 | EVAL-001 |
| CONST-3 | EVAL-004, EVAL-005 |
| CONST-4 | EVAL-003 |
| CONST-5 | EVAL-006, EVAL-007 |
| CONST-6 | EVAL-009, EVAL-021 |
| CONST-7 | EVAL-011 |
| CONST-8 | EVAL-014 |
| CONST-9 | EVAL-008, EVAL-018 |
| CONST-10 | EVAL-016, EVAL-017 |
| CONST-11 | EVAL-023 |
| CONST-12 | EVAL-020 |
| Data contract: Decomposition | EVAL-002 |
| Data contract: Field Buckets | EVAL-004 |
| Data contract: Runtime Execution | EVAL-011 |
| Data contract: Evaluation | EVAL-014, EVAL-015 |
| Data contract: Advanced Search Payload | EVAL-008 |
| Data contract: Row Filtering | EVAL-010 |
| `src/oppp/models.py` | EVAL-002, EVAL-008, EVAL-011, EVAL-023, EVAL-024 |
| `src/oppp/services/base.py` | EVAL-004, EVAL-024 |
| `src/oppp/services/pk.py` | EVAL-004, EVAL-005, EVAL-024 |
| `src/oppp/stages/decompose.py` | EVAL-002, EVAL-003, EVAL-024 |
| `src/oppp/stages/enhance.py` | EVAL-003, EVAL-024 |
| `src/oppp/stages/translate.py` | EVAL-006, EVAL-024 |
| `src/oppp/stages/aggregate.py` | EVAL-007, EVAL-008, EVAL-010, EVAL-024 |
| `src/oppp/execute.py` | EVAL-009, EVAL-024 |
| `src/oppp/pipeline.py` | EVAL-001, EVAL-009, EVAL-011, EVAL-018, EVAL-023, EVAL-024 |
| `src/oppp/cli.py` | EVAL-012, EVAL-019, EVAL-024 |
| `src/oppp/ui/app.py` | EVAL-013, EVAL-024 |
| `src/oppp/eval/harness.py` | EVAL-014, EVAL-015, EVAL-019, EVAL-024 |
| `src/oppp/eval/compare.py` | EVAL-014, EVAL-024 |
| `tests/test_services.py` | EVAL-004, EVAL-005, EVAL-024 |
| `tests/test_stages.py` | EVAL-002, EVAL-003, EVAL-006, EVAL-007, EVAL-010, EVAL-024 |
| `tests/test_pipeline.py` | EVAL-001, EVAL-009, EVAL-011, EVAL-021, EVAL-024 |
| `tests/test_eval.py` | EVAL-014, EVAL-015, EVAL-024 |
| `tests/test_per_step_eval.py` | EVAL-014, EVAL-024 |

## Out of Scope

- Live PharmaPendium data correctness beyond the returned `countTotal` or fetched rows, because the external database changes outside the repository.
- Live TERMite and LLM semantic quality, because default verification must be possible with fakes and deterministic tests.
- Editing or curating `docs/PPPK.xlsx`; the harness consumes it as the documented gold source.
- Performance benchmarking beyond the strict `1000` row gate behavior.
- Non-PK service behavior, except where shared contracts must remain import-compatible.
