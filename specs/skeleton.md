# Project Skeleton

## Purpose
This skeleton is the agreed-upon file map for the `oppp` package and its test suite. It is the authoritative file→owner map for `specs/tasks.md`: every file listed here has exactly one WBS owner, and every `Owns` entry in `tasks.md` appears here.

## Directory Tree

```text
.env.example                           <- keys-only credential template          [owner: W1.1.2]
pyproject.toml                         <- package metadata, extras, console script, quality gate config  [owner: W1]

src/oppp/
├── __init__.py                        <- package public surface                  [owner: W1.4.1]
├── config.py                          <- lazy settings loader and required-creds validation  [owner: W1.1.2]
├── registry.py                        <- service registry (no public stage selection)  [owner: W1.2.1]
├── models.py                          <- all Pydantic contracts (stage boundaries, execution, runtime, post-filter)  [owner: W1.1.1]
├── llm.py                             <- LangChain structured-output LLM factory  [owner: W1.1.4]
├── execute.py                         <- count execution + bounded row/datapoint execution  [owner: W1.3.6]
├── pipeline.py                        <- fixed-path orchestrator + LangGraph builder  [owner: W1.4.1]
├── cli.py                             <- Typer CLI (fixed commands, no method selectors)  [owner: W1.4.2]
├── dag.py                             <- draw.io-aligned fixed flow export       [owner: W1.4.4]
├── normalize/
│   ├── __init__.py                    <- normalizer public exports               [owner: W1.1.3]
│   ├── base.py                        <- normalizer interface and result type     [owner: W1.1.3]
│   └── strategies.py                  <- fixed field/bucket normalization strategies  [owner: W1.1.3]
├── services/
│   ├── __init__.py                    <- service exports and registry wiring     [owner: W1.2.1]
│   ├── base.py                        <- FieldSpec, ServiceConfig dataclasses    [owner: W1.2.2]
│   ├── pk.py                          <- PK service config, field specs, invariants  [owner: W1.2.3]
│   ├── safety.py                      <- Safety service config (inactive scope)  [owner: W1.2.4]
│   └── rtb.py                         <- RTB service config (inactive scope)     [owner: W1.2.4]
├── stages/
│   ├── __init__.py                    <- fixed stage exports (no selectable backends)  [owner: W1.3.7]
│   ├── expand.py                      <- Stage -1: LLM faithful expansion        [owner: W1.3.1]
│   ├── enhance.py                     <- Stage 0: required TERMite NER enhancement  [owner: W1.3.2]
│   ├── decompose.py                   <- Stage 1: LLM vocab-free decomposition + annotation reconciliation  [owner: W1.3.3]
│   ├── translate.py                   <- Stage 2A: input closed-set translation; Stage 2B/2C stubs  [owner: W1.3.4]
│   └── aggregate.py                   <- Stage 3: boolean assembly, invariants, validation, open-filter probe  [owner: W1.3.5]
├── taxonomy/
│   ├── __init__.py                    <- taxonomy index public exports           [owner: W1.2.5]
│   └── index.py                       <- CSV-backed taxonomy indexes, RapidFuzz lookup, hierarchy expansion  [owner: W1.2.5]
├── eval/
│   ├── __init__.py                    <- eval public exports                     [owner: W1.5.1]
│   ├── harness.py                     <- count/row evaluation harness; loads docs/PPPK.xlsx  [owner: W1.5.2]
│   ├── per_step.py                    <- per-step/per-field comparators          [owner: W1.5.3]
│   ├── compare.py                     <- gold-vs-agent filter diff helpers       [owner: W1.5.4]
│   └── judge.py                       <- typed LLM-as-judge (LLMJudge, JudgeVerdict)  [owner: W1.5.4]
└── ui/
    ├── __init__.py                    <- UI package marker                       [owner: W1.4.3]
    └── app.py                         <- Streamlit fixed-path debug UI           [owner: W1.4.3]

tests/
├── conftest.py                        <- fake LLM client, fake TERMite client, API fixtures  [owner: W1.5.5]
├── test_pipeline.py                   <- fixed-path pipeline + row-mode regressions  [owner: W1.5.6]
├── test_stages.py                     <- fixed stage methods + SME regression cases  [owner: W1.5.7]
├── test_runtime_post_filters.py       <- runtime closed-set derivation and post-filter tests  [owner: W1.5.8]
├── test_eval.py                       <- evaluation harness and XLSX report tests  [owner: W1.5.9]
├── test_per_step_eval.py              <- per-step comparator tests               [owner: W1.5.10]
├── test_normalize.py                  <- fixed normalizer policy tests           [owner: W1.5.11]
├── test_services.py                   <- PK service config and invariant tests   [owner: W1.5.12]
├── test_taxonomy.py                   <- taxonomy lookup and hierarchy expansion tests  [owner: W1.5.13]
├── test_cli.py                        <- fixed CLI option/output tests           [owner: W1.5.14]
└── test_dag.py                        <- fixed diagram export tests              [owner: W1.5.15]
```

## File Inventory

| File | Layer | Purpose | Owner (WBS node) |
|------|-------|---------|------------------|
| `.env.example` | Config | Keys-only credential template for full-run settings | W1.1.2 |
| `pyproject.toml` | Build | Package metadata, extras (`llm`, `ui`, `viz`, `report`, `dev`), console script, Ruff/Pytest config | W1 |
| `src/oppp/__init__.py` | Package | Public surface exports | W1.4.1 |
| `src/oppp/config.py` | Config | Lazy settings loader; blocks full runs when TERMite/LLM creds absent | W1.1.2 |
| `src/oppp/registry.py` | Service | Service registry; no public stage selection | W1.2.1 |
| `src/oppp/models.py` | Contracts | Pydantic v2: `ExpandedQuery`, `EntityAnnotation`, `EnhancedQuery`, `Component`, `BooleanGroup`, `GroundingHit`, `Grounding`, `MachineSubquery`, `MachineQuery`, `ExecutionResult`, `RowExecutionResult`, `RuntimeClosedSet`, `PostFilterResult`, `PipelineResult` | W1.1.1 |
| `src/oppp/llm.py` | LLM | LangChain structured-output factory; lazy import; seed/provider wiring | W1.1.4 |
| `src/oppp/execute.py` | Execution | `execute_count` (count-only); `execute_rows` (bounded row fetch, pagination) | W1.3.6 |
| `src/oppp/pipeline.py` | Orchestration | Fixed `run_pipeline`; LangGraph builder; `__init__.py` re-exports | W1.4.1 |
| `src/oppp/cli.py` | CLI | `oppp run/enhance/decompose/field/aggregate/lookup/eval/dag/services`; no method selectors | W1.4.2 |
| `src/oppp/dag.py` | Diagram | Fixed flow export matching `docs/agent-dag.drawio` | W1.4.4 |
| `src/oppp/normalize/__init__.py` | Normalization | Normalizer exports | W1.1.3 |
| `src/oppp/normalize/base.py` | Normalization | `NormalizationResult` interface | W1.1.3 |
| `src/oppp/normalize/strategies.py` | Normalization | Fixed field/bucket strategies (`closed`, `open`, `drugs`) | W1.1.3 |
| `src/oppp/services/__init__.py` | Service | Service exports and registry wiring | W1.2.1 |
| `src/oppp/services/base.py` | Service | `FieldSpec`, `ServiceConfig` dataclasses | W1.2.2 |
| `src/oppp/services/pk.py` | Service | PK field specs, `EARLY_CONTRIBUTOR_THRESHOLD`, facets, invariants, search URL | W1.2.3 |
| `src/oppp/services/safety.py` | Service | Safety config (inactive scope; preserved for future) | W1.2.4 |
| `src/oppp/services/rtb.py` | Service | RTB config (inactive scope; preserved for future) | W1.2.4 |
| `src/oppp/stages/__init__.py` | Stages | Fixed stage exports | W1.3.7 |
| `src/oppp/stages/expand.py` | Stage -1 | LLM `expand_query` → `ExpandedQuery` | W1.3.1 |
| `src/oppp/stages/enhance.py` | Stage 0 | Required TERMite `enhance` → `EnhancedQuery` | W1.3.2 |
| `src/oppp/stages/decompose.py` | Stage 1 | LLM `decompose` + `reconcile_with_annotations` → `Decomposition` | W1.3.3 |
| `src/oppp/stages/translate.py` | Stage 2 | `translate_input_filter` (2A); `translate_runtime_filter` stub (2B/2C) | W1.3.4 |
| `src/oppp/stages/aggregate.py` | Stage 3 | Boolean assembly, PK invariants, structural validation, `drop_empty_open_filters`, `apply_post_filters` | W1.3.5 |
| `src/oppp/taxonomy/__init__.py` | Taxonomy | Taxonomy index exports | W1.2.5 |
| `src/oppp/taxonomy/index.py` | Taxonomy | CSV-backed indexes, RapidFuzz fuzzy lookup, hierarchy expansion, `lookup_*` tools | W1.2.5 |
| `src/oppp/eval/__init__.py` | Evaluation | Eval public exports | W1.5.1 |
| `src/oppp/eval/harness.py` | Evaluation | Count/row harness; loads `docs/PPPK.xlsx` via openpyxl | W1.5.2 |
| `src/oppp/eval/per_step.py` | Evaluation | Stage 0–3 per-step comparators | W1.5.3 |
| `src/oppp/eval/compare.py` | Evaluation | Gold-vs-agent filter diff | W1.5.4 |
| `src/oppp/eval/judge.py` | Evaluation | `LLMJudge`, `JudgeVerdict`; fake-injectable | W1.5.4 |
| `src/oppp/ui/__init__.py` | UI | UI package marker | W1.4.3 |
| `src/oppp/ui/app.py` | UI | Streamlit fixed-path inspector; PPPK.xlsx question picker | W1.4.3 |
| `tests/conftest.py` | Tests | Fake LLM client, fake TERMite client, mocked API response fixtures | W1.5.5 |
| `tests/test_pipeline.py` | Tests | Fixed-path pipeline; row-mode end-to-end | W1.5.6 |
| `tests/test_stages.py` | Tests | Per-stage unit tests; SME regression cases (Rodent expansion, suntinib fuzzy, AUC OR Cmax, PK invariants) | W1.5.7 |
| `tests/test_runtime_post_filters.py` | Tests | Runtime closed-set derivation; post-filter application | W1.5.8 |
| `tests/test_eval.py` | Tests | Harness XLSX load; count/row metrics; CSV/XLSX report export | W1.5.9 |
| `tests/test_per_step_eval.py` | Tests | Per-step comparator coverage | W1.5.10 |
| `tests/test_normalize.py` | Tests | Fixed normalizer policy cases | W1.5.11 |
| `tests/test_services.py` | Tests | PK service config, invariants, field buckets | W1.5.12 |
| `tests/test_taxonomy.py` | Tests | Taxonomy lookup, fuzzy, hierarchy expansion | W1.5.13 |
| `tests/test_cli.py` | Tests | CLI fixed commands; no method selector flags | W1.5.14 |
| `tests/test_dag.py` | Tests | DAG export matches fixed stage list | W1.5.15 |

## Conventions
- **Module boundaries**: `stages/` contains only stage logic; no service-specific field names. `services/` contains only service config data. `taxonomy/` contains only taxonomy index logic. `eval/` contains only evaluation code.
- **No stage imports at top level**: `from oppp.stages import enhance` must not trigger TERMite or LangChain imports. All such imports are deferred to function body or lazy module attribute.
- **`OPPP_INPUTS_DIR`**: controls the directory from which all taxonomy CSVs and the gold set are loaded. Defaults to `inputs/` relative to the repository root.
- **Gold set path**: `docs/PPPK.xlsx` is loaded relative to the repository root (not `OPPP_INPUTS_DIR`).
- **No migration files**: this package has no database; no migration naming convention is needed.
- **`.env.example`**: lists all env var names with empty values and a comment indicating whether each is required for full runs or optional.
