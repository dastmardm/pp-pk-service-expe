# Project Constitution

## Core Principles

### CONST-1 — Product intent starts in `docs/`
**Rule.** Changes to product behavior, evaluation scope, field policy, or pipeline semantics MUST originate in `docs/` and flow through `/mdtechnical` before implementation. Contributors and AI assistants MUST NOT introduce new behavior directly in source, tests, or generated specs.
**Why.** The repository is governed by a docs-first pipeline; specs and code are projections of ratified human-facing intent.
**Breaks if violated.** Implementation can drift away from the product contract and downstream evaluation will no longer trace to the source of truth.

### CONST-2 — The PK staged pipeline order is fixed
**Rule.** The production PK path, CLI execution path, UI execution path, and evaluation harness MUST run the staged sequence: expansion -> decomposition -> field-scoped TERMite enrichment -> early small-closed translation -> aggregate/count -> strict `1000` count gate -> row filtering or staged non-early translation -> final row count. The system MUST NOT move TERMite before decomposition, translate all filters before the early count, or replace the staged count gate with a single aggregate call.
**Why.** The documented product depends on using cheap, field-safe early filters before deciding whether local row filtering is possible.
**Breaks if violated.** Counts can be narrowed by the wrong fields, row filtering can be skipped, and evaluation can report a count from a path the product does not define.

### CONST-3 — Field metadata is the authority for buckets and early eligibility
**Rule.** PK field bucket definitions MUST live in service metadata, not scattered stage code. `EARLY_CONTRIBUTOR_THRESHOLD` MUST be exactly `1000`. The early small-closed fields are `species`, `routes`, `documentSource`, and `documentYear`; `drugs` is closed but not early; `studyGroups` is the documented plural field name.
**Why.** Bucket policy decides execution order and must be auditable from one service configuration boundary.
**Breaks if violated.** A worker can accidentally treat high-cardinality fields as early, miss documented fields, or emit unsupported field names.

### CONST-4 — Decomposition and TERMite stay field-scoped
**Rule.** Decomposition MUST emit typed components with `field`, `nl_fragment`, `type`, `reason`, `source`, and optional boolean grouping metadata before TERMite runs. TERMite enrichment MUST use each component's selected `field` as context and the component's `nl_fragment` as text; `reason` is audit metadata and MUST NOT be enriched as the query fragment.
**Why.** Routing and entity recognition are separate stages; field-scoped enrichment prevents global entity matches from rewriting the user's intent.
**Breaks if violated.** TERMite annotations can attach to the wrong field or every same-type fragment can inherit the first recognized annotation.

### CONST-5 — Translation and aggregation are staged, valid, and replayable
**Rule.** Translation MUST support deterministic staged selection: early small-closed components first, then non-early components only when the count remains `>= 1000`. Aggregation MUST be callable after each staged translation set, preserve boolean grouping, apply PK invariants, validate allowed fields/facets, enforce the query budget, and surface issues without hiding the staged path.
**Why.** The pipeline must be able to explain every API count attempt and every filter that remains pending.
**Breaks if violated.** The final count becomes irreproducible and invalid filters can silently affect API payloads.

### CONST-6 — The `1000` row gate has strict semantics
**Rule.** A staged API count `< 1000` MUST trigger row retrieval and local filtering of all remaining filters. A count `>= 1000` MUST trigger another deterministic non-early translation stage, unless every filter has already been translated, in which case the final API count is the final row count.
**Why.** The product contract distinguishes the row-filter path from the full API-count path by an exact threshold.
**Breaks if violated.** Boundary cases at `1000` will take the wrong path and expected-count evaluation can no longer be trusted.

### CONST-7 — `final_row_count` is the shared result contract
**Rule.** CLI, UI, tests, and evaluation MUST report `PipelineResult.final_row_count` as the product result. `countTotal` from a staged attempt may be used as the final count only when all filters have been translated into the API query. Row-filter runs MUST also record execution mode, fetched rows, filtered rows, filter issues, and staged count attempts.
**Why.** The same question can finish by local row filtering or by a final API count; public surfaces need one canonical count field.
**Breaks if violated.** Evaluation may compare an intermediate `countTotal` instead of the count produced by the completed pipeline.

### CONST-8 — Evaluation is exact-count only
**Rule.** Scored evaluation MUST read `docs/PPPK.xlsx`, sheet `PK_Query`, columns `Quety number`, `Query`, and `Expected Count`, then compare `final_row_count == Expected Count`. No other sheet, tolerance band, per-step qualitative score, or label-level metric may be part of the scored PK evaluation.
**Why.** The product's success measure is exact final row count for the documented PK query sheet.
**Breaks if violated.** The project can appear successful through auxiliary metrics while failing the only ratified acceptance signal.

### CONST-9 — Typed contracts guard every boundary
**Rule.** Stage inputs and outputs, service fields, machine queries, execution results, row-filter results, and evaluation rows MUST use typed contracts. `MachineQuery.to_payload()` MUST normalize the boolean tree into the PK advanced search payload before execution.
**Why.** Typed boundaries make the staged pipeline inspectable and prevent fragile free-text parsing from leaking into execution.
**Breaks if violated.** Malformed payloads, missing result fields, and ambiguous stage artifacts can reach CLI, UI, or evaluation.

### CONST-10 — External systems are lazy and testable
**Rule.** PharmaPendium, LLM, Portkey/OpenAI, and TERMite credentials MUST be read only when the stage that needs them runs. Offline tests MUST use fakes, fixtures, or monkeypatching and MUST NOT require network, model, TERMite, or PharmaPendium access.
**Why.** Local development and CI must validate the contracts without secrets or live services.
**Breaks if violated.** Imports and tests become environment-dependent, and secrets are more likely to leak.

### CONST-11 — Observability is part of the architecture
**Rule.** The pipeline MUST retain expanded text, decomposition reasons, per-component TERMite annotations, translated subqueries, staged API attempts, execution mode, row-filter counts, and validation/execution issues in the runtime result.
**Why.** Count mismatches need to be diagnosable at the stage where they were introduced.
**Breaks if violated.** Maintainers cannot tell whether an error came from expansion, routing, enrichment, translation, aggregation, execution, or local filtering.

### CONST-12 — Quality gates pass before merge
**Rule.** No implementation change may merge unless the quality gates below pass, except for a documented docs/spec-only change that does not alter runnable code.
**Why.** The package must remain importable, lint-clean, formatted, and covered by hermetic tests while the staged pipeline changes.
**Breaks if violated.** Regressions can accumulate outside the spec pipeline and block later evaluation.

## Technology Stack

| Layer | Technology | Version/Notes | Prohibited alternatives |
| --- | --- | --- | --- |
| Language | Python | `>=3.11` | Rewriting the package in another language |
| Package/build | Existing `pyproject.toml` package model | Preserve the current `src/oppp` package layout | Ad-hoc build scripts or a second package layout |
| Core architecture | Existing `oppp` registries and module boundaries | `models.py`, `services/`, `stages/`, `pipeline.py`, `execute.py`, `eval/`, `cli.py`, `ui/` | Parallel PK-only pipeline stack |
| Typed contracts | Pydantic | Serializable stage, query, execution, and evaluation models | Untyped dictionaries at stage boundaries |
| CLI | Typer | `oppp run`, stage/debug commands, `oppp eval` | Hand-rolled CLI parser |
| UI | Streamlit | Optional UI extra; debug surface mirrors production stages | UI-only execution logic |
| Field matching | RapidFuzz plus service vocabularies | Used for closed-set and runtime-set matching | Prompt-only value selection |
| Environment loading | python-dotenv and environment variables | Secrets stay outside committed files | Hardcoded credentials |
| LLM support | LangChain/OpenAI/Portkey packages as configured in `pyproject.toml` | Optional/lazy model stages | Mandatory model import at package import time |
| Graph/agent support | LangGraph/DSPy packages as configured in `pyproject.toml` | Optional extras only | Required runtime dependency for the PK pipeline |
| Entity enrichment | SciBite TERMite service/toolkit | Field-scoped component enrichment | Global pre-decomposition TERMite rewrite |
| PK search integration | PharmaPendium `/v1/pk/search/advanced` | Count and row retrieval through `execute.py` | New service process or database |
| Visualization | matplotlib | Optional DAG/visualization support | Mandatory visualization dependency |
| Reports/workbooks | openpyxl | Required for XLSX evaluation/report support | Treating CSV or other sheets as the scored source |
| Lint/format | Ruff | `ruff check`, `ruff format --check` | Multiple competing linters/formatters |
| Tests | pytest | Offline suite with fakes by default | Networked default tests |

## Development Workflow

### Quality Gates

1. `python3 -m compileall src/oppp`
2. `ruff check src tests`
3. `ruff format --check src tests`
4. `pytest -q`

### Adding a New Component

1. Update `docs/` first when the change affects behavior, evaluation scope, fields, or quality requirements.
2. Define or extend the typed contract in the existing boundary that owns the data.
3. Wire the component into the fixed PK staged path without adding a user-selectable alternate production path.
4. Keep optional model, TERMite, UI, visualization, and report dependencies lazy.
5. Add hermetic tests with fake services or fixtures for the changed boundary.
6. Confirm CLI, UI, and evaluation still report `final_row_count` and execution mode consistently.

### Schema / Data Contract Changes

1. Update the owning Pydantic model, service dataclass, or payload serializer.
2. Update staged pipeline orchestration and all public surfaces that expose the contract.
3. Update tests that assert the contract shape and staged behavior.
4. Update evaluation criteria through the docs-first spec pipeline when the contract changes product behavior.
5. Run the Quality Gates.

## Governance

- Constitution changes are versioned as MAJOR for reversed or removed principles, MINOR for added principles, and PATCH for clarifications.
- Every contributor and AI assistant must comply with the current constitution before changing implementation files.
- A downstream evaluation gap that reveals missing intent is resolved by editing `docs/` and rerunning `/mdtechnical`, not by patching specs or code directly.
- `/mdevaluation` must be able to audit these principles through `specs/evaluation.md`; an unauditable principle is incomplete.
