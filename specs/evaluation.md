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
| EVAL-001 | REQ-001, CONTRACT-EXPANDED-QUERY, CONTRACT-ENHANCED-QUERY | Requirement | `PipelineResult` carries original query, expansion, TERMite enhancement, decomposition, input translations, first query, execution metadata, runtime closed sets, runtime translations, post-filter metadata, final datapoints/count, and issues. | `src/oppp/models.py:PipelineResult`; `src/oppp/pipeline.py:run_pipeline` | BLOCKER |
| EVAL-002 | REQ-002, CONTRACT-EXPANDED-QUERY | Requirement | Stage -1 preserves `original`, returns LLM-sourced `text`, and missing LLM support is reported rather than represented as a public no-op expander. | `src/oppp/stages/expand.py`; `tests/test_stages.py` | BLOCKER |
| EVAL-003 | REQ-003, CONTRACT-ENHANCED-QUERY, CONST-2 | Requirement | Full pipeline and Stage 0 inspection invoke TERMite and fail with a clear configuration/dependency error when TERMite is unavailable. | `src/oppp/stages/enhance.py`; `src/oppp/pipeline.py`; tests with fake/missing TERMite | BLOCKER |
| EVAL-004 | REQ-004, CONTRACT-COMPONENT, CONST-5 | Requirement | Production decomposition uses LLM structured output, emits the required component shape, and has no taxonomy lookup dependency in the production path. | `src/oppp/stages/decompose.py`; imports/function signatures/tests | BLOCKER |
| EVAL-005 | REQ-005, CONTRACT-FIXED-STAGE-PATH, CONST-1 | Requirement | Public pipeline signatures, CLI options, UI controls, and evaluation configuration expose no stage method selectors, normalizer selectors, or no-op bypasses. | `src/oppp/pipeline.py`, `src/oppp/cli.py`, `src/oppp/ui/app.py`, `src/oppp/eval/harness.py`; CLI tests | BLOCKER |
| EVAL-006 | REQ-006, CONTRACT-COMPONENT | Requirement | Pipeline translates only `Decomposition.filters`; question components are used only for facets/display columns/output metadata. | `src/oppp/pipeline.py`; `src/oppp/stages/aggregate.py`; tests | MAJOR |
| EVAL-007 | REQ-007, CONTRACT-CLOSED-SET-TRANSLATION | Data contract | Closed-set translation implements exact matching, fuzzy matching, LLM pool enrichment, exact/fuzzy retry, LLM closed-set selection, and membership feedback/retry before invalid. | `src/oppp/stages/translate.py`; tests for each branch | BLOCKER |
| EVAL-008 | REQ-008, CONTRACT-CLOSED-SET-TRANSLATION, CONST-3 | Data contract | Input and runtime closed-set translation never emit out-of-set values; empty/None/out-of-set-only candidates produce invalid metadata. | `src/oppp/stages/translate.py`; `tests/test_stages.py`; `tests/test_runtime_post_filters.py` | BLOCKER |
| EVAL-009 | REQ-009, CONTRACT-SUBQUERY, CONST-3 | Requirement | Invalid input closed-set translations are recorded and excluded from the first API query, entity filters, facets, display columns, and post-filtering. | `MachineSubquery.dropped`; `src/oppp/stages/aggregate.py`; tests | BLOCKER |
| EVAL-010 | REQ-010, CONST-8 | Requirement | Normalization is one fixed field/bucket policy, preserves valid class labels, and exposes no public `noop` normalizer selection. | `src/oppp/normalize/*.py`; `tests/test_normalize.py` | MAJOR |
| EVAL-011 | REQ-011, CONTRACT-GROUNDING, CONST-9 | Requirement | Code/tests cover class labels, Monkeys, effect family rollups, positive Ames Test, MTD, ADC, Columvi/Glofitamab, and preclinical handling. | `src/oppp/taxonomy/index.py`; `src/oppp/stages/translate.py`; `tests/test_stages.py`; `tests/test_taxonomy.py` | BLOCKER |
| EVAL-012 | REQ-012, CONTRACT-MACHINE-QUERY, CONST-7 | Data contract | Stage 3 emits exactly one top-level query constraint, validates AND/OR/NOT arity, routes entity filters, applies invariants, and attaches allowed facets/display columns. | `src/oppp/stages/aggregate.py:validate`; service configs; tests | BLOCKER |
| EVAL-013 | REQ-013, CONTRACT-EXECUTION-COUNT, CONTRACT-EXECUTION-ROWS | Requirement | `execute_count` remains present and typed row execution returns datapoints or structured unavailable/error results. | `src/oppp/execute.py`; `src/oppp/models.py`; row execution tests | BLOCKER |
| EVAL-014 | REQ-014, CONTRACT-RUNTIME-CLOSED-SET, CONST-4 | Data contract | Pipeline derives sorted unique non-empty runtime value sets for deferred open fields from fetched datapoints. | `src/oppp/pipeline.py` or helper; `tests/test_runtime_post_filters.py` | BLOCKER |
| EVAL-015 | REQ-015, CONTRACT-POST-FILTER, CONST-4 | Data contract | Runtime translation accepts an open-field component plus runtime values and returns only selected values from that runtime set. | `src/oppp/stages/translate.py` runtime entry; tests | BLOCKER |
| EVAL-016 | REQ-016, CONTRACT-POST-FILTER | Requirement | Valid runtime selections filter datapoints; invalid runtime selections leave datapoints unchanged and record an issue. | `src/oppp/stages/aggregate.py` post-filter helper; tests | BLOCKER |
| EVAL-017 | REQ-017 | Requirement | Count-only execution/evaluation still works, and row mode uses runtime post-filtering rather than zero-count probes when datapoints are available. | `src/oppp/pipeline.py`; `src/oppp/eval/harness.py`; tests | MAJOR |
| EVAL-018 | REQ-018, CONTRACT-SERVICE-CONFIG, CONST-10 | Data contract | Safety, PK, and RTB are registered service configs; shared stage modules do not own service-specific field maps. | `src/oppp/services/*.py`; stage module scan/tests | MAJOR |
| EVAL-019 | REQ-019 | Requirement | CLI exposes fixed full-run and isolated-stage commands, row/runtime output, and no old stage method or normalizer flags. | `src/oppp/cli.py`; `tests/test_cli.py`; Typer help output | BLOCKER |
| EVAL-020 | REQ-020 | Requirement | Streamlit app displays fixed-path stage outputs, runtime closed sets, invalid runtime filters, and filtered count without backend selector widgets. | `src/oppp/ui/app.py`; UI code inspection/tests | MAJOR |
| EVAL-021 | REQ-021 | Requirement | Diagram export reflects the fixed draw.io flow and contains no pluggable-backend legend or registry-derived method list. | `src/oppp/dag.py`; `docs/agent-dag.drawio`; `tests/test_dag.py` | MINOR |
| EVAL-022 | REQ-022, CONTRACT-GOLD-PERSTEP, CONTRACT-GOLD-PERFIELD, CONST-12 | Requirement | Evaluation loads both SME gold sources and reports per-step, per-field, machine-query, and count metrics. | `src/oppp/eval/per_step.py`; `src/oppp/eval/harness.py`; `src/oppp/eval/compare.py`; tests | MAJOR |
| EVAL-023 | REQ-023 | Requirement | Regression tests explicitly cover Q7, Q12, Q18, Q20, Q23, Q24, and Q25. | `tests/test_stages.py`; `tests/test_pipeline.py`; `tests/test_per_step_eval.py` | BLOCKER |
| EVAL-024 | REQ-024, CONST-11, NFR-002 | Requirement | Default tests use injected fakes/fixtures and do not require network, LLM credentials, TERMite credentials, or public no-op product methods. | `tests/conftest.py`; tests; absence of product no-op selectors | BLOCKER |
| EVAL-025 | REQ-025, CONST-13 | Constitution | Secrets are read lazily at invocation; `.env` is ignored; `.env.example` contains keys only and no real secrets. | `src/oppp/config.py`; `.gitignore`; `.env.example` | BLOCKER |
| EVAL-026 | REQ-026, NFR-004 | Non-functional | Row fetch exposes bounded options and row-fetch failures produce structured issues while count-only execution remains usable. | `src/oppp/execute.py`; `src/oppp/pipeline.py`; tests | MAJOR |
| EVAL-027 | REQ-027 | Requirement | LLM judge remains typed and injectable/fakeable for hermetic tests. | `src/oppp/eval/judge.py`; `tests/test_per_step_eval.py` | MINOR |
| EVAL-028 | CONTRACT-GROUNDING | Data contract | Grounding metadata records matched hits, expansion source, and confidence for grounded filters. | `src/oppp/models.py:Grounding`; translate/taxonomy tests | MAJOR |
| EVAL-029 | CONST-6 | Constitution | Stage and execution boundaries exchange typed models/dataclasses, not unvalidated free text. | `src/oppp/models.py`; signatures in `src/oppp/stages/*.py`, `src/oppp/execute.py` | MAJOR |
| EVAL-030 | CONST-14, NFR-001 | Non-functional | Compile, Ruff lint, Ruff format-check, and pytest commands are documented and pass. | `specs/constitution.md`; command results | BLOCKER |
| EVAL-031 | NFR-003 | Non-functional | Importing core modules does not import LLM, TERMite, Streamlit, matplotlib, or openpyxl dependencies. | import graph/code inspection/tests | MAJOR |
| EVAL-032 | NFR-005 | Non-functional | Public help text contains no advertised `noop`, backend, normalizer, decomposer, enhancer, translator, or aggregator method options. | `oppp --help`, `oppp run --help`, `tests/test_cli.py` | BLOCKER |
| EVAL-033 | Skeleton: `.env.example`, `src/oppp/config.py` | Skeleton/Structure | Config files exist and serve required lazy settings/template purposes. | listed files | MAJOR |
| EVAL-034 | Skeleton: `src/oppp/models.py` | Skeleton/Structure | File exists and defines runtime row/post-filter contracts. | `src/oppp/models.py` | BLOCKER |
| EVAL-035 | Skeleton: `src/oppp/normalize/*` | Skeleton/Structure | Normalization files exist and expose fixed policy behavior. | `src/oppp/normalize/base.py`; `strategies.py`; `__init__.py` | MAJOR |
| EVAL-036 | Skeleton: `src/oppp/registry.py`, `src/oppp/services/*` | Skeleton/Structure | Registry/service files exist and keep service config separate from stage logic. | listed files | MAJOR |
| EVAL-037 | Skeleton: `src/oppp/stages/expand.py`, `enhance.py`, `decompose.py`, `translate.py`, `aggregate.py`, `__init__.py` | Skeleton/Structure | Stage files exist and expose fixed stage behavior. | listed files | BLOCKER |
| EVAL-038 | Skeleton: `src/oppp/execute.py` | Skeleton/Structure | File exists and owns count plus row execution. | `src/oppp/execute.py` | BLOCKER |
| EVAL-039 | Skeleton: `src/oppp/pipeline.py`, `src/oppp/cli.py`, `src/oppp/ui/app.py`, `src/oppp/dag.py` | Skeleton/Structure | Surface/orchestration files exist and expose fixed path/runtime metadata. | listed files | MAJOR |
| EVAL-040 | Skeleton: `src/oppp/eval/per_step.py`, `harness.py`, `compare.py`, `judge.py` | Skeleton/Structure | Evaluation files exist and support per-step/count/runtime/judge behavior. | listed files | MAJOR |
| EVAL-041 | Skeleton: tests | Skeleton/Structure | All promised test files exist, including new `tests/conftest.py`, `tests/test_runtime_post_filters.py`, `tests/test_cli.py`, and `tests/test_dag.py`. | `tests/` files listed in `specs/skeleton.md` | BLOCKER |

## Coverage Map
| Source item | Covered by |
|-------------|------------|
| REQ-001 | EVAL-001 |
| REQ-002 | EVAL-002 |
| REQ-003 | EVAL-003 |
| REQ-004 | EVAL-004 |
| REQ-005 | EVAL-005, EVAL-019, EVAL-020, EVAL-032 |
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
| REQ-025 | EVAL-025 |
| REQ-026 | EVAL-026 |
| REQ-027 | EVAL-027 |
| NFR-001 | EVAL-030 |
| NFR-002 | EVAL-024 |
| NFR-003 | EVAL-031 |
| NFR-004 | EVAL-026 |
| NFR-005 | EVAL-032 |
| CONTRACT-EXPANDED-QUERY | EVAL-001, EVAL-002 |
| CONTRACT-ENHANCED-QUERY | EVAL-001, EVAL-003 |
| CONTRACT-COMPONENT | EVAL-004, EVAL-006 |
| CONTRACT-CLOSED-SET | EVAL-007, EVAL-008, EVAL-014, EVAL-015 |
| CONTRACT-CLOSED-SET-TRANSLATION | EVAL-007, EVAL-008, EVAL-015 |
| CONTRACT-SUBQUERY | EVAL-009 |
| CONTRACT-GROUNDING | EVAL-011, EVAL-028 |
| CONTRACT-MACHINE-QUERY | EVAL-012 |
| CONTRACT-EXECUTION-COUNT | EVAL-013, EVAL-017 |
| CONTRACT-EXECUTION-ROWS | EVAL-013, EVAL-026 |
| CONTRACT-RUNTIME-CLOSED-SET | EVAL-014 |
| CONTRACT-POST-FILTER | EVAL-015, EVAL-016 |
| CONTRACT-SERVICE-CONFIG | EVAL-018 |
| CONTRACT-GOLD-PERSTEP | EVAL-022, EVAL-023 |
| CONTRACT-GOLD-PERFIELD | EVAL-022 |
| CONTRACT-FIXED-STAGE-PATH | EVAL-005, EVAL-019, EVAL-020, EVAL-032 |
| CONST-1 | EVAL-005 |
| CONST-2 | EVAL-003 |
| CONST-3 | EVAL-008, EVAL-009 |
| CONST-4 | EVAL-014, EVAL-015, EVAL-016 |
| CONST-5 | EVAL-004 |
| CONST-6 | EVAL-029 |
| CONST-7 | EVAL-012 |
| CONST-8 | EVAL-010 |
| CONST-9 | EVAL-011 |
| CONST-10 | EVAL-018 |
| CONST-11 | EVAL-024 |
| CONST-12 | EVAL-022, EVAL-027 |
| CONST-13 | EVAL-025 |
| CONST-14 | EVAL-030 |
| `.env.example` | EVAL-033 |
| `src/oppp/config.py` | EVAL-033 |
| `src/oppp/models.py` | EVAL-034 |
| `src/oppp/normalize/base.py` | EVAL-035 |
| `src/oppp/normalize/strategies.py` | EVAL-035 |
| `src/oppp/normalize/__init__.py` | EVAL-035 |
| `src/oppp/registry.py` | EVAL-036 |
| `src/oppp/services/base.py` | EVAL-036 |
| `src/oppp/services/__init__.py` | EVAL-036 |
| `src/oppp/services/safety.py` | EVAL-036 |
| `src/oppp/services/pk.py` | EVAL-036 |
| `src/oppp/services/rtb.py` | EVAL-036 |
| `src/oppp/stages/expand.py` | EVAL-037 |
| `src/oppp/stages/enhance.py` | EVAL-037 |
| `src/oppp/stages/decompose.py` | EVAL-037 |
| `src/oppp/stages/translate.py` | EVAL-037 |
| `src/oppp/stages/aggregate.py` | EVAL-037 |
| `src/oppp/stages/__init__.py` | EVAL-037 |
| `src/oppp/execute.py` | EVAL-038 |
| `src/oppp/pipeline.py` | EVAL-039 |
| `src/oppp/cli.py` | EVAL-039 |
| `src/oppp/ui/app.py` | EVAL-039 |
| `src/oppp/dag.py` | EVAL-039 |
| `src/oppp/eval/per_step.py` | EVAL-040 |
| `src/oppp/eval/harness.py` | EVAL-040 |
| `src/oppp/eval/compare.py` | EVAL-040 |
| `src/oppp/eval/judge.py` | EVAL-040 |
| `tests/conftest.py` | EVAL-041 |
| `tests/test_pipeline.py` | EVAL-041 |
| `tests/test_stages.py` | EVAL-041 |
| `tests/test_runtime_post_filters.py` | EVAL-041 |
| `tests/test_eval.py` | EVAL-041 |
| `tests/test_per_step_eval.py` | EVAL-041 |
| `tests/test_normalize.py` | EVAL-041 |
| `tests/test_services.py` | EVAL-041 |
| `tests/test_taxonomy.py` | EVAL-041 |
| `tests/test_cli.py` | EVAL-041 |
| `tests/test_dag.py` | EVAL-041 |

## Out of Scope
- Live PharmaPendium API availability and exact live count values. Criteria check
  code support, row parsing, and graceful failure; external service behavior is
  not auditable from the repository alone.
- SME judgement of whether a new free-text runtime value is clinically correct
  beyond the typed judge/fakeable comparator contract.
