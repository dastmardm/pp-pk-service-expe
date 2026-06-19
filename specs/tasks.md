# Tasks

## Format
<!-- [ID] [P?] Description → file:path | done when: condition -->
<!-- [P] = can run in parallel (touches different files, no shared dependency) -->
<!-- Phase 1 items already exist in the codebase; their task is to CONFIRM the file
     satisfies its done-when (these are also the evaluation anchors). Phases 2–5 are
     net-new work. Every file here appears in specs/skeleton.md and vice versa. -->

## Phase 1 — Foundation (confirm built)
- [ ] T001 [P] Typed contracts (all `CONTRACT-*`) → `src/oppp/models.py` | done when: every model in `specs/technical.md` → Data Contracts is present and `MachineQuery.to_payload()` / `MachineSubquery.to_constraint()` exist.
- [ ] T002 [P] Settings + lazy `.env` load → `src/oppp/config.py` | done when: `OPPP_INPUTS_DIR` honoured; secrets read only via `get_settings`/`load_dotenv_if_present`, not at import.
- [ ] T003 [P] Generic pluggable registry → `src/oppp/registry.py` | done when: `register`/`add`/`create`/`names` work and unknown name raises `KeyError`.
- [ ] T004 [P] Taxonomy grounding + hierarchy expansion → `src/oppp/taxonomy/index.py` | done when: exact+fuzzy `lookup`, `is_class`, `expand_children` return `GroundingHit`s from the `inputs/` tables.
- [ ] T005 [P] Misspelling normalizers → `src/oppp/normalize/base.py`, `src/oppp/normalize/strategies.py` | done when: `noop` (default) and `fuzzy` registered; `fuzzy` is conservative on open fields.
- [ ] T006 Stage 0 enhance → `src/oppp/stages/enhance.py` | done when: `noop` (default) returns query unchanged; `termite` registered behind lazy import; output is `EnhancedQuery`.
- [ ] T007 Stage 1 decompose → `src/oppp/stages/decompose.py` | done when: `llm` (vocab-free) and `gazetteer` (offline double) registered; output is `Decomposition` of `Component`s with `type`/`reason`.
- [ ] T008 Stage 2 translate → `src/oppp/stages/translate.py` | done when: `tool` (LLM term-select) and `deterministic` registered; closed-vocab grounded+expanded, open→REGEX/RANGE/MATCH, no invented closed-vocab value.
- [ ] T009 Stage 3 aggregate → `src/oppp/stages/aggregate.py` | done when: `llm` and `deterministic` registered; boolean tree built, entityFilters routed, facets/displayColumns attached, invariants applied, query validated with `ValidationIssue`s.
- [ ] T010 [P] LLM/structured-output helper (lazy) → `src/oppp/llm.py` | done when: importing the deterministic core does not import this module's heavy deps.
- [ ] T011 Service config — Safety → `src/oppp/services/base.py`, `src/oppp/services/safety.py` | done when: `ServiceConfig`/`FieldSpec` defined; Safety registers fields, buckets, facet allow-list, termite type map, invariants hook, `search_url`.
- [ ] T012 Pipeline orchestration → `src/oppp/pipeline.py` | done when: `run_pipeline(query, service, *, enhancer, decomposer, translator, aggregator, normalizer)` returns a `PipelineResult` keeping every intermediate.
- [ ] T013 Execution → `src/oppp/execute.py` | done when: `execute_count` POSTs the payload (stdlib) and returns `countTotal`/error.
- [ ] T014 CLI → `src/oppp/cli.py` | done when: `run`, `enhance`, `decompose`, `field`, `aggregate`, `lookup`, `services`, `dag`, `eval` exist, each mapping backend flags to `run_pipeline` args.
- [ ] T015 [P] Count-based evaluation → `src/oppp/eval/harness.py`, `src/oppp/eval/compare.py` | done when: `evaluate(...)` scores executed `countTotal` vs gold `s`; gold-case lookup + per-field compare available.
- [ ] T016 [P] DAG export → `src/oppp/dag.py` | done when: `oppp dag` writes the component PNG (needs `viz` extra) without importing it in the core path.
- [ ] T017 Streamlit inspector (baseline) → `src/oppp/ui/app.py` | done when: typing a question and translating shows Stage-1/2/3 outputs; Service/Decomposer/Normalizer selectable.
- [ ] T018 [P] Offline test suite → `tests/test_taxonomy.py`, `tests/test_stages.py`, `tests/test_pipeline.py`, `tests/test_eval.py` | done when: `pytest -q` passes with no network and no model creds.
- [ ] T019 [P] Packaging + tool config → `pyproject.toml` | done when: `oppp` console script, extras (`llm`/`ui`/`viz`/`dev`), ruff (line 100; `E,F,I,UP,B,SIM`) and pytest (`pythonpath=src`,`testpaths=tests`) configured.

## Phase 2 — Production model backends
- [ ] T020 Reconcile TERMite env-var names → `src/oppp/config.py` (and `.env.example`) | done when: the names `config.py` reads match the documented `.env` template; the `termite` enhancer authenticates from `.env`.
- [ ] T021 Verify `llm` decompose + `llm` aggregate + `tool` translate live → `src/oppp/stages/decompose.py`, `src/oppp/stages/aggregate.py`, `src/oppp/stages/translate.py`, `src/oppp/llm.py` | done when: `oppp run "<q>"` (defaults) returns `ok=true`; falls back to deterministic structure on LLM failure.
- [ ] T022 [P] Env template → `.env.example` | done when: file lists every key from `specs/technical.md` → Configuration and Secrets, with no values, and is committed.

## Phase 3 — Per-step & judge evaluation
- [ ] T023 Per-step comparators → `src/oppp/eval/per_step.py` | done when: each stage's output is scored against its column in `docs/sme_stage_cases.csv` (set match / routing-type-boolean / set-F1 / structural).
- [ ] T024 LLM-as-judge → `src/oppp/eval/judge.py` | done when: a constrained judge returns a typed verdict (`match\|partial\|miss` + reason) for Stage-1 fragments, Stage-2 open-field patterns, and Stage-3 structure tie-breaks; logged and lazy-imported.
- [ ] T025 Reconcile per-step dataset location → `utils/build_sme_stage_cases.py` | done when: the builder writes `docs/sme_stage_cases.csv` (the documented location) and the per-step harness reads the same path.
- [ ] T026 [P] Per-step eval tests → `tests/test_per_step_eval.py` | done when: comparators are unit-tested offline; the judge is exercised with a stub/fake so the test stays hermetic.

## Phase 4 — Inspection UI completion
- [ ] T027 UI per-step selectors + Stage-0 panel + gold-set picker → `src/oppp/ui/app.py` | done when: Enhancer/Translator/Aggregator/Execute are selectable, a Stage-0 output panel renders annotations, and a gold-set question picker loads a case.

## Phase 5 — Coverage expansion
- [ ] T028 [P] PK service config → `src/oppp/services/pk.py` | done when: a PK `ServiceConfig` registers PK fields/buckets/facets/invariants (concomitants, tissueSpecific, metabolitesEnantiomers).
- [ ] T029 [P] RTB service config + serializer → `src/oppp/services/rtb.py` | done when: an RTB `ServiceConfig` emits the `where_clause` surface from the same filter set.
- [ ] T030 [P] Service-config tests → `tests/test_services.py` | done when: PK and RTB produce valid queries for a sample question offline.

## Dependencies
- T001–T019 underpin everything; they exist already and gate Phases 2–5.
- T020 gates T021 (TERMite auth). T022 supports T020.
- T023 depends on T015 (eval scaffolding) and T025 (dataset location). T024 depends on T010/T021 (LLM access) but must stay test-stubbable. T026 depends on T023/T024.
- T027 depends on T006–T009/T012 (all stages run via the pipeline).
- T028/T029 depend on T011 (the `ServiceConfig` contract). T030 depends on T028/T029.

## Parallel opportunities
- T001–T005, T010, T016, T018, T019 touch independent files → parallel.
- T028, T029, T030 (different service files) → parallel after T011.
- T022 parallel with T020; T026 parallel once T023/T024 land.
