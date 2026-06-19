# Evaluation Criteria

## Sources
- `specs/requirements.md` (REQ-*/NFR-*)
- `specs/technical.md` (CONTRACT-*)
- `specs/constitution.md` (CONST-*)
- `specs/skeleton.md` (promised files)
- `specs/product.md` (capabilities, for tracing)

## How to read this file
Each row is one objectively-decidable check. `/evaluation` assigns
`PASS / PARTIAL / FAIL / N/A` per criterion (or `BLOCKED` if the criterion itself
is defective) and cites `file:line` evidence. This file defines **WHAT** to check;
`/evaluation` owns **HOW**. Criteria target the **current realised scope (Safety +
deterministic core + model backends + baseline UI)**; deferred items are in
*Out of Scope*.

## Criteria

| ID | Source ref | Category | Criterion (objectively decidable) | Evidence to look for | Severity |
|----|------------|----------|-----------------------------------|----------------------|----------|
| EVAL-001 | REQ-001, CONTRACT-RESULT | Requirement | `run_pipeline(query, service, *, enhancer, decomposer, translator, aggregator, normalizer)` exists and returns a `PipelineResult` carrying `enhanced`, `decomposition`, `subqueries`, `machine_query`, `issues`. | `src/oppp/pipeline.py:run_pipeline`; `src/oppp/models.py:PipelineResult` | BLOCKER |
| EVAL-002 | REQ-002, CONTRACT-MACHINE-QUERY/OPERATORS | Data contract | Stage-3 validation enforces exactly one top-level constraint, `OR`/`AND` ≥2 children, `NOT` exactly 1, operators drawn from `Operator` and upper-case. | `src/oppp/stages/aggregate.py` validation; `src/oppp/models.py:Operator` | BLOCKER |
| EVAL-003 | REQ-003, CONST-7, CONTRACT-ENHANCED | Constitution | `enhancer_registry` registers `noop` and `termite`; the pipeline's default enhancer is `noop`; `enhance` returns an `EnhancedQuery`. | `src/oppp/stages/enhance.py`; `src/oppp/pipeline.py` default | MAJOR |
| EVAL-004 | REQ-004, CONST-2 | Constitution | `decomposer_registry` registers `llm` and `gazetteer`; the `llm` decomposer performs no taxonomy import/lookup (vocab-free); `gazetteer` is documented as an offline double. | `src/oppp/stages/decompose.py` | BLOCKER |
| EVAL-005 | REQ-005, CONTRACT-DECOMP | Requirement | Only `type==filter` components are translated; `Decomposition.filters` is the iteration source in the pipeline. | `src/oppp/pipeline.py`; `src/oppp/models.py:Decomposition.filters` | MAJOR |
| EVAL-006 | REQ-006/024, CONST-1 | Constitution | Closed-vocab translation resolves the value via the taxonomy index and, on no match, does NOT emit a fabricated value (returns empty/flagged). | `src/oppp/stages/translate.py` closed path; `src/oppp/taxonomy/index.py` | BLOCKER |
| EVAL-007 | REQ-007, CONST-6 | Constitution | A generic class→members expansion over `parent_id`/`parent_name` exists and is invoked for class/roll-up fragments. | `src/oppp/taxonomy/index.py:expand_children`; call in `translate.py` | MAJOR |
| EVAL-008 | REQ-008, CONTRACT-GROUNDING | Data contract | Closed-vocab subqueries carry a `Grounding` block (`matched`, `expanded_from`, `confidence`). | `src/oppp/models.py:Grounding`; set in `translate.py` | MAJOR |
| EVAL-009 | REQ-009 | Requirement | Open-field translation emits `REGEX`/`RANGE`/`MATCH` as appropriate (no closed-vocab grounding attempted). | `src/oppp/stages/translate.py` open path | MAJOR |
| EVAL-010 | REQ-010 | Requirement | `normalizer_registry` has `noop` (default) + `fuzzy`; the normalizer runs on the fragment before value production and is conservative on open fields. | `src/oppp/normalize/strategies.py`; call in `translate.py` | MINOR |
| EVAL-011 | REQ-011, CONST-5 | Constitution | Stage 3 honours within-field boolean groups and combines fields under a top-level operator (default `AND`). | `src/oppp/stages/aggregate.py`; `models.py:BooleanGroup/AggregationPlan` | BLOCKER |
| EVAL-012 | REQ-012 | Requirement | Stage 3 routes fields with an `entity_name` into `entityFilters`, leaving direct fields in `query`. | `src/oppp/stages/aggregate.py`; `services/base.py:FieldSpec.entity_name` | MAJOR |
| EVAL-013 | REQ-013 | Requirement | Facets/displayColumns are attached from `question` components and constrained to the service facet allow-list. | `src/oppp/stages/aggregate.py`; `services/safety.py` allow-list | MAJOR |
| EVAL-014 | REQ-014, CONST-12 | Constitution | Stage 3 calls the service `invariants` hook; Safety provides one. | `src/oppp/stages/aggregate.py`; `services/safety.py:_safety_invariants` | MAJOR |
| EVAL-015 | REQ-015, CONST-3 | Constitution | The assembled query is validated, issues recorded as `ValidationIssue`, and `PipelineResult.ok` is false on any error-level issue. | `src/oppp/stages/aggregate.py`; `models.py:PipelineResult.ok` | BLOCKER |
| EVAL-016 | REQ-016 | Requirement | Each stage is selectable from the CLI; backend flags map to `run_pipeline` args. | `src/oppp/cli.py:run` options | MAJOR |
| EVAL-017 | REQ-017, CONST-8, NFR-001/003/005 | Non-functional | The full pipeline runs with `noop`/`gazetteer`/`deterministic` making no network or LLM call; heavy deps are imported lazily so the core imports without `llm`/`ui`/`viz`. | `stages/*.py` lazy imports; `llm.py`; `tests/test_pipeline.py` offline | BLOCKER |
| EVAL-018 | REQ-018 | Requirement | CLI exposes `enhance`, `decompose`, `field`, `aggregate` as standalone subcommands. | `src/oppp/cli.py` commands | MAJOR |
| EVAL-019 | REQ-019, CONST-9, CONTRACT-GOLD-PERFIELD | Requirement | `evaluate(...)` reads `inputs/sme_expected_cases.csv`, executes the query, compares `countTotal` to `s`, and reports valid/executed/exact/within-tolerance. | `src/oppp/eval/harness.py:evaluate`/`EvalReport` | MAJOR |
| EVAL-020 | REQ-022 | Requirement | The Streamlit app runs a question through `run_pipeline` and renders Stage-1/2/3 outputs. | `src/oppp/ui/app.py` | MINOR |
| EVAL-021 | REQ-025/027, CONST-10 | Constitution | Secrets are read lazily (only when a model/entity backend runs); the deterministic core needs none; `.env` is git-ignored. | `src/oppp/config.py`; `.gitignore` contains `.env` | BLOCKER |
| EVAL-022 | REQ-026, CONST-3 | Constitution | Every stage function signature consumes/returns a Pydantic model (no free-text boundary). | `stages/*.py` signatures vs `models.py` | MAJOR |
| EVAL-023 | CONTRACT-SUBQUERY | Data contract | `MachineSubquery.to_constraint()` emits the correct shape per operator (MATCH/REGEX/RANGE/DATE_RANGE/EMPTY). | `src/oppp/models.py:MachineSubquery.to_constraint` | MAJOR |
| EVAL-024 | CONTRACT-MACHINE-QUERY | Data contract | `MachineQuery.to_payload()` always includes `query` and `leafOnly`, and includes optional sections only when non-empty. | `src/oppp/models.py:MachineQuery.to_payload` | MAJOR |
| EVAL-025 | CONTRACT-TAXONOMY-CSV | Data contract | The taxonomy index loads `name,id,parent_id,parent_name` (hierarchical) / `name,id,count` (flat) from the configured inputs dir. | `src/oppp/taxonomy/index.py`; `inputs/*.csv` headers | MAJOR |
| EVAL-026 | CONTRACT-SERVICECONFIG, CONST-12 | Data contract | `ServiceConfig`/`FieldSpec` expose `bucket`, `taxonomy`, `entity_name`, `facet_allow_list`, `termite_type_map`, `invariants`, `search_url`. | `src/oppp/services/base.py` | MAJOR |
| EVAL-027 | CONTRACT-COMPONENT/ENHANCED/PLAN/TERMSELECT | Data contract | `Component`, `EnhancedQuery`, `AggregationPlan`, `TermSelection` exist with the documented fields. | `src/oppp/models.py` | MAJOR |
| EVAL-028 | CONTRACT-GOLD-PERSTEP | Data contract | `docs/sme_stage_cases.csv` exists with columns `nl query,counts,termite,decompose,translate,aggregate,machine query`. | `docs/sme_stage_cases.csv` header | MINOR |
| EVAL-029 | CONST-4 | Constitution | A single field is translatable in isolation via `oppp field`/`translate_one` without running other stages. | `src/oppp/cli.py:field`; `src/oppp/stages/translate.py:translate_one` | MAJOR |
| EVAL-031 | CONST-11, NFR-002 | Non-functional | Ruff (lint+format, line 100, `E,F,I,UP,B,SIM`) and pytest (`pythonpath=src`,`testpaths=tests`) are configured; the suite needs no network. | `pyproject.toml` `[tool.ruff]`/`[tool.pytest.ini_options]`; `tests/` | MAJOR |
| EVAL-032 | CONST-12 | Constitution | Stage modules contain no service-specific field/facet literals; per-service data lives only under `services/`. | `grep` `stages/*.py` for hardcoded field/facet lists | MINOR |
| EVAL-033 | skeleton (Phase 1) | Skeleton/Structure | All Phase-1 `src/oppp/**` files in `specs/skeleton.md` exist and import without error. | the listed module paths | MAJOR |
| EVAL-034 | skeleton (tests), NFR-001 | Skeleton/Structure | `tests/test_{taxonomy,stages,pipeline,eval}.py` exist and `pytest -q` passes offline. | `tests/`; a clean `pytest -q` run | MAJOR |
| EVAL-035 | skeleton (build) | Skeleton/Structure | `pyproject.toml` defines the `oppp` console script and the `llm`/`ui`/`viz`/`dev` extras. | `pyproject.toml` `[project.scripts]`, `[project.optional-dependencies]` | MINOR |

## Coverage Map

| Source item | Covered by |
|-------------|-----------|
| REQ-001 | EVAL-001 |
| REQ-002 | EVAL-002 |
| REQ-003 | EVAL-003 |
| REQ-004 | EVAL-004 |
| REQ-005 | EVAL-005 |
| REQ-006 | EVAL-006 |
| REQ-007 | EVAL-007 |
| REQ-008 | EVAL-008 |
| REQ-009 | EVAL-009 |
| REQ-010 (SHOULD) | EVAL-010 |
| REQ-011 | EVAL-011 |
| REQ-012 | EVAL-012 |
| REQ-013 | EVAL-013 |
| REQ-014 | EVAL-014 |
| REQ-015 | EVAL-015 |
| REQ-016 | EVAL-016 |
| REQ-017 | EVAL-017 |
| REQ-018 | EVAL-018 |
| REQ-019 | EVAL-019 |
| REQ-020/021/023 (SHOULD) | Out of Scope (Phase 3/4) |
| REQ-022 | EVAL-020 |
| REQ-024 | EVAL-006 |
| REQ-025 | EVAL-021 |
| REQ-026 | EVAL-022 |
| REQ-027 | EVAL-021 |
| NFR-001/003/005 | EVAL-017 |
| NFR-002 | EVAL-031 / EVAL-034 |
| NFR-004 | Out of Scope (no perf harness) |
| CONTRACT-COMPONENT/DECOMP | EVAL-027 / EVAL-005 |
| CONTRACT-SUBQUERY | EVAL-023 |
| CONTRACT-GROUNDING | EVAL-008 |
| CONTRACT-MACHINE-QUERY/OPERATORS | EVAL-002 / EVAL-024 |
| CONTRACT-ENHANCED/PLAN/TERMSELECT | EVAL-027 |
| CONTRACT-RESULT | EVAL-001 |
| CONTRACT-TAXONOMY-CSV | EVAL-025 |
| CONTRACT-SERVICECONFIG | EVAL-026 |
| CONTRACT-GOLD-PERFIELD | EVAL-019 |
| CONTRACT-GOLD-PERSTEP | EVAL-028 |
| CONST-1 | EVAL-006 |
| CONST-2 | EVAL-004 |
| CONST-3 | EVAL-015 / EVAL-022 |
| CONST-4 | EVAL-029 |
| CONST-5 | EVAL-011 |
| CONST-6 | EVAL-007 |
| CONST-7 | EVAL-003 |
| CONST-8 | EVAL-017 |
| CONST-9 | EVAL-019 (baseline); per-step+judge Out of Scope (Phase 3) |
| CONST-10 | EVAL-021 |
| CONST-11 | EVAL-031 |
| CONST-12 | EVAL-014 / EVAL-026 / EVAL-032 |
| Skeleton: Phase-1 src files | EVAL-033 |
| Skeleton: test files | EVAL-034 |
| Skeleton: pyproject | EVAL-035 |
| Skeleton: gold sets (perfield/perstep) | EVAL-019 / EVAL-028 |
| Skeleton: pk.py, rtb.py, eval/per_step.py, eval/judge.py, ui selectors, .env.example, test_per_step_eval.py, test_services.py | Out of Scope (Phase 2–5; not yet built) |

## Out of Scope
- **REQ-020/021/023 and per-step/judge evaluators** (`eval/per_step.py`,
  `eval/judge.py`, full UI selectors) — Phase 3/4; not yet built. N/A until then.
- **PK/RTB service configs** (`services/pk.py`, `services/rtb.py`,
  `tests/test_services.py`) — Phase 5. N/A.
- **`.env.example`** — Phase 2 (T022); N/A until created.
- **TERMite env-var-name mismatch & per-step dataset path mismatch** — known,
  tracked defects (`specs/technical.md` → Open Questions; `specs/plan.md` → Risks);
  the `termite` backend is optional and the core is unaffected, so not gated here.
- **TERMite live behaviour / API execution counts** — require external
  credentials and network; not auditable from the codebase alone.
- **NFR-004 latency** — no performance harness in scope.
