# Project Skeleton

## Purpose
This skeleton is the implementation file map for the fixed TERMite pipeline and
runtime closed-set post-filtering. It is also the authoritative file-to-owner map
for `specs/tasks.md`: every file listed here has exactly one WBS owner, and every
`Owns` entry in the WBS appears here.

## Directory Tree
```text
.env.example                  <- keys-only template for required full-run settings [owner: W1.1.2]
src/oppp/
├── config.py                  <- lazy settings and required full-run config errors [owner: W1.1.2]
├── registry.py                <- registry helper limited away from public stage selection [owner: W1.2.1]
├── models.py                  <- runtime row/post-filter contracts and PipelineResult metadata [owner: W1.1.1]
├── execute.py                 <- count execution plus bounded row/datapoint execution [owner: W1.3.6]
├── pipeline.py                <- fixed-path orchestration and runtime post-filter wiring [owner: W1.4.1]
├── cli.py                     <- fixed CLI controls and runtime output [owner: W1.4.2]
├── dag.py                     <- draw.io-aligned fixed flow export [owner: W1.4.4]
├── normalize/
│   ├── __init__.py            <- fixed normalizer exports [owner: W1.1.3]
│   ├── base.py                <- fixed normalizer interface [owner: W1.1.3]
│   └── strategies.py          <- fixed field/bucket normalization policy [owner: W1.1.3]
├── services/
│   ├── __init__.py            <- service exports [owner: W1.2.2]
│   ├── base.py                <- service schema and field buckets [owner: W1.2.2]
│   ├── safety.py              <- Safety service config [owner: W1.2.3]
│   ├── pk.py                  <- PK service config and invariants [owner: W1.2.3]
│   └── rtb.py                 <- RTB service config and serializer [owner: W1.2.3]
├── stages/
│   ├── __init__.py            <- fixed stage exports [owner: W1.3.7]
│   ├── expand.py              <- fixed LLM expansion [owner: W1.3.1]
│   ├── enhance.py             <- required TERMite enhancement [owner: W1.3.2]
│   ├── decompose.py           <- fixed LLM decomposition and reconciliation [owner: W1.3.3]
│   ├── translate.py           <- input/runtime closed-set translation [owner: W1.3.4]
│   └── aggregate.py           <- aggregation, validation, and post-filtering [owner: W1.3.5]
├── eval/
│   ├── per_step.py            <- per-step/per-field/runtime comparators [owner: W1.5.1]
│   ├── harness.py             <- count/row-aware evaluation harness [owner: W1.5.2]
│   ├── compare.py             <- gold-vs-agent comparison [owner: W1.5.3]
│   └── judge.py               <- typed LLM judge seam [owner: W1.5.3]
└── ui/
    └── app.py                 <- Streamlit fixed-path inspection [owner: W1.4.3]

tests/
├── conftest.py                <- fake LLM, TERMite, and API fixtures [owner: W1.5.4]
├── test_pipeline.py           <- fixed path and row-mode pipeline regressions [owner: W1.5.5]
├── test_stages.py             <- fixed stage and SME regression tests [owner: W1.5.6]
├── test_runtime_post_filters.py <- runtime closed-set/post-filter tests [owner: W1.5.7]
├── test_eval.py               <- evaluation harness/report tests [owner: W1.5.8]
├── test_per_step_eval.py      <- per-step comparator tests [owner: W1.5.9]
├── test_normalize.py          <- fixed normalizer policy tests [owner: W1.5.10]
├── test_services.py           <- service config/invariant tests [owner: W1.5.11]
├── test_taxonomy.py           <- taxonomy and hierarchy tests [owner: W1.5.12]
├── test_cli.py                <- fixed CLI option/output tests [owner: W1.5.13]
└── test_dag.py                <- fixed diagram export tests [owner: W1.5.14]
```

## File Inventory
| File | Layer | Purpose | Owner (WBS node) |
|------|-------|---------|------------------|
| `.env.example` | Config | Keys-only template for required full-run model and TERMite settings | W1.1.2 |
| `src/oppp/models.py` | Contracts | Row execution, runtime closed-set, post-filter, and result metadata contracts | W1.1.1 |
| `src/oppp/config.py` | Config | Lazy settings and clear required-credential failures | W1.1.2 |
| `src/oppp/normalize/base.py` | Normalization | Fixed normalizer interface and result model | W1.1.3 |
| `src/oppp/normalize/strategies.py` | Normalization | Fixed field/bucket normalization policy | W1.1.3 |
| `src/oppp/normalize/__init__.py` | Normalization | Fixed normalizer exports | W1.1.3 |
| `src/oppp/registry.py` | Infrastructure | Registry helper limited to non-public-stage selection use | W1.2.1 |
| `src/oppp/services/base.py` | Services | Service schema, field buckets, runtime metadata hooks | W1.2.2 |
| `src/oppp/services/__init__.py` | Services | Service package exports | W1.2.2 |
| `src/oppp/services/safety.py` | Services | Safety field map, TERMite map, facets, invariants | W1.2.3 |
| `src/oppp/services/pk.py` | Services | PK field map, TERMite map, facets, invariants | W1.2.3 |
| `src/oppp/services/rtb.py` | Services | RTB field map, TERMite map, invariant, where-clause serializer | W1.2.3 |
| `src/oppp/stages/expand.py` | Stage -1 | Fixed LLM expansion with fakeable test seam | W1.3.1 |
| `src/oppp/stages/enhance.py` | Stage 0 | Required TERMite enhancement with fakeable client seam | W1.3.2 |
| `src/oppp/stages/decompose.py` | Stage 1 | Fixed LLM decomposition and annotation reconciliation | W1.3.3 |
| `src/oppp/stages/translate.py` | Stage 2 | Input and runtime closed-set translation | W1.3.4 |
| `src/oppp/stages/aggregate.py` | Stage 3 | First-query aggregation, validation, and runtime post-filtering | W1.3.5 |
| `src/oppp/stages/__init__.py` | Stage exports | Fixed stage helper exports only | W1.3.7 |
| `src/oppp/execute.py` | Execution | Existing count execution plus bounded row/datapoint fetching | W1.3.6 |
| `src/oppp/pipeline.py` | Orchestration | Fixed two-pass pipeline wiring and result assembly | W1.4.1 |
| `src/oppp/cli.py` | Surface | CLI commands with fixed controls and runtime metadata output | W1.4.2 |
| `src/oppp/ui/app.py` | Surface | Streamlit fixed-path inspection and runtime panels | W1.4.3 |
| `src/oppp/dag.py` | Surface | Draw.io-aligned fixed flow export | W1.4.4 |
| `src/oppp/eval/per_step.py` | Evaluation | Per-step, per-field, and runtime comparator support | W1.5.1 |
| `src/oppp/eval/harness.py` | Evaluation | Count harness compatibility and report export with runtime metadata | W1.5.2 |
| `src/oppp/eval/compare.py` | Evaluation | Gold-vs-agent comparison with runtime/post-filter awareness | W1.5.3 |
| `src/oppp/eval/judge.py` | Evaluation | Typed LLM judge seam with injectable client | W1.5.3 |
| `tests/conftest.py` | Tests | Shared fake LLM, TERMite, count, row, and pipeline fixtures | W1.5.4 |
| `tests/test_pipeline.py` | Tests | Fixed-path, count-only, and row-mode pipeline regression tests | W1.5.5 |
| `tests/test_stages.py` | Tests | Stage behavior and resolved SME regression tests | W1.5.6 |
| `tests/test_runtime_post_filters.py` | Tests | Mocked datapoint/runtime post-filter tests | W1.5.7 |
| `tests/test_eval.py` | Tests | Evaluation/report regression tests | W1.5.8 |
| `tests/test_per_step_eval.py` | Tests | Per-step comparator and judge-stub regression tests | W1.5.9 |
| `tests/test_normalize.py` | Tests | Fixed normalizer policy regression tests | W1.5.10 |
| `tests/test_services.py` | Tests | Safety/PK/RTB config and invariant tests | W1.5.11 |
| `tests/test_taxonomy.py` | Tests | Taxonomy lookup, hierarchy, and candidate-window tests | W1.5.12 |
| `tests/test_cli.py` | Tests | CLI no-option and runtime-output tests | W1.5.13 |
| `tests/test_dag.py` | Tests | Diagram export no-pluggable-backend tests | W1.5.14 |

## Conventions
- Keep existing module names where possible; change behavior and exports rather
  than moving files.
- Public APIs expose fixed methods. External collaborators are faked by
  dependency injection, monkeypatching, or fixtures in tests, not by public
  `noop`, `gazetteer`, `deterministic`, or backend options.
- Add typed runtime contracts in `models.py`; do not pass ad-hoc row metadata
  dictionaries between stages.
- Keep row API parsing in `execute.py`; stages consume typed execution results.
- Keep count-only execution available for evaluation/debugging, but do not use
  probe-based open-field guards as the row-mode substitute.
- Do not add package dependencies unless row execution cannot be implemented with
  the standard library.
- Add no migrations; the project has no database.
- Keep `.env.example` keys-only and leave real `.env` out of version control.
