# Tasks

## Overview

The project's work is decomposed as a **Work Breakdown Structure** (WBS) tree cut by
**architectural layer**, because `oppp`'s files group cleanly by layer and a layer cut
keeps every node's owned files disjoint while making the dependency order explicit
(foundation → services → stages → integration → evaluation → tests). Most leaves are
**confirm-built** (the file exists; the node verifies its `Done-when`); the leaves that
create net-new files (`services/pk.py`, `services/rtb.py`, `eval/per_step.py`,
`eval/judge.py`, `.env.example`) and the modify leaves (`config.py` TERMite names,
`ui/app.py` selector completion, `utils/build_sme_stage_cases.py` output path) are the
forward work. The convergent files are the package barrels (`services/__init__.py`,
`stages/__init__.py`, `eval/__init__.py`) and the project manifest (`pyproject.toml`),
each owned by the nearest common ancestor of its contributors.

```
W1 (root)              — oppp NL→machine-query translator
  W2 (summary)         — Foundation & shared contracts
    W2.0 (leaf)        — package marker
    W2.1 (leaf)        — typed contracts (models)
    W2.2 (leaf)        — pluggable registry
    W2.3 (leaf)        — settings + env template
    W2.4 (leaf)        — taxonomy grounding + expansion
    W2.5 (leaf)        — misspelling normalizers
    W2.6 (leaf)        — lazy LLM/structured-output helper
  W3 (summary)         — Service configuration
    W3.1 (leaf)        — ServiceConfig/FieldSpec + registry
    W3.2 (leaf)        — Safety service
    W3.3 (leaf)        — PK service
    W3.4 (leaf)        — RTB service + serializer
  W4 (summary)         — Pipeline stages
    W4.1 (leaf)        — Stage 0 enhance
    W4.2 (leaf)        — Stage 1 decompose
    W4.3 (leaf)        — Stage 2 translate
    W4.4 (leaf)        — Stage 3 aggregate
  W5 (summary)         — Integration & surfaces
    W5.1 (leaf)        — pipeline orchestration
    W5.2 (leaf)        — CLI
    W5.3 (leaf)        — execution
    W5.4 (leaf)        — DAG export
    W5.5 (leaf)        — Streamlit inspector
  W6 (summary)         — Evaluation
    W6.1 (leaf)        — count-based harness
    W6.2 (leaf)        — gold-case lookup + per-field compare
    W6.3 (leaf)        — per-step comparators
    W6.4 (leaf)        — LLM-as-judge
    W6.5 (leaf)        — per-step gold-set builder
  W7 (summary)         — Offline test suite
    W7.1..W7.6 (leaf)  — taxonomy / stages / pipeline / eval / per-step / services tests
```

The outline is a reading aid; the per-node `Parent`/`Children` fields below are
authoritative. The combined dependency graph (parent-after-children ∪ `After` ∪
cross-tree) is acyclic and flows foundation → … → tests.

## Nodes

### W1 — oppp NL→machine-query translator
- **Type**: root
- **Parent**: none
- **Children**: W2, W3, W4, W5, W6, W7
- **Owns**: `pyproject.toml`
- **Contributors** (`pyproject.toml`): W2, W3, W4, W5, W6, W7 — each subtree reports the
  dependency set it needs (core: pydantic/typer/rapidfuzz/python-dotenv; `llm` extra:
  langchain*/langgraph/dspy/openai; `ui` extra: streamlit; `viz` extra: matplotlib;
  `dev` extra: ruff/pytest). The root declares the union into `pyproject.toml` and runs
  **one** resolver invocation (`uv lock` then `uv pip install -e '.[dev]'`).
- **After**: none
- **Review**: full tree resolved; `ruff check src tests` and `ruff format --check src tests`
  report no findings; `pytest -q` passes with no network and no model credentials;
  `oppp run --decomposer gazetteer --translator deterministic --aggregator deterministic --no-execute "<safety question>"`
  returns a `PipelineResult` with `ok=true` and a `query` carrying exactly one top-level constraint.
- **Done-when**: every child reports success and the Review assertions hold.

### W2 — Foundation & shared contracts
- **Type**: summary
- **Parent**: W1
- **Children**: W2.0, W2.1, W2.2, W2.3, W2.4, W2.5, W2.6
- **Owns**: none
- **After**: none
- **Review**: `python -c "import oppp.models, oppp.registry, oppp.config, oppp.taxonomy.index, oppp.normalize.strategies"`
  succeeds with only the core deps installed (no langchain/streamlit/matplotlib importable);
  `oppp.models` exposes every `CONTRACT-*` model from `specs/technical.md`; a known term
  resolves through `taxonomy.index.lookup` to a `GroundingHit`.
- **Done-when**: all children resolved and the Review holds.

### W2.0 — Package marker
- **Type**: leaf
- **Parent**: W2
- **Children**: none
- **Owns**: `src/oppp/__init__.py`
- **REQ**: Structural: top-level package marker / version string (traces to no functional requirement).
- **After**: none
- **Done-when**: `import oppp` succeeds and exposes `__version__`.

### W2.1 — Typed contracts (models)
- **Type**: leaf
- **Parent**: W2
- **Children**: none
- **Owns**: `src/oppp/models.py`
- **REQ**: REQ-002, REQ-026 (defines every `CONTRACT-*` boundary type)
- **After**: none
- **Done-when**: every model in `specs/technical.md` → Data Contracts is present;
  `MachineQuery.to_payload()` and `MachineSubquery.to_constraint()` exist; `Operator`
  enumerates `MATCH,OR,AND,NOT,REGEX,RANGE,DATE_RANGE,EMPTY`; constructing each model
  validates its fields. Verifiable by import + attribute inspection.

### W2.2 — Pluggable registry
- **Type**: leaf
- **Parent**: W2
- **Children**: none
- **Owns**: `src/oppp/registry.py`
- **REQ**: REQ-016 (the by-name selection primitive)
- **After**: none
- **Done-when**: `register`/`add`/`create`/`names` work; resolving an unknown name raises
  `KeyError`. Verifiable by a focused unit exercise.

### W2.3 — Settings + env template
- **Type**: leaf
- **Parent**: W2
- **Children**: none
- **Owns**: `src/oppp/config.py`, `.env.example`
- **REQ**: REQ-025, REQ-027
- **After**: none
- **Done-when**: `OPPP_INPUTS_DIR` overrides the inputs dir; secrets are read only via
  `get_settings`/`load_dotenv_if_present` (not at import); the TERMite env-var names
  `config.py` reads match `.env.example`; `.env.example` lists **every** key from
  `specs/technical.md` → Configuration and Secrets with **no values** and is committed.

### W2.4 — Taxonomy grounding + expansion
- **Type**: leaf
- **Parent**: W2
- **Children**: none
- **Owns**: `src/oppp/taxonomy/index.py`, `src/oppp/taxonomy/__init__.py`
- **REQ**: REQ-006, REQ-007, REQ-008
- **After**: W2.1
- **Done-when**: exact + fuzzy (rapidfuzz) `lookup`, `is_class`, and generic
  `expand_children` over `parent_id`/`parent_name` return `GroundingHit`s loaded from the
  configured inputs dir; hierarchical tables parse `name,id,parent_id,parent_name`, flat
  tables `name,id,count`. Exposes the index interface Stage 2 consumes.

### W2.5 — Misspelling normalizers
- **Type**: leaf
- **Parent**: W2
- **Children**: none
- **Owns**: `src/oppp/normalize/base.py`, `src/oppp/normalize/strategies.py`, `src/oppp/normalize/__init__.py`
- **REQ**: REQ-010
- **After**: W2.2, W2.4
- **Done-when**: `normalizer_registry` registers `noop` (default) and `fuzzy`; the
  `normalize(fragment, field, bucket, context)` contract is honoured; `fuzzy` is
  conservative on the `open` bucket. Verifiable on typo fixtures offline.

### W2.6 — Lazy LLM/structured-output helper
- **Type**: leaf
- **Parent**: W2
- **Children**: none
- **Owns**: `src/oppp/llm.py`
- **REQ**: REQ-017 (preserves the no-network/lazy-import guarantee for model-backed backends)
- **After**: W2.1
- **Done-when**: importing the deterministic core (`oppp.models`, `oppp.pipeline` driven
  by the doubles) does **not** import `langchain*`/`dspy`/`openai`; the module exposes a
  structured-output helper bound to a Pydantic model behind a lazy import. Exposes the
  interface W4.2/W4.3/W4.4/W6.4 call.

### W3 — Service configuration
- **Type**: summary
- **Parent**: W1
- **Children**: W3.1, W3.2, W3.3, W3.4
- **Owns**: `src/oppp/services/__init__.py`  *(convergent barrel — registers services on import)*
- **Contributors** (`src/oppp/services/__init__.py`): W3.1, W3.2 *(extended to W3.3/W3.4 as those land)* — append-only re-exports/registration collected from child reports.
- **After**: none
- **Review**: `service_registry` resolves `safety` (and `pk`/`rtb` once built) to a
  `ServiceConfig` exposing `fields`/`bucket` map, `facet_allow_list`, entity routing,
  `termite_type_map`, `invariants`, and `search_url`; no module under `services/` imports
  stage code.
- **Done-when**: children resolved; the barrel re-exports every contributed service and the Review holds.

### W3.1 — ServiceConfig/FieldSpec + registry
- **Type**: leaf
- **Parent**: W3
- **Children**: none
- **Owns**: `src/oppp/services/base.py`
- **REQ**: REQ-014, REQ-016 (the per-service data contract + service registry; CONST-12)
- **After**: none
- **Done-when**: `ServiceConfig` and `FieldSpec` are defined with the fields listed in
  `CONTRACT-SERVICECONFIG`; `service_registry`/`get_service` resolve a service by name.
  Exposes the `ServiceConfig`/`FieldSpec` interface every stage consumes.

### W3.2 — Safety service
- **Type**: leaf
- **Parent**: W3
- **Children**: none
- **Owns**: `src/oppp/services/safety.py`
- **REQ**: REQ-001, REQ-012, REQ-013, REQ-014
- **After**: W3.1
- **Done-when**: a Safety `ServiceConfig` registers its field set, per-field buckets,
  facet allow-list (`drugs, species, sources, effects, route, doseType, documentYear`),
  TERMite type map, the always-on invariants hook, and `search_url`.

### W3.3 — PK service
- **Type**: leaf
- **Parent**: W3
- **Children**: none
- **Owns**: `src/oppp/services/pk.py`
- **REQ**: Structural: designed-for PK service config (`specs/plan.md` → Coverage expansion; no current MUST requirement — Safety-only is the realised scope per `requirements.md` Non-Goals).
- **After**: W3.1
- **Done-when**: a PK `ServiceConfig` registers PK fields/buckets/facets and the PK
  invariants (concomitants Fasted-or-empty, tissueSpecific, metabolitesEnantiomers); a
  sample PK question assembles a valid query offline.

### W3.4 — RTB service + serializer
- **Type**: leaf
- **Parent**: W3
- **Children**: none
- **Owns**: `src/oppp/services/rtb.py`
- **REQ**: Structural: designed-for RTB service config + `where_clause` serializer (`specs/plan.md` → Coverage expansion; no current MUST requirement).
- **After**: W3.1
- **Done-when**: an RTB `ServiceConfig` emits the `where_clause` surface from the same
  filter set; a sample RTB question assembles a valid clause offline.

### W4 — Pipeline stages
- **Type**: summary
- **Parent**: W1
- **Children**: W4.1, W4.2, W4.3, W4.4
- **Owns**: `src/oppp/stages/__init__.py`  *(convergent barrel — re-exports stage callables/registries)*
- **Contributors** (`src/oppp/stages/__init__.py`): W4.2, W4.3, W4.4 *(and W4.1 as it exports through the barrel)* — append-only re-exports collected from child reports.
- **After**: none
- **Review**: each stage backend is registered under its documented name
  (`noop`/`termite`, `llm`/`gazetteer`, `tool`/`deterministic`, `llm`/`deterministic`)
  and consumes/returns the contracted Pydantic models; the offline doubles run with no
  network and no LLM call.
- **Done-when**: children resolved; the barrel re-exports every stage and the Review holds.

### W4.1 — Stage 0 enhance
- **Type**: leaf
- **Parent**: W4
- **Children**: none
- **Owns**: `src/oppp/stages/enhance.py`
- **REQ**: REQ-003 (CONST-7 — optional, `noop` default)
- **After**: none
- **Done-when**: `enhancer_registry` registers `noop` (default; returns the query
  unchanged, no annotations) and `termite` (behind a lazy import); the result is an
  `EnhancedQuery`. Verifiable on the `noop` path with no creds.

### W4.2 — Stage 1 decompose
- **Type**: leaf
- **Parent**: W4
- **Children**: none
- **Owns**: `src/oppp/stages/decompose.py`
- **REQ**: REQ-004, REQ-005 (CONST-2 — vocab-free production decomposer)
- **After**: none
- **Done-when**: `decomposer_registry` registers `llm` (vocab-free; performs no taxonomy
  import/lookup) and `gazetteer` (offline double); output is a `Decomposition` of
  `Component`s each carrying `field`, `nl_fragment`, `type` (`filter`|`question`),
  `reason`; `Decomposition.filters`/`.questions` views exist.

### W4.3 — Stage 2 translate
- **Type**: leaf
- **Parent**: W4
- **Children**: none
- **Owns**: `src/oppp/stages/translate.py`
- **REQ**: REQ-006, REQ-009, REQ-024 (closed-vocab grounding/expansion + open-field value + no fabrication; runs the W2.5 normalizer first)
- **After**: none
- **Done-when**: `translator_registry` registers `tool` (closed-vocab grounding +
  hierarchy expansion + LLM term-selector) and `deterministic` (same grounding, no LLM);
  closed-vocab fragments resolve via the taxonomy index and on no match emit **no**
  fabricated value (empty/flagged); open fragments emit `REGEX`/`RANGE`/`MATCH`; each
  grounded subquery carries a `Grounding` block; a single field is translatable in
  isolation via `translate_one`.

### W4.4 — Stage 3 aggregate
- **Type**: leaf
- **Parent**: W4
- **Children**: none
- **Owns**: `src/oppp/stages/aggregate.py`
- **REQ**: REQ-002, REQ-011, REQ-012, REQ-013, REQ-014, REQ-015
- **After**: none
- **Done-when**: `aggregator_registry` registers `llm` (decides only the boolean
  *structure* via `AggregationPlan`, rendered + validated deterministically) and
  `deterministic`; the boolean tree honours within-field groups and a default top-level
  `AND`; fields with an `entity_name` route into `entityFilters`; facets/displayColumns
  attach from `question` components within the service allow-list; the service
  `invariants` hook is applied; the final query is validated, `ValidationIssue`s recorded,
  and `PipelineResult.ok` is false on any error-level issue.

### W5 — Integration & surfaces
- **Type**: summary
- **Parent**: W1
- **Children**: W5.1, W5.2, W5.3, W5.4, W5.5
- **Owns**: none
- **After**: none
- **Review**: `run_pipeline(query, service, *, enhancer, decomposer, translator,
  aggregator, normalizer)` wires all four stages and returns a `PipelineResult` retaining
  every intermediate; the CLI exposes `run`, `enhance`, `decompose`, `field`, `aggregate`,
  `lookup`, `services`, `dag`, `eval`, each mapping backend flags to `run_pipeline` args;
  an offline `oppp run --no-execute` yields a validated query.
- **Done-when**: children resolved and the Review holds.

### W5.1 — Pipeline orchestration
- **Type**: leaf
- **Parent**: W5
- **Children**: none
- **Owns**: `src/oppp/pipeline.py`
- **REQ**: REQ-001, REQ-017
- **After**: none
- **Done-when**: `run_pipeline(...)` returns a `PipelineResult` keeping `enhanced`,
  `decomposition`, `subqueries`, `machine_query`, `issues`; runs end-to-end with the
  offline doubles making no network/LLM call. Exposes the `run_pipeline` interface the CLI/UI/eval consume.

### W5.2 — CLI
- **Type**: leaf
- **Parent**: W5
- **Children**: none
- **Owns**: `src/oppp/cli.py`
- **REQ**: REQ-016, REQ-018
- **After**: W5.1
- **Done-when**: each subcommand (`run`/`enhance`/`decompose`/`field`/`aggregate`/
  `lookup`/`services`/`dag`/`eval`) exists; each backend flag maps one-to-one to a
  `run_pipeline` argument; `enhance`/`decompose`/`field`/`aggregate` run standalone.

### W5.3 — Execution
- **Type**: leaf
- **Parent**: W5
- **Children**: none
- **Owns**: `src/oppp/execute.py`
- **REQ**: REQ-019 (supplies the executed `countTotal` the harness scores)
- **After**: none
- **Done-when**: `execute_count(machine_query, service, *, timeout)` POSTs the payload
  via stdlib `urllib` and returns an `ExecutionResult` with `count_total`/`status`/`error`.

### W5.4 — DAG export
- **Type**: leaf
- **Parent**: W5
- **Children**: none
- **Owns**: `src/oppp/dag.py`
- **REQ**: Structural: developer diagram-export tool (`oppp dag`; no functional requirement).
- **After**: none
- **Done-when**: `oppp dag` writes the component PNG using the `viz` extra without
  importing matplotlib in the core import path.

### W5.5 — Streamlit inspector
- **Type**: leaf
- **Parent**: W5
- **Children**: none
- **Owns**: `src/oppp/ui/app.py`, `src/oppp/ui/__init__.py`
- **REQ**: REQ-022, REQ-023
- **After**: W5.1
- **Done-when**: the app calls `run_pipeline` and renders Stage-1/2/3 outputs; the
  documented selector set (Service/Enhancer/Decomposer/Translator/Aggregator/Normalizer/
  Execute), the Stage-0 panel, and the gold-set question picker are present. Verifiable by
  inspecting the rendered control/panel set in `app.py`.

### W6 — Evaluation
- **Type**: summary
- **Parent**: W1
- **Children**: W6.1, W6.2, W6.3, W6.4, W6.5
- **Owns**: `src/oppp/eval/__init__.py`  *(convergent barrel — re-exports the eval surface)*
- **Contributors** (`src/oppp/eval/__init__.py`): W6.1, W6.2, W6.3, W6.4 — append-only re-exports collected from child reports.
- **After**: none
- **Review**: `evaluate(...)` reads the per-field gold set, executes the query, scores
  `countTotal` vs `s`, and reports valid/executed/exact/within-tolerance rates; the
  per-step comparators score each stage against its column in `docs/sme_stage_cases.csv`;
  the judge and per-step modules import lazily and are unit-stubbable offline.
- **Done-when**: children resolved; the barrel re-exports the eval surface and the Review holds.

### W6.1 — Count-based harness
- **Type**: leaf
- **Parent**: W6
- **Children**: none
- **Owns**: `src/oppp/eval/harness.py`
- **REQ**: REQ-019
- **After**: W6.2
- **Done-when**: `evaluate(...)` produces an `EvalReport` with `valid_rate`,
  `executed_rate`, `exact_count`, `within_<tol>`; `--no-execute` yields a validity-only
  report. Verifiable offline with `--no-execute`.

### W6.2 — Gold-case lookup + per-field compare
- **Type**: leaf
- **Parent**: W6
- **Children**: none
- **Owns**: `src/oppp/eval/compare.py`
- **REQ**: REQ-019 (CONTRACT-GOLD-PERFIELD)
- **After**: none
- **Done-when**: loads `inputs/sme_expected_cases.csv`, resolves a case by number, and
  compares resolved per-field label sets to the gold cells. Verifiable offline.

### W6.3 — Per-step comparators
- **Type**: leaf
- **Parent**: W6
- **Children**: none
- **Owns**: `src/oppp/eval/per_step.py`
- **REQ**: REQ-020 (CONTRACT-GOLD-PERSTEP)
- **After**: W6.1
- **Done-when**: each stage's output is scored against its column in
  `docs/sme_stage_cases.csv` with the fitting comparator (set match / routing-type-boolean
  / set-F1 / structural). Verifiable offline against the gold cells.

### W6.4 — LLM-as-judge
- **Type**: leaf
- **Parent**: W6
- **Children**: none
- **Owns**: `src/oppp/eval/judge.py`
- **REQ**: REQ-021
- **After**: none
- **Done-when**: a constrained judge returns a typed verdict (`match|partial|miss` +
  one-line reason) for Stage-1 fragments, Stage-2 open-field patterns, and Stage-3
  structure tie-breaks; the LLM client is lazy-imported and the path is stubbable so tests
  stay hermetic.

### W6.5 — Per-step gold-set builder
- **Type**: leaf
- **Parent**: W6
- **Children**: none
- **Owns**: `utils/build_sme_stage_cases.py`
- **REQ**: Structural: tooling that reshapes the per-field gold set into the per-step gold set (supports REQ-020).
- **After**: none
- **Done-when**: the builder writes the per-step gold set to the documented canonical
  location `docs/sme_stage_cases.csv` (not `inputs/`), and the per-step harness reads the
  same path.

### W7 — Offline test suite
- **Type**: summary
- **Parent**: W1
- **Children**: W7.1, W7.2, W7.3, W7.4, W7.5, W7.6
- **Owns**: none
- **After**: none
- **Review**: `pytest -q` passes with no network access and no model credentials present;
  every test module collects; the suite exercises only the offline doubles.
- **Done-when**: children resolved and the Review holds.

### W7.1 — Taxonomy tests
- **Type**: leaf
- **Parent**: W7
- **Children**: none
- **Owns**: `tests/test_taxonomy.py`
- **REQ**: REQ-006, REQ-007
- **After**: none
- **Done-when**: grounding/expansion behaviour is asserted offline; the module passes under `pytest -q`.

### W7.2 — Stage tests
- **Type**: leaf
- **Parent**: W7
- **Children**: none
- **Owns**: `tests/test_stages.py`
- **REQ**: REQ-004, REQ-006, REQ-009, REQ-011
- **After**: none
- **Done-when**: each stage's offline backend is asserted (routing/grounding/open-field/
  boolean) and the module passes under `pytest -q`.

### W7.3 — Pipeline tests
- **Type**: leaf
- **Parent**: W7
- **Children**: none
- **Owns**: `tests/test_pipeline.py`
- **REQ**: REQ-001, REQ-017
- **After**: none
- **Done-when**: an end-to-end run with the doubles is asserted to produce a validated
  query with no network/LLM call; passes under `pytest -q`.

### W7.4 — Eval tests
- **Type**: leaf
- **Parent**: W7
- **Children**: none
- **Owns**: `tests/test_eval.py`
- **REQ**: REQ-019
- **After**: none
- **Done-when**: count parsing + the harness are asserted offline (`--no-execute`); passes under `pytest -q`.

### W7.5 — Per-step eval tests
- **Type**: leaf
- **Parent**: W7
- **Children**: none
- **Owns**: `tests/test_per_step_eval.py`
- **REQ**: REQ-020, REQ-021
- **After**: none
- **Done-when**: the per-step comparators are unit-tested offline and the judge is
  exercised with a stub/fake so the test stays hermetic; passes under `pytest -q`.

### W7.6 — Service tests
- **Type**: leaf
- **Parent**: W7
- **Children**: none
- **Owns**: `tests/test_services.py`
- **REQ**: Structural: offline tests for the PK/RTB service configs (forward scope; no current MUST requirement).
- **After**: none
- **Done-when**: PK and RTB produce valid queries for a sample question offline; passes under `pytest -q`.

## Cross-tree dependencies
<!-- The only place a dependency between two DIFFERENT subtrees may appear.
     <consumer> after <producer> — interface: <what the producer exposes>.
     Intra-subtree order is carried by the `After` fields above; these are the
     inter-layer interface edges a parallel scheduler must respect. Sequential
     bottom-up (post-order) execution satisfies all of them trivially. -->

- W3.1 after W2.1 — interface: `oppp.models` types referenced by `ServiceConfig`/`FieldSpec`.
- W4.1 after W2.1, W3.1 — interface: `EnhancedQuery` model + `ServiceConfig` (entity-type map).
- W4.2 after W2.1, W2.6, W3.1 — interface: `Decomposition`/`Component` models + lazy LLM helper + `ServiceConfig` (field catalogue).
- W4.3 after W2.1, W2.4, W2.5, W2.6, W3.1 — interface: `MachineSubquery`/`Grounding` models + taxonomy index + normalizer registry + LLM term-selector + `ServiceConfig` (buckets/taxonomy bindings).
- W4.4 after W2.1, W2.6, W3.1 — interface: `MachineQuery`/`AggregationPlan` models + lazy LLM helper + `ServiceConfig` (facets/entity routing/invariants).
- W5.1 after W2.1, W3, W4 — interface: `service_registry` + all four stage callables/registries.
- W5.3 after W2.1 — interface: `MachineQuery.to_payload()`.
- W6.1 after W2.1, W5.1, W5.3, W3.2 — interface: `run_pipeline` + `execute_count` + Safety `ServiceConfig` + per-field gold set.
- W6.3 after W5.1 — interface: per-stage `PipelineResult` artefacts to score.
- W6.4 after W2.6 — interface: lazy LLM structured-output helper.
- W7.1 after W2.4 — interface: taxonomy index.
- W7.2 after W4 — interface: stage backends.
- W7.3 after W5.1 — interface: `run_pipeline`.
- W7.4 after W6.1 — interface: `evaluate`/`EvalReport`.
- W7.5 after W6.3, W6.4 — interface: per-step comparators + judge.
- W7.6 after W3 — interface: PK/RTB `ServiceConfig`s.
