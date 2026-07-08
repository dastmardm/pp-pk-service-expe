# Tasks

## Overview
The WBS decomposes `oppp` v0.1 alignment into five subtrees under root W1. Leaves are file-disjoint and independently implementable within their dependency wave. Summary nodes aggregate convergent files, run integration assertions, and report upward.

```
W1 (root)         — oppp v0.1 PK pipeline
  W1.1 (summary)  — Contracts and config
    W1.1.1 (leaf) — Pydantic models
    W1.1.2 (leaf) — Config and .env.example
    W1.1.3 (leaf) — Normalizer interface and strategies
    W1.1.4 (leaf) — LLM factory
  W1.2 (summary)  — Service layer
    W1.2.1 (leaf) — Service registry
    W1.2.2 (leaf) — Service base schema
    W1.2.3 (leaf) — PK service config
    W1.2.4 (leaf) — Safety and RTB configs (inactive)
    W1.2.5 (leaf) — Taxonomy index
  W1.3 (summary)  — Stages and execution
    W1.3.1 (leaf) — Stage -1: expand
    W1.3.2 (leaf) — Stage 0: enhance
    W1.3.3 (leaf) — Stage 1: decompose
    W1.3.4 (leaf) — Stage 2: translate
    W1.3.5 (leaf) — Stage 3: aggregate
    W1.3.6 (leaf) — Execution (count + rows)
    W1.3.7 (leaf) — Stages package init
  W1.4 (summary)  — Surfaces
    W1.4.1 (leaf) — Pipeline orchestrator
    W1.4.2 (leaf) — CLI
    W1.4.3 (leaf) — Streamlit UI
    W1.4.4 (leaf) — DAG export
  W1.5 (summary)  — Evaluation and tests
    W1.5.1 (leaf) — Eval package init
    W1.5.2 (leaf) — Evaluation harness
    W1.5.3 (leaf) — Per-step comparators
    W1.5.4 (leaf) — Compare and judge
    W1.5.5 (leaf) — Test conftest (fakes and fixtures)
    W1.5.6 (leaf) — test_pipeline.py
    W1.5.7 (leaf) — test_stages.py
    W1.5.8 (leaf) — test_runtime_post_filters.py
    W1.5.9 (leaf) — test_eval.py
    W1.5.10 (leaf) — test_per_step_eval.py
    W1.5.11 (leaf) — test_normalize.py
    W1.5.12 (leaf) — test_services.py
    W1.5.13 (leaf) — test_taxonomy.py
    W1.5.14 (leaf) — test_cli.py
    W1.5.15 (leaf) — test_dag.py
```

## Nodes

### W1 — oppp v0.1 PK pipeline
- **Type**: root
- **Parent**: none
- **Children**: W1.1, W1.2, W1.3, W1.4, W1.5
- **Owns**: `pyproject.toml`
- **Contributors**: W1.1 (llm extra, dev extra), W1.4 (ui/viz extras), W1.5 (report extra)
- **After**: none
- **Review**: `python3 -m compileall src/oppp` exits 0; `ruff check src tests` exits 0; `ruff format --check src tests` exits 0; `pytest -q` exits 0; `pyproject.toml` declares all required extras and console script.
- **Done-when**: all four quality gates pass; `pyproject.toml` extras include `llm`, `ui`, `viz`, `report`, `dev`; `oppp` console script entry point resolves.

---

### W1.1 — Contracts and config
- **Type**: summary
- **Parent**: W1
- **Children**: W1.1.1, W1.1.2, W1.1.3, W1.1.4
- **Owns**: none
- **After**: none
- **Review**: `from oppp.models import PipelineResult, RowExecutionResult, PostFilterResult` succeeds; `from oppp.config import load_dotenv_if_present` succeeds without importing LangChain or TERMite; `from oppp.normalize import normalize` succeeds; importing `oppp.llm` does not trigger LangChain import at module load time.
- **Done-when**: all four child leaves complete; the review assertions above pass.

### W1.1.1 — Pydantic models
- **Type**: leaf
- **Parent**: W1.1
- **Children**: none
- **Owns**: `src/oppp/models.py`
- **REQ**: REQ-001, REQ-006, REQ-008, REQ-013, REQ-014, REQ-015, REQ-016, REQ-017
- **After**: none
- **Done-when**: `models.py` exports all required types; each has the fields described in the CONTRACT-* entries in `specs/technical.md`; `python3 -m compileall src/oppp/models.py` exits 0; `ruff check src/oppp/models.py` exits 0.

### W1.1.2 — Config and .env.example
- **Type**: leaf
- **Parent**: W1.1
- **Children**: none
- **Owns**: `src/oppp/config.py`, `.env.example`
- **REQ**: REQ-027
- **After**: none
- **Done-when**: `config.py` loads `.env` lazily; `get_llm_settings()` raises `ConfigError` when `PORTKEY_ENDPOINT` absent; `get_termite_settings()` raises `ConfigError` when `TERMITE_HOME` absent; `.env.example` lists all 10 env vars with empty values and required/optional annotations; `python3 -m compileall src/oppp/config.py` exits 0.

### W1.1.3 — Normalizer interface and strategies
- **Type**: leaf
- **Parent**: W1.1
- **Children**: none
- **Owns**: `src/oppp/normalize/__init__.py`, `src/oppp/normalize/base.py`, `src/oppp/normalize/strategies.py`
- **REQ**: REQ-010
- **After**: W1.1.1
- **Done-when**: `base.py` defines `NormalizationResult`; `strategies.py` implements `ClosedSetNormalizer`, `ConservativeNormalizer`, `DrugNormalizer`; `normalize(fragment, field, bucket, context)` dispatches correctly; no selectable normalizer option exported; compile and ruff pass.

### W1.1.4 — LLM factory
- **Type**: leaf
- **Parent**: W1.1
- **Children**: none
- **Owns**: `src/oppp/llm.py`
- **REQ**: REQ-002, REQ-003, NFR-003
- **After**: W1.1.2
- **Done-when**: `get_chat_model()` returns a LangChain chat model with temperature 0, `top_p=0`, seed from `LLM_SEED` (default 7); LangChain NOT imported at `import oppp.llm` module load time; compile and ruff pass.

---

### W1.2 — Service layer
- **Type**: summary
- **Parent**: W1
- **Children**: W1.2.1, W1.2.2, W1.2.3, W1.2.4, W1.2.5
- **Owns**: none
- **After**: W1.1
- **Review**: `from oppp.services import get_service; svc = get_service("pk")` returns a `ServiceConfig`; `svc.field_specs["drugs"].bucket == "closed"` is true; `svc.field_specs["parameter"].bucket == "open"` is true; `EARLY_CONTRIBUTOR_THRESHOLD` is 500.
- **Done-when**: all five child leaves complete; the review assertions above pass.

### W1.2.1 — Service registry
- **Type**: leaf
- **Parent**: W1.2
- **Children**: none
- **Owns**: `src/oppp/services/__init__.py`, `src/oppp/registry.py`
- **Structural**: service registry; no stage selection exposure
- **After**: W1.2.2
- **Done-when**: `get_service(name)` raises `KeyError` for unknown names; no stage method selection exported; compile and ruff pass.

### W1.2.2 — Service base schema
- **Type**: leaf
- **Parent**: W1.2
- **Children**: none
- **Owns**: `src/oppp/services/base.py`
- **REQ**: REQ-019
- **After**: W1.1.1
- **Done-when**: `FieldSpec` has `bucket`, `taxonomy_path`, `api_field`, `facet`, `display`; `ServiceConfig` has `name`, `search_url`, `field_specs`, `early_contributor_threshold`, `invariants`, `facet_allowlist`; compile and ruff pass.

### W1.2.3 — PK service config
- **Type**: leaf
- **Parent**: W1.2
- **Children**: none
- **Owns**: `src/oppp/services/pk.py`
- **REQ**: REQ-011, REQ-012, REQ-019
- **After**: W1.2.2
- **Done-when**: `pk.py` defines all 16 PK fields with correct buckets; three PK invariants present; `EARLY_CONTRIBUTOR_THRESHOLD = 500`; search URL is `/v1/pk/search/advanced`; no hardcoded field names outside this file; compile and ruff pass.

### W1.2.4 — Safety and RTB configs (inactive)
- **Type**: leaf
- **Parent**: W1.2
- **Children**: none
- **Owns**: `src/oppp/services/safety.py`, `src/oppp/services/rtb.py`
- **Structural**: inactive service configs preserved for future; not imported by pipeline/cli/ui
- **After**: W1.2.2
- **Done-when**: both files compile without syntax errors; neither imported by `pipeline.py`, `cli.py`, or `ui/app.py`; compile and ruff pass.

### W1.2.5 — Taxonomy index
- **Type**: leaf
- **Parent**: W1.2
- **Children**: none
- **Owns**: `src/oppp/taxonomy/__init__.py`, `src/oppp/taxonomy/index.py`
- **REQ**: REQ-007, REQ-011
- **After**: W1.2.2
- **Done-when**: `TaxonomyIndex` loads CSV by path; `lookup(query, match, expand, limit)` returns `list[GroundingHit]`; hierarchy expansion traverses `parent_id`/`parent_name`; compile and ruff pass.

---

### W1.3 — Stages and execution
- **Type**: summary
- **Parent**: W1
- **Children**: W1.3.1, W1.3.2, W1.3.3, W1.3.4, W1.3.5, W1.3.6, W1.3.7
- **Owns**: none
- **After**: W1.2
- **Review**: `from oppp.stages import expand, enhance, decompose, translate, aggregate` succeeds without LangChain or TERMite imports at module load; `translate.translate_input_filter` with a `drugs` component returns `MachineSubquery` or `None`.
- **Done-when**: all seven child leaves complete; the review assertions above pass.

### W1.3.1 — Stage -1: expand
- **Type**: leaf
- **Parent**: W1.3
- **Children**: none
- **Owns**: `src/oppp/stages/expand.py`
- **REQ**: REQ-002
- **After**: W1.1.4
- **Done-when**: `expand_query(query, service) -> ExpandedQuery` uses LLM structured output; preserves `original`; raises `ConfigError` (not no-op) when LLM unavailable; LangChain not imported at module load; ruff pass.

### W1.3.2 — Stage 0: enhance
- **Type**: leaf
- **Parent**: W1.3
- **Children**: none
- **Owns**: `src/oppp/stages/enhance.py`
- **REQ**: REQ-003
- **After**: W1.1.2
- **Done-when**: `enhance(query, service) -> EnhancedQuery` calls TERMite lazily; raises `ConfigError` when TERMite settings missing; returns `EnhancedQuery` with `annotations` list; TERMite not imported at module load; ruff pass.

### W1.3.3 — Stage 1: decompose
- **Type**: leaf
- **Parent**: W1.3
- **Children**: none
- **Owns**: `src/oppp/stages/decompose.py`
- **REQ**: REQ-004, REQ-005, REQ-006
- **After**: W1.1.1, W1.2.3
- **Done-when**: `decompose(query, service, annotations) -> Decomposition` uses LLM structured output; no taxonomy CSV import; `reconcile_with_annotations` promotes `PARAMETER`-typed TERMite hits from `question` to `filter`; ruff pass.

### W1.3.4 — Stage 2: translate
- **Type**: leaf
- **Parent**: W1.3
- **Children**: none
- **Owns**: `src/oppp/stages/translate.py`
- **REQ**: REQ-007, REQ-008, REQ-009, REQ-010, REQ-015, REQ-016
- **After**: W1.1.3, W1.2.5
- **Done-when**: `translate_input_filter` implements 6-step `CONTRACT-CLOSED-SET-TRANSLATION`; emits only closed-set members; marks invalid when empty; `translate_runtime_filter` reuses the same contract over runtime list; `_translate_open` emits `MATCH`/`REGEX` for v0.1 count mode; ruff pass.

### W1.3.5 — Stage 3: aggregate
- **Type**: leaf
- **Parent**: W1.3
- **Children**: none
- **Owns**: `src/oppp/stages/aggregate.py`
- **REQ**: REQ-012, REQ-017, REQ-018
- **After**: W1.1.1, W1.2.3
- **Done-when**: `aggregate_query` applies boolean grouping, PK invariants, facets, displayColumns, structural validation; `drop_empty_open_filters` probes and drops zero-count open filters; `apply_post_filters` applies valid runtime selections and records invalid runtime translations in `issues` without narrowing datapoints; ruff pass.

### W1.3.6 — Execution (count + rows)
- **Type**: leaf
- **Parent**: W1.3
- **Children**: none
- **Owns**: `src/oppp/execute.py`
- **REQ**: REQ-013, REQ-014, REQ-018, NFR-004
- **After**: W1.1.1, W1.2.2
- **Done-when**: `execute_count` POSTs and reads `data.countTotal`; `execute_rows` paginates until limit/all/error; row unavailability returns `ok=false` with error (no exception); `urllib.request` is only HTTP import; ruff pass.

### W1.3.7 — Stages package init
- **Type**: leaf
- **Parent**: W1.3
- **Children**: none
- **Owns**: `src/oppp/stages/__init__.py`
- **Structural**: fixed stage public API; no stage method registry
- **After**: W1.3.1, W1.3.2, W1.3.3, W1.3.4, W1.3.5, W1.3.6
- **Done-when**: `from oppp.stages import expand, enhance, decompose, translate, aggregate` resolves; no `noop`, `gazetteer`, or method-selector names exported; ruff pass.

---

### W1.4 — Surfaces
- **Type**: summary
- **Parent**: W1
- **Children**: W1.4.1, W1.4.2, W1.4.3, W1.4.4
- **Owns**: none
- **After**: W1.3
- **Review**: `oppp run --help` contains no `--enhancer`, `--decomposer`, `--translator`, `--aggregator`, `--normalizer`; `oppp dag` output contains all eight stage labels (Stage -1, Stage 0, Stage 1, Stage 2A, Stage 3A, Stage 2B, Stage 3B, Stage 2C).
- **Done-when**: all four child leaves complete; the review assertions above pass.

### W1.4.1 — Pipeline orchestrator
- **Type**: leaf
- **Parent**: W1.4
- **Children**: none
- **Owns**: `src/oppp/pipeline.py`, `src/oppp/__init__.py`
- **REQ**: REQ-001, REQ-018
- **After**: W1.3.7
- **Done-when**: `run_pipeline` calls stages in fixed order; `fetch_rows=True` calls `execute_rows` and 2B/2C stubs; no stage method parameter; `build_langgraph()` exists and returns a callable graph wrapping the same fixed stage functions (behavioral correctness of the LangGraph topology is out of evaluation scope per `specs/evaluation.md`); ruff pass.

### W1.4.2 — CLI
- **Type**: leaf
- **Parent**: W1.4
- **Children**: none
- **Owns**: `src/oppp/cli.py`
- **REQ**: REQ-020, NFR-005
- **After**: W1.4.1
- **Done-when**: all listed commands exist; none accept `--enhancer`, `--decomposer`, `--translator`, `--aggregator`, `--normalizer`; help text mentions no pluggable backend; ruff pass.

### W1.4.3 — Streamlit UI
- **Type**: leaf
- **Parent**: W1.4
- **Children**: none
- **Owns**: `src/oppp/ui/__init__.py`, `src/oppp/ui/app.py`
- **REQ**: REQ-021
- **After**: W1.4.1
- **Done-when**: `app.py` loads questions from `docs/PPPK.xlsx` (`PK_Query` sheet); shows Stage 0-3 panels and execution count; no stage backend `st.selectbox`; Streamlit not imported at module load; ruff pass.

### W1.4.4 — DAG export
- **Type**: leaf
- **Parent**: W1.4
- **Children**: none
- **Owns**: `src/oppp/dag.py`
- **REQ**: REQ-022
- **After**: W1.4.1
- **Done-when**: `dag.py` exports fixed stage list containing all eight stages (Stage -1, Stage 0, Stage 1, Stage 2A, Stage 3A, Stage 2B, Stage 3B, Stage 2C); no pluggable-backend registry; ruff pass.

---

### W1.5 — Evaluation and tests
- **Type**: summary
- **Parent**: W1
- **Children**: W1.5.1, W1.5.2, W1.5.3, W1.5.4, W1.5.5, W1.5.6, W1.5.7, W1.5.8, W1.5.9, W1.5.10, W1.5.11, W1.5.12, W1.5.13, W1.5.14, W1.5.15
- **Owns**: none
- **After**: W1.4
- **Review**: `pytest -q` passes with no `.env` and no network; `ruff check tests` exits 0.
- **Done-when**: all fifteen child leaves complete; `pytest -q` passes; `ruff check tests` passes.

### W1.5.1 — Eval package init
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `src/oppp/eval/__init__.py`
- **Structural**: exposes harness, per_step, compare, judge exports
- **After**: none
- **Done-when**: `from oppp.eval import harness, per_step, judge` succeeds; ruff pass.

### W1.5.2 — Evaluation harness
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `src/oppp/eval/harness.py`
- **REQ**: REQ-023
- **After**: W1.5.1, W1.4.1
- **Done-when**: loads `docs/PPPK.xlsx` via openpyxl from `PK_Query` sheet; handles `Quety number` column; iterates 47 rows; computes `valid_rate`, `executed_rate`, `exact_count`, `within_<tol>`; writes CSV and XLSX reports; ruff pass.

### W1.5.3 — Per-step comparators
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `src/oppp/eval/per_step.py`
- **REQ**: REQ-024
- **After**: W1.5.1, W1.1.1
- **Done-when**: exports Stage 0 entity set P/R, Stage 1 field/type exact score, Stage 1 fragment judge call, Stage 2 field name score, Stage 3 structural compare + judge tie-break; ruff pass.

### W1.5.4 — Compare and judge
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `src/oppp/eval/compare.py`, `src/oppp/eval/judge.py`
- **REQ**: REQ-028
- **After**: W1.5.1, W1.1.1, W1.1.4
- **Done-when**: `judge.py` exports `LLMJudge` and `JudgeVerdict`; `LLMJudge` accepts injectable client; `compare.py` exports gold-vs-agent diff helpers; ruff pass.

### W1.5.5 — Test conftest (fakes and fixtures)
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/conftest.py`
- **REQ**: REQ-026, NFR-002
- **After**: W1.1.1, W1.1.4
- **Done-when**: provides `fake_llm_client`, `fake_termite_client`, `mock_api_count_response`, `mock_api_row_response` fixtures; no fixture imports live LangChain or TERMite unconditionally; ruff pass.

### W1.5.6 — test_pipeline.py
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/test_pipeline.py`
- **REQ**: REQ-001, REQ-005
- **After**: W1.5.5
- **Done-when**: covers count-mode and row-mode pipeline; no stage method parameter; no `.env` needed; `pytest -q tests/test_pipeline.py` passes.

### W1.5.7 — test_stages.py
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/test_stages.py`
- **REQ**: REQ-002, REQ-003, REQ-004, REQ-005, REQ-007, REQ-011, REQ-012, REQ-025
- **After**: W1.5.5
- **Done-when**: covers Rodent expansion, suntinib fuzzy drug, AUC OR Cmax group, PK invariants, annotation reconciliation, ConfigError on missing TERMite, ConfigError on missing LLM; `pytest -q tests/test_stages.py` passes.

### W1.5.8 — test_runtime_post_filters.py
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/test_runtime_post_filters.py`
- **REQ**: REQ-015, REQ-016, REQ-017
- **After**: W1.5.5
- **Done-when**: covers runtime closed-set derivation, valid post-filter application, invalid post-filter non-narrowing; `pytest -q tests/test_runtime_post_filters.py` passes.

### W1.5.9 — test_eval.py
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/test_eval.py`
- **REQ**: REQ-023
- **After**: W1.5.5, W1.5.2
- **Done-when**: covers XLSX load (47 rows), `Quety number` handling, metrics computation, report export; `pytest -q tests/test_eval.py` passes.

### W1.5.10 — test_per_step_eval.py
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/test_per_step_eval.py`
- **REQ**: REQ-024
- **After**: W1.5.5, W1.5.3
- **Done-when**: covers all five per-step comparators with pass and fail cases; judge comparator injects fake; `pytest -q tests/test_per_step_eval.py` passes.

### W1.5.11 — test_normalize.py
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/test_normalize.py`
- **REQ**: REQ-010
- **After**: W1.5.5
- **Done-when**: covers closed-set typo correction, class label preservation, conservative open-set passthrough, drug brand-name synonym; `pytest -q tests/test_normalize.py` passes.

### W1.5.12 — test_services.py
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/test_services.py`
- **REQ**: REQ-019
- **After**: none
- **Done-when**: covers PK service 16 fields, bucket correctness, EARLY_CONTRIBUTOR_THRESHOLD=500, three invariants, search URL; `pytest -q tests/test_services.py` passes.

### W1.5.13 — test_taxonomy.py
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/test_taxonomy.py`
- **REQ**: REQ-007, REQ-011
- **After**: none
- **Done-when**: covers exact lookup, fuzzy lookup, children expansion, leaf not widened; `pytest -q tests/test_taxonomy.py` passes.

### W1.5.14 — test_cli.py
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/test_cli.py`
- **REQ**: REQ-020
- **After**: W1.5.5
- **Done-when**: `oppp run --help` output contains no method selector flags; `oppp eval --no-execute` with mocked harness exits 0; `pytest -q tests/test_cli.py` passes.

### W1.5.15 — test_dag.py
- **Type**: leaf
- **Parent**: W1.5
- **Children**: none
- **Owns**: `tests/test_dag.py`
- **REQ**: REQ-022
- **After**: none
- **Done-when**: DAG fixed stage list contains all eight stage labels (Stage -1, Stage 0, Stage 1, Stage 2A, Stage 3A, Stage 2B, Stage 3B, Stage 2C); no backend registry; `pytest -q tests/test_dag.py` passes.

## Cross-tree dependencies
- W1.2 after W1.1 — interface: `FieldSpec` and `ServiceConfig` dataclasses (W1.1.1/W1.2.2) consumed by all service leaves.
- W1.3 after W1.2 — interface: PK `ServiceConfig` instance consumed by all stage leaves.
- W1.4 after W1.3 — interface: stage public API and `execute_*` functions consumed by pipeline and CLI.
- W1.5 after W1.4 — interface: `run_pipeline`, `PipelineResult`, eval harness consumed by test leaves.
