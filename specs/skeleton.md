# Project Skeleton

## Purpose
This skeleton is the implementation file map for runtime closed-set
post-filtering and the authoritative file-to-owner map for `specs/tasks.md`.
Every file listed here has exactly one WBS owner, and every `Owns` entry in the
WBS appears here.

## Directory Tree
```text
src/oppp/
├── models.py                 <- runtime row/post-filter contracts and PipelineResult metadata [owner: W1.1.1]
├── execute.py                <- count execution plus row/datapoint execution [owner: W1.1.2]
├── pipeline.py               <- two-pass orchestration for row/runtime mode [owner: W1.2.1]
├── cli.py                    <- CLI flags/output for row/runtime metadata [owner: W1.2.2]
├── stages/
│   ├── translate.py          <- input and runtime closed-set translation [owner: W1.1.3]
│   └── aggregate.py          <- query aggregation plus runtime post-filter application [owner: W1.1.4]
├── eval/
│   ├── per_step.py           <- per-step/runtime comparators [owner: W1.3.1]
│   └── harness.py            <- count harness compatibility and report export [owner: W1.3.2]
└── ui/
    └── app.py                <- Streamlit row/runtime inspection [owner: W1.2.3]

tests/
├── test_runtime_post_filters.py <- mocked row/runtime closed-set tests [owner: W1.3.3]
├── test_pipeline.py             <- pipeline regression tests [owner: W1.3.4]
├── test_stages.py               <- stage and resolved SME regression tests [owner: W1.3.5]
├── test_eval.py                 <- eval/report regression tests [owner: W1.3.6]
└── test_per_step_eval.py        <- per-step comparator regression tests [owner: W1.3.7]
```

## File Inventory
| File | Layer | Purpose | Owner (WBS node) |
|------|-------|---------|------------------|
| `src/oppp/models.py` | Contracts | Row execution, runtime closed-set, post-filter, and result metadata contracts | W1.1.1 |
| `src/oppp/execute.py` | Execution | Existing count execution plus bounded row/datapoint fetching | W1.1.2 |
| `src/oppp/stages/translate.py` | Stage 2 | Input closed-set translation and runtime closed-set translation | W1.1.3 |
| `src/oppp/stages/aggregate.py` | Stage 3 | First-query aggregation, count probes, runtime post-filtering | W1.1.4 |
| `src/oppp/pipeline.py` | Orchestration | Two-pass count/row pipeline wiring and result assembly | W1.2.1 |
| `src/oppp/cli.py` | Surface | Row/runtime CLI flags and output while preserving existing commands | W1.2.2 |
| `src/oppp/ui/app.py` | Surface | Stage -1 and runtime post-filter panels in Streamlit | W1.2.3 |
| `src/oppp/eval/per_step.py` | Evaluation | Per-step and runtime comparator support | W1.3.1 |
| `src/oppp/eval/harness.py` | Evaluation | Count harness compatibility and report export with runtime metadata | W1.3.2 |
| `tests/test_runtime_post_filters.py` | Tests | Mocked datapoint/runtime post-filter tests | W1.3.3 |
| `tests/test_pipeline.py` | Tests | Pipeline count-only and row-mode regression tests | W1.3.4 |
| `tests/test_stages.py` | Tests | Stage and clarified SME regression tests | W1.3.5 |
| `tests/test_eval.py` | Tests | Evaluation/report regression tests | W1.3.6 |
| `tests/test_per_step_eval.py` | Tests | Per-step comparator and judge-stub regression tests | W1.3.7 |

## Conventions
- Keep existing module names and registry keys stable.
- Add typed runtime contracts in `models.py`; do not pass ad-hoc row metadata
  dictionaries between stages.
- Keep row API parsing in `execute.py`; stages consume typed execution results.
- Keep count-only execution available and compatible.
- Do not add package dependencies unless row execution cannot be implemented with
  the standard library.
- Add no migrations; the project has no database.
- Keep `.env.example` keys-only and leave real `.env` out of version control.
