# Project Skeleton

## Purpose

The agreed file map for `oppp`: what `/implement` must produce/modify and
`/evaluation` will verify, **and** the authoritative file→owner map for the Work
Breakdown Structure (`../CONVENTIONS.md` → File-ownership invariant). Most leaves
already exist (confirm-built); those marked *(new)* / *(modify)* are the forward
deltas. Every file here has exactly one owning WBS node in `specs/tasks.md`, and the
union of all owners covers every file with none owned twice. The `Owner (WBS node)`
column below is the source of truth; a conflict with a node's `Owns` list in
`tasks.md` is a spec defect.

`inputs/**` and `docs/sme_stage_cases.csv` are **provided data** (consumed, not
created by the implementation) and are therefore shown for context but are **not**
owned WBS files — except that `docs/sme_stage_cases.csv` is the *output* of the
builder owned by W6.5 (the CSV itself is generated data, not a tracked source).

## Directory Tree

```
.
├── pyproject.toml                  ← packaging, deps, extras, ruff/pytest config   [owner: W1, convergent]
├── .env.example                    ← env template (keys only, no values)    (new)  [owner: W2.3]
├── src/oppp/
│   ├── __init__.py                 ← package marker / version                       [owner: W2.0]
│   ├── models.py                   ← Pydantic contracts (all CONTRACT-*)            [owner: W2.1]
│   ├── config.py                   ← Settings + lazy .env load; OPPP_INPUTS_DIR  (modify: TERMite env names)  [owner: W2.3]
│   ├── registry.py                 ← generic Registry[T]                            [owner: W2.2]
│   ├── llm.py                      ← lazy LLM/structured-output helper              [owner: W2.6]
│   ├── pipeline.py                 ← run_pipeline orchestration                     [owner: W5.1]
│   ├── cli.py                      ← Typer CLI                                      [owner: W5.2]
│   ├── execute.py                  ← POST payload, read countTotal (stdlib)         [owner: W5.3]
│   ├── dag.py                      ← component DAG → PNG (viz extra)                 [owner: W5.4]
│   ├── stages/
│   │   ├── __init__.py             ← barrel: re-export stage callables/registries   [owner: W4, convergent]
│   │   ├── enhance.py              ← Stage 0: noop* | termite                       [owner: W4.1]
│   │   ├── decompose.py            ← Stage 1: llm* (vocab-free) | gazetteer (double) [owner: W4.2]
│   │   ├── translate.py            ← Stage 2: tool* | deterministic; runs normalizer [owner: W4.3]
│   │   └── aggregate.py            ← Stage 3: llm* | deterministic; validates       [owner: W4.4]
│   ├── services/
│   │   ├── __init__.py             ← barrel: register services on import            [owner: W3, convergent]
│   │   ├── base.py                 ← ServiceConfig/FieldSpec + service_registry      [owner: W3.1]
│   │   ├── safety.py               ← Safety service config                          [owner: W3.2]
│   │   ├── pk.py                   ← PK service config                        (new) [owner: W3.3]
│   │   └── rtb.py                  ← RTB service config + where_clause serializer (new) [owner: W3.4]
│   ├── taxonomy/
│   │   ├── __init__.py             ← taxonomy package surface                       [owner: W2.4]
│   │   └── index.py                ← in-memory indices, fuzzy lookup, expansion      [owner: W2.4]
│   ├── normalize/
│   │   ├── __init__.py             ← normalize package surface                      [owner: W2.5]
│   │   ├── base.py                 ← normalizer protocol + registry                 [owner: W2.5]
│   │   └── strategies.py           ← noop* + fuzzy                                   [owner: W2.5]
│   ├── eval/
│   │   ├── __init__.py             ← barrel: re-export eval surface                 [owner: W6, convergent]
│   │   ├── harness.py              ← count-based eval vs gold `s`                    [owner: W6.1]
│   │   ├── compare.py              ← gold-case lookup + per-field compare            [owner: W6.2]
│   │   ├── per_step.py             ← per-step comparators vs docs/sme_stage_cases.csv (new) [owner: W6.3]
│   │   └── judge.py                ← LLM-as-judge for free-text steps          (new) [owner: W6.4]
│   └── ui/
│       ├── __init__.py             ← ui package marker                              [owner: W5.5]
│       └── app.py                  ← Streamlit inspector       (modify: selectors/Stage-0/picker) [owner: W5.5]
├── tests/
│   ├── test_taxonomy.py            ← grounding/expansion (offline)                  [owner: W7.1]
│   ├── test_stages.py              ← stage backends (offline)                       [owner: W7.2]
│   ├── test_pipeline.py            ← end-to-end with doubles (offline)              [owner: W7.3]
│   ├── test_eval.py                ← count parsing + harness (offline)              [owner: W7.4]
│   ├── test_per_step_eval.py       ← per-step comparators + stubbed judge     (new) [owner: W7.5]
│   └── test_services.py            ← PK/RTB configs (offline)                  (new) [owner: W7.6]
├── utils/
│   └── build_sme_stage_cases.py    ← reshape per-field gold → per-step  (modify: write docs/)  [owner: W6.5]
├── inputs/                         ← controlled-vocabulary tables + per-field gold set (provided data; not owned)
│   ├── drugs.csv  effects.csv  indications.csv  species.csv  route.csv
│   ├── sources.csv  toxicity_parameters.csv  dose_type.csv  document_year.csv
│   ├── fields.csv  query_criteria_fields.csv  enums.csv
│   └── sme_expected_cases.csv      ← CONTRACT-GOLD-PERFIELD (provided data)
└── docs/
    └── sme_stage_cases.csv         ← CONTRACT-GOLD-PERSTEP (generated by W6.5; canonical per-step gold location; preliminary)
```

## File Inventory

| File | Layer | Purpose | Owner (WBS node) |
|------|-------|---------|------------------|
| `pyproject.toml` | Build | Packaging, deps, extras, ruff/pytest config (convergent manifest) | W1 |
| `.env.example` | Config | Env template (keys only) | W2.3 |
| `src/oppp/__init__.py` | Core | Package marker / version | W2.0 |
| `src/oppp/models.py` | Contracts | All typed stage-boundary models | W2.1 |
| `src/oppp/registry.py` | Core | Pluggability primitive | W2.2 |
| `src/oppp/config.py` | Config | Settings, inputs dir, lazy secrets | W2.3 |
| `src/oppp/taxonomy/__init__.py` | Grounding | Taxonomy package surface | W2.4 |
| `src/oppp/taxonomy/index.py` | Grounding | Vocabulary indices + expansion | W2.4 |
| `src/oppp/normalize/__init__.py` | Stage 2 | Normalize package surface | W2.5 |
| `src/oppp/normalize/base.py` | Stage 2 | Normalizer protocol + registry | W2.5 |
| `src/oppp/normalize/strategies.py` | Stage 2 | noop + fuzzy normalizers | W2.5 |
| `src/oppp/llm.py` | Integration | Lazy model/structured-output helper | W2.6 |
| `src/oppp/services/__init__.py` | Config | Service barrel (registers on import) — convergent | W3 |
| `src/oppp/services/base.py` | Config | ServiceConfig/FieldSpec + registry | W3.1 |
| `src/oppp/services/safety.py` | Config | Safety service data | W3.2 |
| `src/oppp/services/pk.py` | Config | PK service data | W3.3 |
| `src/oppp/services/rtb.py` | Config | RTB service data + serializer | W3.4 |
| `src/oppp/stages/__init__.py` | Stages | Stage barrel (re-exports) — convergent | W4 |
| `src/oppp/stages/enhance.py` | Stage 0 | Optional entity enhancement | W4.1 |
| `src/oppp/stages/decompose.py` | Stage 1 | Vocab-free decomposition (+offline double) | W4.2 |
| `src/oppp/stages/translate.py` | Stage 2 | Per-field translation + grounding | W4.3 |
| `src/oppp/stages/aggregate.py` | Stage 3 | Boolean assembly + validation | W4.4 |
| `src/oppp/pipeline.py` | Core | Stage orchestration | W5.1 |
| `src/oppp/cli.py` | Surface | Terminal entry points | W5.2 |
| `src/oppp/execute.py` | Integration | Query execution / count | W5.3 |
| `src/oppp/dag.py` | Tooling | Component diagram export | W5.4 |
| `src/oppp/ui/__init__.py` | Surface | UI package marker | W5.5 |
| `src/oppp/ui/app.py` | Surface | Streamlit inspector | W5.5 |
| `src/oppp/eval/__init__.py` | Eval | Eval barrel (re-exports) — convergent | W6 |
| `src/oppp/eval/harness.py` | Eval | Count-based scoring | W6.1 |
| `src/oppp/eval/compare.py` | Eval | Gold-case lookup + per-field compare | W6.2 |
| `src/oppp/eval/per_step.py` | Eval | Per-step comparators | W6.3 |
| `src/oppp/eval/judge.py` | Eval | LLM-as-judge | W6.4 |
| `utils/build_sme_stage_cases.py` | Tooling | Per-step gold-set builder | W6.5 |
| `tests/test_taxonomy.py` | Tests | Grounding/expansion (offline) | W7.1 |
| `tests/test_stages.py` | Tests | Stage backends (offline) | W7.2 |
| `tests/test_pipeline.py` | Tests | End-to-end with doubles (offline) | W7.3 |
| `tests/test_eval.py` | Tests | Count parsing + harness (offline) | W7.4 |
| `tests/test_per_step_eval.py` | Tests | Per-step comparators + stubbed judge | W7.5 |
| `tests/test_services.py` | Tests | PK/RTB configs (offline) | W7.6 |

## Conventions

- **Package layout.** `src/` layout; the package is `oppp`; `pytest` sets
  `pythonpath=src`. New stage backends register in their stage's registry; new
  services add a `ServiceConfig` under `services/` and register it — never fork
  stage code (CONST-12).
- **`__init__.py` barrels.** A package `__init__.py` that re-exports/registers from
  its sibling modules is a **convergent barrel** owned by that subtree's summary node
  (`services/__init__.py` → W3, `stages/__init__.py` → W4, `eval/__init__.py` → W6);
  its `Contributors` are the leaves whose symbols it re-exports, and it is assembled
  append-only during the summary's aggregate step. A package `__init__.py` that re-
  exports only from one leaf's own modules (`taxonomy/`, `normalize/`) is owned by
  that leaf, written together with them; pure markers (`oppp/__init__.py`,
  `ui/__init__.py`) are owned by their nearest leaf.
- **Naming.** Modules `lower_snake.py`; registry keys are short lowercase strings
  (`noop`, `gazetteer`, `tool`, `deterministic`, `llm`, `termite`, `fuzzy`).
  Backend names are the public contract (CLI flags + UI selectors use them verbatim).
- **Env template.** The committed template is **`.env.example`** at the repo root:
  every variable from `specs/technical.md` → Configuration and Secrets, keys only, no
  values. `/implement` and `/fix` consult it; the real `.env` is never committed (see
  `specs/git.md` → Never Commit).
- **Gold-set locations.** Per-field gold set: `inputs/sme_expected_cases.csv`
  (provided). Per-step gold set: `docs/sme_stage_cases.csv` (the documented canonical
  location; the builder in `utils/` — W6.5 — must write there).
- **Migrations.** None — there is no database; "schema" means the Pydantic contracts
  in `models.py`. A contract change follows `constitution.md` → Schema / Data Contract
  Changes (change the model → update the `CONTRACT-*` entry → update the affected
  `EVAL-NNN` → run the Quality Gates). There is therefore no migration-file naming
  convention.
