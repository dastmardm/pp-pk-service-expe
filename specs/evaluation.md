# Evaluation Criteria

## Sources
- `specs/product.md`
- `specs/technical.md`
- `specs/constitution.md`
- `specs/requirements.md`
- `specs/plan.md`
- `specs/skeleton.md`

## How to read this file
Each criterion is an objectively decidable check over the codebase. The
`/mdevaluation` step assigns PASS, PARTIAL, FAIL, N/A, or BLOCKED and cites
file:line evidence. This file defines what to check; it does not prescribe how
the auditor must implement the audit.

## Criteria
| ID | Source ref | Category | Criterion (objectively decidable) | Evidence to look for | Severity |
|----|------------|----------|-----------------------------------|----------------------|----------|
| EVAL-001 | REQ-001, CONTRACT-EXPANDED-QUERY | Requirement | `PipelineResult` carries original query, expanded query, enhancement, decomposition, subqueries, machine query, issues, and row/runtime metadata fields when row mode is used. | `src/oppp/models.py:PipelineResult`; `src/oppp/pipeline.py:run_pipeline` | BLOCKER |
| EVAL-002 | REQ-002 | Requirement | Stage -1 preserves `original` and produces `text` without mutating the original query field. | `src/oppp/stages/expand.py`; tests asserting original preservation | MAJOR |
| EVAL-003 | REQ-003, CONST-8 | Requirement | Enhancer registry exposes `noop` and `termite`; `noop` runs without credentials. | `src/oppp/stages/enhance.py`; registry tests | MAJOR |
| EVAL-004 | REQ-004, CONST-3 | Constitution | Production decomposer has no taxonomy lookup/import dependency and emits components with field, fragment, type, reason, source, and optional boolean group. | `src/oppp/stages/decompose.py`; `src/oppp/models.py:Component` | BLOCKER |
| EVAL-005 | REQ-005 | Requirement | Pipeline translates only `Decomposition.filters`; question components are used for facets/display columns. | `src/oppp/pipeline.py`; `src/oppp/stages/aggregate.py:_outputs` | MAJOR |
| EVAL-006 | REQ-006, CONTRACT-CLOSED-SET-TRANSLATION, CONST-1 | Data contract | Closed-set translation implements exact/fuzzy matching, LLM enrichment/selection fallback hooks, and membership assertion before emission. | `src/oppp/stages/translate.py` closed path and tests | BLOCKER |
| EVAL-007 | REQ-007, CONST-1 | Data contract | Closed-set translation never emits an out-of-set value; ungroundable values produce an invalid/dropped result. | `MachineSubquery.dropped`; translate tests for unknown values | BLOCKER |
| EVAL-008 | REQ-008 | Requirement | Dropped input closed-set subqueries are excluded from query/entity filters and surfaced as warnings. | `src/oppp/stages/aggregate.py:_drop_ungroundable`; tests | BLOCKER |
| EVAL-009 | REQ-009, CONST-6 | Requirement | Tests or code paths cover Rodent class label, Monkeys member expansion, positive Ames Test narrowing, MTD toxicity parameter, ADC class, Columvi/Glofitamab, and preclinical boolean handling. | `src/oppp/stages/translate.py`; `tests/test_stages.py` | BLOCKER |
| EVAL-010 | REQ-010, CONTRACT-MACHINE-QUERY, CONST-5 | Data contract | Stage 3 emits exactly one top-level query constraint, validates AND/OR/NOT arity, routes entity filters, applies invariants, and attaches allowed facets/display columns. | `src/oppp/stages/aggregate.py:validate`; service configs | BLOCKER |
| EVAL-011 | REQ-011, CONTRACT-EXECUTION-COUNT, CONTRACT-EXECUTION-ROWS | Requirement | `execute_count` remains present and `execute_rows` or equivalent typed row execution returns datapoints or structured errors. | `src/oppp/execute.py`; row execution tests | BLOCKER |
| EVAL-012 | REQ-012, CONTRACT-RUNTIME-CLOSED-SET, CONST-2 | Data contract | Pipeline derives unique non-empty runtime value sets for deferred open fields from fetched datapoints. | `src/oppp/pipeline.py` or helper; `tests/test_runtime_post_filters.py` | BLOCKER |
| EVAL-013 | REQ-013, CONTRACT-POST-FILTER, CONST-2 | Data contract | Runtime translation accepts open-field component plus runtime values and can return only selected values from those runtime values. | `src/oppp/stages/translate.py` runtime entry; tests | BLOCKER |
| EVAL-014 | REQ-014, CONTRACT-POST-FILTER | Requirement | Valid runtime selections filter datapoints; invalid runtime selections leave datapoints unchanged and record an issue. | `src/oppp/stages/aggregate.py` post-filter helper; tests | BLOCKER |
| EVAL-015 | REQ-015 | Requirement | Zero-count probes still exist for count-only/live mode and are not used as the row-mode substitute when datapoints are available. | `drop_empty_open_filters`; pipeline row-mode branch | MAJOR |
| EVAL-016 | REQ-016, CONTRACT-SERVICE-CONFIG, CONST-7 | Data contract | Safety, PK, and RTB are registered service configs; stage modules do not own service field maps. | `src/oppp/services/*.py`; stage module scan/tests | MAJOR |
| EVAL-017 | REQ-017 | Requirement | CLI exposes existing run/payload/count options and a row/runtime output path. | `src/oppp/cli.py` command options/output | MAJOR |
| EVAL-018 | REQ-018 | Requirement | Streamlit app displays Stage -1, row execution, runtime selections, invalid runtime filters, and filtered datapoint count when present. | `src/oppp/ui/app.py` controls/panels | MINOR |
| EVAL-019 | REQ-019, CONTRACT-GOLD-PERSTEP, CONTRACT-GOLD-PERFIELD, CONST-9 | Requirement | Evaluation reads `docs/sme_stage_cases.csv`, keeps per-step comparators, and preserves count metrics/report export. | `src/oppp/eval/per_step.py`; `src/oppp/eval/harness.py` | MAJOR |
| EVAL-020 | REQ-020 | Requirement | Regression tests cover Q7, Q12, Q18, Q20, Q23, Q24, and Q25 expected behavior from `docs/sme_stage_cases.csv`. | `tests/test_stages.py`; `tests/test_pipeline.py`; `tests/test_per_step_eval.py` | BLOCKER |
| EVAL-021 | REQ-021, NFR-002, CONST-8 | Non-functional | Default tests use offline doubles and do not require network/LLM/TERMite credentials. | test configuration and monkeypatch/fake clients | BLOCKER |
| EVAL-022 | REQ-022, CONST-10 | Constitution | Secrets are read lazily; `.env` is ignored; `.env.example` contains keys only. | `src/oppp/config.py`; `.gitignore`; `.env.example` | BLOCKER |
| EVAL-023 | REQ-023 | Requirement | LLM judge remains typed and injectable/fakeable for hermetic tests. | `src/oppp/eval/judge.py`; `tests/test_per_step_eval.py` | MINOR |
| EVAL-024 | REQ-024, NFR-004 | Non-functional | Row fetch exposes bounded options and row execution failures produce structured issues while count-only execution remains usable. | `src/oppp/execute.py`; `src/oppp/pipeline.py`; tests | MAJOR |
| EVAL-025 | CONTRACT-GROUNDING | Data contract | Grounding metadata records matched hits, expansion source, and confidence for grounded closed-set filters. | `src/oppp/models.py:Grounding`; translate code/tests | MAJOR |
| EVAL-026 | CONST-4 | Constitution | Stage and execution boundaries exchange typed models/dataclasses, not unvalidated free text. | `src/oppp/models.py`; function signatures in `src/oppp/stages/*.py`, `execute.py` | MAJOR |
| EVAL-027 | CONST-11, NFR-001 | Non-functional | Compile, Ruff lint, Ruff format-check, and pytest commands are documented and pass. | `pyproject.toml`; command results | BLOCKER |
| EVAL-028 | Skeleton: `src/oppp/models.py` | Skeleton/Structure | File exists and defines runtime row/post-filter contracts. | `src/oppp/models.py` | BLOCKER |
| EVAL-029 | Skeleton: `src/oppp/execute.py` | Skeleton/Structure | File exists and owns count plus row execution. | `src/oppp/execute.py` | BLOCKER |
| EVAL-030 | Skeleton: `src/oppp/stages/translate.py` | Skeleton/Structure | File exists and owns input/runtime translation behavior. | `src/oppp/stages/translate.py` | BLOCKER |
| EVAL-031 | Skeleton: `src/oppp/stages/aggregate.py` | Skeleton/Structure | File exists and owns query aggregation plus runtime post-filtering. | `src/oppp/stages/aggregate.py` | BLOCKER |
| EVAL-032 | Skeleton: `src/oppp/pipeline.py`, `src/oppp/cli.py`, `src/oppp/ui/app.py` | Skeleton/Structure | Surface/orchestration files exist and expose runtime metadata. | listed files | MAJOR |
| EVAL-033 | Skeleton: `src/oppp/eval/per_step.py`, `src/oppp/eval/harness.py` | Skeleton/Structure | Evaluation files exist and support per-step/count compatibility. | listed files | MAJOR |
| EVAL-034 | Skeleton: tests | Skeleton/Structure | All promised test files exist, including `tests/test_runtime_post_filters.py`. | `tests/` files listed in `specs/skeleton.md` | BLOCKER |

## Coverage Map
| Source item | Covered by |
|-------------|------------|
| REQ-001 | EVAL-001 |
| REQ-002 | EVAL-002 |
| REQ-003 | EVAL-003 |
| REQ-004 | EVAL-004 |
| REQ-005 | EVAL-005 |
| REQ-006 | EVAL-006 |
| REQ-007 | EVAL-007 |
| REQ-008 | EVAL-008 |
| REQ-009 | EVAL-009 |
| REQ-010 | EVAL-010 |
| REQ-011 | EVAL-011 |
| REQ-012 | EVAL-012 |
| REQ-013 | EVAL-013 |
| REQ-014 | EVAL-014 |
| REQ-015 | EVAL-015 |
| REQ-016 | EVAL-016 |
| REQ-017 | EVAL-017 |
| REQ-018 | EVAL-018 |
| REQ-019 | EVAL-019 |
| REQ-020 | EVAL-020 |
| REQ-021 | EVAL-021 |
| REQ-022 | EVAL-022 |
| REQ-023 | EVAL-023 |
| REQ-024 | EVAL-024 |
| NFR-001 | EVAL-027 |
| NFR-002 | EVAL-021 |
| NFR-003 | EVAL-021, EVAL-026 |
| NFR-004 | EVAL-024 |
| CONTRACT-EXPANDED-QUERY | EVAL-001, EVAL-002 |
| CONTRACT-ENHANCED-QUERY | EVAL-003 |
| CONTRACT-COMPONENT | EVAL-004, EVAL-005 |
| CONTRACT-SUBQUERY | EVAL-006, EVAL-007, EVAL-008 |
| CONTRACT-MACHINE-QUERY | EVAL-010 |
| CONTRACT-CLOSED-SET-TRANSLATION | EVAL-006, EVAL-007 |
| CONTRACT-GROUNDING | EVAL-025 |
| CONTRACT-RUNTIME-CLOSED-SET | EVAL-012 |
| CONTRACT-POST-FILTER | EVAL-013, EVAL-014 |
| CONTRACT-EXECUTION-COUNT | EVAL-011, EVAL-019 |
| CONTRACT-EXECUTION-ROWS | EVAL-011, EVAL-024 |
| CONTRACT-SERVICE-CONFIG | EVAL-016 |
| CONTRACT-GOLD-PERSTEP | EVAL-019, EVAL-020 |
| CONTRACT-GOLD-PERFIELD | EVAL-019 |
| CONST-1 | EVAL-006, EVAL-007 |
| CONST-2 | EVAL-012, EVAL-013, EVAL-014 |
| CONST-3 | EVAL-004 |
| CONST-4 | EVAL-026 |
| CONST-5 | EVAL-010 |
| CONST-6 | EVAL-009 |
| CONST-7 | EVAL-016 |
| CONST-8 | EVAL-003, EVAL-021 |
| CONST-9 | EVAL-019, EVAL-023 |
| CONST-10 | EVAL-022 |
| CONST-11 | EVAL-027 |
| `src/oppp/models.py` | EVAL-028 |
| `src/oppp/execute.py` | EVAL-029 |
| `src/oppp/stages/translate.py` | EVAL-030 |
| `src/oppp/stages/aggregate.py` | EVAL-031 |
| `src/oppp/pipeline.py` | EVAL-032 |
| `src/oppp/cli.py` | EVAL-032 |
| `src/oppp/ui/app.py` | EVAL-032 |
| `src/oppp/eval/per_step.py` | EVAL-033 |
| `src/oppp/eval/harness.py` | EVAL-033 |
| `tests/test_runtime_post_filters.py` | EVAL-034 |
| `tests/test_pipeline.py` | EVAL-034 |
| `tests/test_stages.py` | EVAL-034 |
| `tests/test_eval.py` | EVAL-034 |
| `tests/test_per_step_eval.py` | EVAL-034 |

## Out of Scope
- Live PharmaPendium API availability and exact live count values. Criteria check
  code support and graceful failure; external service behavior is not auditable
  from the repository alone.
- SME judgement of whether a new free-text runtime value is clinically correct
  beyond the typed judge/fakeable comparator contract.
