# Project Skeleton

## Purpose

The agreed file map for `oppp`: what `/implement` must produce/modify and
`/evaluation` will verify. Most leaves already exist (Phase 1); those marked
*(new)* / *(modify)* are the Phases 2–5 deltas. Every file here has a task in
`specs/tasks.md` and vice versa.

## Directory Tree

```
.
├── pyproject.toml                  ← packaging, deps, extras, ruff/pytest config           [T019]
├── .env.example                    ← env template (keys only, no values)            (new)  [T022]
├── src/oppp/
│   ├── __init__.py                 ← package marker / version
│   ├── models.py                   ← Pydantic contracts (all CONTRACT-*)                    [T001]
│   ├── config.py                   ← Settings + lazy .env load; OPPP_INPUTS_DIR             [T002] (modify: TERMite env names) [T020]
│   ├── registry.py                 ← generic Registry[T]                                    [T003]
│   ├── pipeline.py                 ← run_pipeline orchestration                             [T012]
│   ├── cli.py                      ← Typer CLI (run/enhance/decompose/field/aggregate/…)    [T014]
│   ├── execute.py                  ← POST payload, read countTotal (stdlib)                 [T013]
│   ├── dag.py                      ← component DAG → PNG (viz extra)                         [T016]
│   ├── llm.py                      ← lazy LLM/structured-output helper                      [T010]
│   ├── stages/
│   │   ├── __init__.py
│   │   ├── enhance.py              ← Stage 0: noop* | termite                               [T006]
│   │   ├── decompose.py            ← Stage 1: llm* (vocab-free) | gazetteer (double)        [T007]
│   │   ├── translate.py            ← Stage 2: tool* | deterministic; runs normalizer        [T008]
│   │   └── aggregate.py            ← Stage 3: llm* | deterministic; validates               [T009]
│   ├── services/
│   │   ├── __init__.py
│   │   ├── base.py                 ← ServiceConfig/FieldSpec + service_registry             [T011]
│   │   ├── safety.py               ← Safety service config                                  [T011]
│   │   ├── pk.py                   ← PK service config                                (new) [T028]
│   │   └── rtb.py                  ← RTB service config + where_clause serializer     (new) [T029]
│   ├── taxonomy/
│   │   ├── __init__.py
│   │   └── index.py                ← in-memory indices, fuzzy lookup, expansion            [T004]
│   ├── normalize/
│   │   ├── __init__.py
│   │   ├── base.py                 ← normalizer protocol + registry                        [T005]
│   │   └── strategies.py           ← noop* + fuzzy                                          [T005]
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── harness.py              ← count-based eval vs gold `s`                           [T015]
│   │   ├── compare.py              ← gold-case lookup + per-field compare                   [T015]
│   │   ├── per_step.py             ← per-step comparators vs docs/sme_stage_cases.csv (new) [T023]
│   │   └── judge.py                ← LLM-as-judge for free-text steps                 (new) [T024]
│   └── ui/
│       ├── __init__.py
│       └── app.py                  ← Streamlit inspector              [T017] (modify: selectors/Stage-0/picker) [T027]
├── tests/
│   ├── test_taxonomy.py            ← grounding/expansion (offline)                          [T018]
│   ├── test_stages.py              ← stage backends (offline)                               [T018]
│   ├── test_pipeline.py            ← end-to-end with doubles (offline)                      [T018]
│   ├── test_eval.py                ← count parsing + harness (offline)                      [T018]
│   ├── test_per_step_eval.py       ← per-step comparators + stubbed judge            (new) [T026]
│   └── test_services.py            ← PK/RTB configs (offline)                         (new) [T030]
├── utils/
│   └── build_sme_stage_cases.py    ← reshape per-field gold → per-step  (modify: write docs/) [T025]
├── inputs/                         ← controlled-vocabulary tables + per-field gold set (data; provided)
│   ├── drugs.csv  effects.csv  indications.csv  species.csv  route.csv
│   ├── sources.csv  toxicity_parameters.csv  dose_type.csv  document_year.csv
│   ├── fields.csv  query_criteria_fields.csv  enums.csv
│   └── sme_expected_cases.csv      ← CONTRACT-GOLD-PERFIELD
└── docs/
    └── sme_stage_cases.csv         ← CONTRACT-GOLD-PERSTEP (canonical per-step gold location; preliminary)
```

## File Inventory

| File | Layer | Purpose | Created/owned by |
|------|-------|---------|------------------|
| `src/oppp/models.py` | Contracts | All typed stage-boundary models | T001 |
| `src/oppp/config.py` | Config | Settings, inputs dir, lazy secrets | T002 / T020 |
| `src/oppp/registry.py` | Core | Pluggability primitive | T003 |
| `src/oppp/pipeline.py` | Core | Stage orchestration | T012 |
| `src/oppp/cli.py` | Surface | Terminal entry points | T014 |
| `src/oppp/execute.py` | Integration | Query execution / count | T013 |
| `src/oppp/dag.py` | Tooling | Component diagram export | T016 |
| `src/oppp/llm.py` | Integration | Lazy model/structured-output helper | T010 |
| `src/oppp/stages/enhance.py` | Stage 0 | Optional entity enhancement | T006 |
| `src/oppp/stages/decompose.py` | Stage 1 | Vocab-free decomposition (+offline double) | T007 |
| `src/oppp/stages/translate.py` | Stage 2 | Per-field translation + grounding | T008 |
| `src/oppp/stages/aggregate.py` | Stage 3 | Boolean assembly + validation | T009 |
| `src/oppp/services/base.py` | Config | ServiceConfig/FieldSpec + registry | T011 |
| `src/oppp/services/safety.py` | Config | Safety service data | T011 |
| `src/oppp/services/pk.py` | Config | PK service data | T028 |
| `src/oppp/services/rtb.py` | Config | RTB service data + serializer | T029 |
| `src/oppp/taxonomy/index.py` | Grounding | Vocabulary indices + expansion | T004 |
| `src/oppp/normalize/base.py` | Stage 2 | Normalizer protocol + registry | T005 |
| `src/oppp/normalize/strategies.py` | Stage 2 | noop + fuzzy normalizers | T005 |
| `src/oppp/eval/harness.py` | Eval | Count-based scoring | T015 |
| `src/oppp/eval/compare.py` | Eval | Gold-case lookup + per-field compare | T015 |
| `src/oppp/eval/per_step.py` | Eval | Per-step comparators | T023 |
| `src/oppp/eval/judge.py` | Eval | LLM-as-judge | T024 |
| `src/oppp/ui/app.py` | Surface | Streamlit inspector | T017 / T027 |
| `tests/test_*.py` | Tests | Offline behavioural suite | T018 / T026 / T030 |
| `pyproject.toml` | Build | Packaging + tool config | T019 |
| `.env.example` | Config | Env template | T022 |
| `utils/build_sme_stage_cases.py` | Tooling | Per-step gold-set builder | T025 |

## Conventions

- **Package layout.** `src/` layout; the package is `oppp`; `pytest` sets
  `pythonpath=src`. New stage backends register in their stage's registry; new
  services add a `ServiceConfig` under `services/` and register it — never fork
  stage code (CONST-12).
- **Naming.** Modules `lower_snake.py`; registry keys are short lowercase strings
  (`noop`, `gazetteer`, `tool`, `deterministic`, `llm`, `termite`, `fuzzy`).
  Backend names are the public contract (CLI flags + UI selectors use them
  verbatim).
- **Env template.** The committed template is **`.env.example`** at the repo root:
  every variable from `specs/technical.md` → Configuration and Secrets, keys only,
  no values. `/implement` and `/fix` consult it; the real `.env` is never
  committed (see `specs/git.md` → Never Commit).
- **Gold-set locations.** Per-field gold set: `inputs/sme_expected_cases.csv`.
  Per-step gold set: `docs/sme_stage_cases.csv` (the documented canonical
  location; the builder in `utils/` must write there — T025).
- **Migrations.** None — there is no database; "schema" means the Pydantic
  contracts in `models.py`. A contract change follows `constitution.md` → Schema /
  Data Contract Changes.
