# Technical Specification

## Sources

- `specs/product.md` — the File 1 product spec produced this run (upstream source
  of *what* and *why*).
- `./docs/` — the human-facing documentation tree the product spec was synthesised
  from. Concrete files read: `README.md`; `00-overview/{problem-statement,glossary}.md`;
  `01-current-system/{legacy-architecture,pain-points}.md`;
  `02-domain-inputs/{machine-query-schema,field-taxonomy,csv-catalog}.md`;
  `03-proposed-design/{architecture,stage-1-decomposition,stage-2-subquery-translation,stage-3-aggregation,grounding-and-tool-calling,misspelling-strategy}.md`;
  `04-examples/worked-examples.md`; `05-evaluation/gold-set-and-metrics.md`;
  `06-implementation/{tech-stack,build-status,streamlit-ui}.md`; `sme_stage_cases.csv`.
- Existing code (ground truth of what is implemented; folder `src/oppp/`, concrete
  files read): `models.py`, `config.py`, `registry.py`, `pipeline.py`, `cli.py`,
  `execute.py`, `dag.py`, `llm.py`, `stages/{enhance,decompose,translate,aggregate}.py`,
  `services/{base,safety}.py`, `taxonomy/index.py`, `normalize/{base,strategies}.py`,
  `eval/{harness,compare}.py`, `ui/app.py`.
- `pyproject.toml` (file) — packaging, dependencies, optional extras, ruff/pytest config.
- `tests/` (folder; files read: `test_taxonomy.py`, `test_stages.py`, `test_pipeline.py`, `test_eval.py`).
- `inputs/` (folder) — the controlled-vocabulary tables and the per-field SME gold set.
- `utils/` (folder; files read: `ppendium/__init__.py`, `ppendium/prompts.py`, `build_sme_stage_cases.py`) — the legacy monolith (reference) and the per-step gold-set builder.

## Architecture Overview

A linear pipeline of pluggable stages, each resolved by name from a registry and
each independently invokable. Production defaults are the model-backed design;
offline doubles keep the core hermetic.

```
NL query
  └─▶ Stage 0  enhance     (optional)  [noop* | termite]      → EnhancedQuery
        └─▶ Stage 1  decompose          [llm* | gazetteer]     → Decomposition (Components)
              └─▶ Stage 2  translate    [tool* | deterministic] per FILTER component → MachineSubquery
                    └─▶ Stage 3  aggregate [llm* | deterministic] → MachineQuery (+ validation issues)
                          └─▶ (optional) execute against the search service → countTotal
( * = production default )       normalize (misspelling) [noop* | fuzzy] runs inside Stage 2
```

- **Stages** are plain callables behind typed protocols, registered under string
  keys in per-stage registries (`enhancer_registry`, `decomposer_registry`,
  `translator_registry`, `aggregator_registry`, `normalizer_registry`). The
  pipeline resolves each by name from its arguments (`oppp/pipeline.py:run_pipeline`).
- **Stage 0 — enhance** (`stages/enhance.py`): `noop` (default; returns the query
  unchanged) or `termite` (entity recognition; prepends a recognised-entities hint
  block and attaches `EntityAnnotation`s). Optional.
- **Stage 1 — decompose** (`stages/decompose.py`): `llm` (default; **vocab-free**
  structured-output segmentation/routing) or `gazetteer` (**offline double only**;
  vocab-based exact+fuzzy detection — explicitly not the production behaviour).
- **Stage 2 — translate** (`stages/translate.py`): `tool` (default; closed-vocab
  grounding + hierarchy expansion + an LLM term-selector refining candidates) or
  `deterministic` (offline double; same grounding without the LLM selector). Runs
  the chosen **normalizer** on each fragment first.
- **Stage 3 — aggregate** (`stages/aggregate.py`): `llm` (default; the model
  decides only the boolean *structure* via an `AggregationPlan`, which is rendered
  and validated deterministically) or `deterministic` (offline double; structure
  derived from per-field boolean groups). Always validates the final query.
- **Per-service configuration** (`services/base.py`, `services/safety.py`): a
  `ServiceConfig` carries the field set, the per-field bucket map, taxonomy
  bindings, facet allow-list, entity-routing, the entity-type→field map, and the
  always-on invariants. Stage code is shared; only this data differs per service.
- **Grounding** (`taxonomy/index.py`): in-memory indices over the vocabulary
  tables, exact + fuzzy (rapidfuzz) look-up, and parent→children hierarchy
  expansion. Closed-vocab look-up is the enforced mechanism behind CAP-4.
- **Execution** (`execute.py`) and **evaluation** (`eval/harness.py`,
  `eval/compare.py`): POST the payload, read `countTotal`, score against the gold
  `s`.
- **Surfaces**: a command-line app (`cli.py`, Typer) and an interactive inspector
  (`ui/app.py`, Streamlit).

## Data Contracts

Named contracts the implementation must honour. Each is a typed boundary; the
final query is always validated regardless of how it was produced.

| Contract ID | What it governs | Definition |
|-------------|-----------------|------------|
| `CONTRACT-COMPONENT` | Stage 1 output unit | `Component{field:str, nl_fragment:str, type:"filter"\|"question", reason:str, source:str, boolean_group?:{id,op}}` (`models.py:Component`). |
| `CONTRACT-DECOMP` | Stage 1 output | `Decomposition{query, service, components:[Component]}` with `.filters` / `.questions` views (`models.py:Decomposition`). |
| `CONTRACT-SUBQUERY` | Stage 2 output unit | `MachineSubquery{field, operator∈Operator, value, pattern?, boolean_group?, entity_name?, collapse_to?, grounding?, notes?}` with `to_constraint()` → API constraint shape (`models.py:MachineSubquery`). |
| `CONTRACT-GROUNDING` | Auditable provenance for a grounded value | `Grounding{matched:[GroundingHit{name,id,parent_id,parent_name,score,match,count}], expanded_from:"class"\|"term"\|null, confidence:0..1}` (`models.py:Grounding`). |
| `CONTRACT-MACHINE-QUERY` | Stage 3 output / API payload | `MachineQuery{query, entityFilters, facets, displayColumns, sortColumns, leafOnly}` with `to_payload()` (`models.py:MachineQuery`). Exactly one top-level constraint in `query`; `OR`/`AND` ≥2 children, `NOT` exactly 1; operators upper-case. |
| `CONTRACT-OPERATORS` | Allowed constraint types | `MATCH, OR, AND, NOT, REGEX, RANGE, DATE_RANGE, EMPTY` (`models.py:Operator`). (`PROXIMITY` is documented as rarely-used and not modelled.) |
| `CONTRACT-ENHANCED` | Stage 0 output | `EnhancedQuery{text, annotations:[EntityAnnotation{surface,label,entity_type?}], source}` (`models.py:EnhancedQuery`). |
| `CONTRACT-PLAN` | Stage 3 LLM structure decision | `AggregationPlan{top_op, fields:[FieldCombine{field,op,negate}], facets, display_columns, reason}` (`models.py:AggregationPlan`). |
| `CONTRACT-TERMSELECT` | Stage 2 LLM term choice | `TermSelection{selected:[str], reason}` constrained to exact candidate spellings (`models.py:TermSelection`). |
| `CONTRACT-RESULT` | Full run artefact | `PipelineResult{query, service, enhanced?, decomposition, subqueries, machine_query?, issues}` with `.ok` (`models.py:PipelineResult`). |
| `CONTRACT-TAXONOMY-CSV` | Vocabulary tables | Hierarchical tables share `name,id,parent_id,parent_name`; flat tables `name,id,count`. Located under `inputs/` (overridable by `OPPP_INPUTS_DIR`). `name`=preferred label sent to the API; `id`=stable key. |
| `CONTRACT-GOLD-PERFIELD` | Per-field evaluation reference | `inputs/sme_expected_cases.csv`: `query_number,query_type,question,s,comment,mapping_comment` + one column per field. `s`=expected result count. |
| `CONTRACT-GOLD-PERSTEP` | Per-step evaluation reference | `docs/sme_stage_cases.csv`: `nl query,counts,termite,decompose,translate,aggregate,machine query` — one column per pipeline step. Preliminary. |
| `CONTRACT-SERVICECONFIG` | Per-service data | `ServiceConfig{name, search_url, fields:{name:FieldSpec}, facet_allow_list, termite_type_map, invariants}`; `FieldSpec{name, bucket∈"closed"\|"open"\|"enum"\|"boolean", taxonomy?, value_field?, fuzzy_wildcard, entity_name?, enum_values, facetable, display_column?, rollup_to_siblings}` (`services/base.py`). |

## Schema

The schema is the set of Pydantic v2 models in `src/oppp/models.py` (enumerated in
the contracts table above) plus the `ServiceConfig`/`FieldSpec` dataclasses in
`src/oppp/services/base.py`. There is no database; persistent data is the set of
controlled-vocabulary tables and gold-set files under `inputs/` and `docs/`.
Validation is by Pydantic model construction at every stage boundary; the final
machine query additionally passes Stage 3 structural validation
(`stages/aggregate.py`), which emits `ValidationIssue` records consumed by
`PipelineResult.ok`.

## Component Interfaces

| Interface | Signature (essential) | Backends |
|-----------|------------------------|----------|
| Enhancer | `enhance(query:str, service:ServiceConfig) -> EnhancedQuery` | `noop`, `termite` |
| Decomposer | `decompose(query:str, service:ServiceConfig) -> Decomposition` | `llm`, `gazetteer` |
| Translator | `translate(component:Component, service:ServiceConfig, normalizer) -> MachineSubquery\|None` | `tool`, `deterministic` |
| Aggregator | `aggregate(decomp:Decomposition, subqueries:[MachineSubquery], service:ServiceConfig) -> (MachineQuery, [ValidationIssue])` | `llm`, `deterministic` |
| Normalizer | `normalize(fragment:str, field:str, bucket:str, context) -> {normalized, candidates?, changed, confidence, note?}` | `noop`, `fuzzy` |
| TaxonomyIndex | `lookup(term, limit)`, `is_class(term)`, `expand_children(term)` → `[GroundingHit]` | per-taxonomy in-memory index |
| Registry[T] | `register(name)` / `add(name,factory)` / `create(name,**kw)` / `names()` | generic, one per stage + services |
| Pipeline | `run_pipeline(query, service, *, enhancer, decomposer, translator, aggregator, normalizer) -> PipelineResult` | sequential runner (+ optional graph) |
| Execution | `execute_count(machine_query, service, *, timeout) -> ExecutionResult{ok,count_total,status,error}` | stdlib HTTP POST |
| Evaluation | `evaluate(*, service, enhancer, decomposer, translator, aggregator, normalizer, tolerance, execute, limit) -> EvalReport` | count-based harness |

The CLI (`cli.py`) exposes one subcommand per surface: `run`, `enhance`,
`decompose`, `field`, `aggregate`, `lookup`, `services`, `dag`, `eval`. Each
backend selection is a flag that maps one-to-one to a `run_pipeline` argument.

## Infrastructure

- A single installable Python package (`oppp`, `src/` layout), Python ≥ 3.11.
- **No** database, message broker, container, or cluster. Execution against the
  search service is a plain HTTP POST from the local process (stdlib only).
- Optional capability is gated behind extras so the deterministic core installs
  and runs alone: `llm` (model + orchestration + tool-calling + prompt
  optimisation), `ui` (interactive inspector), `viz` (diagram export), `dev`
  (linter + test runner). Heavy dependencies are imported lazily.

## Configuration and Secrets

- **Inputs location.** `OPPP_INPUTS_DIR` overrides the default `inputs/` directory
  (`config.py:get_settings`).
- **Model provider (Portkey).** `PORTKEY_ENDPOINT`, `PORTKEY_API_KEY`,
  `PORTKEY_PROVIDER`, `TOOL_MODEL` — read only when a model-backed backend runs.
- **Entity recognition (TERMite).** `config.py` currently reads `TERMITE_HOME`,
  `TERMITE_AUTH_URL`, `TERMITE_CLIENT_NAME`, `TERMITE_CLIENT_SECRET`.
- Secrets are loaded best-effort from the project `.env` (`config.py:load_dotenv_if_present`)
  and **only** when a model/entity backend is selected. The deterministic core
  never needs them. `.env` is never committed.
- **Env template.** A committed `\.env.example` (keys only, no values) is the
  documented template for the variables above; see `specs/skeleton.md` → Conventions.

## Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python ≥ 3.11 | Matches the legacy system, the data-science workflow, and the available NER/LLM/vocabulary tooling. |
| Typed boundaries | Pydantic v2 models at every stage edge | Validation replaces the legacy regex/brace JSON scraping; the schema *is* the contract end-to-end (docs/06 → Structured output). |
| Pluggability | A tiny string-keyed `Registry[T]` per stage | Selecting/ swapping a step is a config change, not a code edit — the precondition for step isolation (docs/06 → Pluggability). |
| Per-service variation | `ServiceConfig`/`FieldSpec` data objects | The pipeline shape is identical across Safety/PK/RTB; only data differs, so config carries it and stage code stays shared (docs/03 → architecture). |
| Vocabulary look-up | In-memory indices + rapidfuzz | Tables are small/medium; exact+prefix+fuzzy covers most cases with no external service (docs/03 → grounding). |
| Closed-vocab grounding | Look-up tool whose output *is* the value | Makes grounding *enforced*, not *encouraged*; yields an auditable provenance block (docs/03 → grounding). |
| Decomposition | Vocab-free structured-output model step; offline `gazetteer` double | Keeps "what is asked" separate from "how to express it"; the double keeps tests hermetic (docs/03 → stage-1). |
| Aggregation structure | Model decides structure only; rendered+validated deterministically | The output is always a legal query even though the boolean shape is model-decided (docs/03 → stage-3). |
| CLI | Typer | One subcommand per stage/surface for isolation from the terminal (docs/06 → tech-stack). |
| Interactive UI | Streamlit | Run + inspect every stage; the design's debugging surface (docs/06 → streamlit-ui). |
| HTTP execution | stdlib `urllib` | Keeps the core dependency-free; only a count is needed (`execute.py`). |
| Env/packaging | `uv` + `pyproject.toml` (hatchling) | Single source of truth for deps; extras gate heavy stacks. |
| Quality gates | Ruff (lint+format) + pytest | Enforce style and the offline test suite; both already configured in `pyproject.toml`. |
| Prompt optimisation | DSPy (designed-for) | Authoring model steps as optimisable programs; per-step isolation makes tuning one step tractable (docs/06 → tech-stack). |
| LLM-as-judge | Constrained typed-verdict judge for free-text steps | Free-text outputs (Stage 1 fragments, Stage 2 open-field patterns, Stage 3 structure tie-breaks) have no canonical form (docs/05). |

## Open Questions

Product-design open items are listed in `specs/product.md` → Open Questions. The
following are **technical/implementation** open items observed against the current
code (not settled by `./docs/`):

- **Per-step gold-set location mismatch.** `./docs/` (the source of truth) places
  the per-step gold set at `docs/sme_stage_cases.csv`, but `utils/build_sme_stage_cases.py`
  writes `inputs/sme_stage_cases.csv`. The evaluation design and skeleton follow
  the docs (`docs/sme_stage_cases.csv`); the builder's output path needs
  reconciling.
- **TERMite env-var naming mismatch.** `.env` defines `TERMITE_USERNAME`,
  `TERMITE_PASSWORD`, `TERMITE_URL`, `TERMITE_SAAS_LOGIN_URL`, but `config.py`
  reads `TERMITE_HOME`, `TERMITE_AUTH_URL`, `TERMITE_CLIENT_NAME`,
  `TERMITE_CLIENT_SECRET`. The TERMite backend cannot authenticate until these are
  reconciled. (TERMite is optional and was never verified live, per docs/06 →
  build-status.)
- **Per-step evaluators & LLM-as-judge are designed but not built.** The realised
  harness scores by result count only; the per-step comparators and the judge are
  the target (docs/05 → Status & next steps).
- **PK/RTB service configs and DSPy modules** are designed-for but not realised
  (Safety only).
