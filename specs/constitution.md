# Project Constitution

## Core Principles

### CONST-1 — The stage path is fixed
**Rule.** The public pipeline, CLI, UI, and evaluation harness MUST run the documented fixed sequence: LLM expansion → LLM decomposition → TERMite enhancement → input closed-set translation (Stage 2A) → Stage 3A aggregation and execution → runtime narrowing (Stage 2B) → final aggregation and execution (Stage 3B) → open-set post-filtering (Stage 2C). They MUST NOT expose selectable stage methods, normalizer choices, or no-op bypasses.
**Why.** The product is an auditable workflow, not a menu of interchangeable agents.
**Breaks if violated.** A run can silently skip required grounding or use an undocumented method.

### CONST-2 — TERMite is mandatory
**Rule.** Stage 0 MUST call TERMite for every full pipeline run and fixed stage inspection command. Missing TERMite credentials or toolkit support is a blocking configuration error, not permission to continue with an empty enhancement.
**Why.** Stage 0 runs over the per-field fragments produced by Stage 1. TERMite supplies preferred labels, entity types, and synonyms that the post-Stage-1 `reconcile_with_annotations` pass uses to adjust routing (e.g. promoting a PK parameter from `question` to `filter`), and that seed Stage 2 translation pools. Absent TERMite, brand names, scientific names, and retrieval-defining PK parameters can be silently lost before translation.
**Breaks if violated.** Brand names, scientific names, and retrieval-defining PK parameters can be silently lost before translation.

### CONST-3 — Closed sets are authoritative
**Rule.** A closed-set translation MUST emit only values that are members of the field's provided closed set. `[]` or `None` means invalid. An invalid translation MUST NOT narrow API queries, post-filters, facets, or display columns.
**Why.** The redesign exists precisely because invented values produced wrong or empty queries.
**Breaks if violated.** The system reintroduces the legacy hallucinated-filter failure mode.

### CONST-4 — Open fields become runtime closed sets
**Rule.** An open-set filter (`parameter`, `parameterDisplay`, `studyGroup`, `age`, `dose`, `duration`) MUST be deferred until datapoints are fetched. The unique fetched values become the runtime closed set, and the same closed-set translation contract selects the post-filter subset.
**Why.** Open fields cannot be safely grounded before the data reveals their actual value space.
**Breaks if violated.** Free-text guesses can zero valid results or retain invalid matches without an audit trail.

### CONST-5 — Stage 1 routes only
**Rule.** The decomposer MUST segment and route the user's own words into field components. It MUST NOT normalize, ground, expand, or consult controlled vocabularies.
**Why.** Routing and value selection are separate, independently testable concerns.
**Breaks if violated.** The pipeline collapses back into a monolithic translator.

### CONST-6 — Typed contracts at every boundary
**Rule.** Stage boundaries, execution results, runtime closed sets, and post-filter results MUST be represented by typed Pydantic contracts. Final machine queries MUST be structurally validated before being treated as successful.
**Why.** Typed boundaries eliminate fragile free-text parsing and enable per-step evaluation.
**Breaks if violated.** Malformed payloads and ambiguous traces reach downstream stages.

### CONST-7 — Boolean intent is explicit
**Rule.** Within-field boolean groups and cross-field boolean assembly MUST be represented in data (as `boolean_group` objects and `AND`/`OR`/`NOT` tree nodes), not implied by prose.
**Why.** SME cases distinguish OR and AND within a field; the API boolean tree must reflect that distinction exactly.
**Breaks if violated.** Retrieval breadth changes invisibly, especially for multi-value gold cases.

### CONST-8 — Normalization policy is fixed
**Rule.** Misspelling and cleanup behavior MUST follow the documented field/bucket policy (fuzzy closed-set correction for closed fields, conservative cleanup for open fields, drug-specific normalizer for drug fields). It MUST NOT be exposed as a selectable stage or `noop` option.
**Why.** Normalization is part of deterministic translation safety, not a runtime experiment.
**Breaks if violated.** Closed-set matching can drift between runs; open-set filters can be handled by undocumented rules.

### CONST-9 — Hierarchy is reusable grounding logic
**Rule.** Class labels (drug class → API-resolved subtree), exact species class labels (server-resolved), colloquial species groups without exact class labels (expanded to member species), and source hierarchy (document → FDA/EMA parent) MUST be handled by shared taxonomy/runtime grounding helpers in `taxonomy/index.py`, not by one-off prompt text.
**Why.** The same parent/child semantics recur across drugs, species, and sources.
**Breaks if violated.** Fixes for one field do not generalize and class breadth regresses.

### CONST-10 — Service differences are in configuration
**Rule.** PK field buckets, taxonomies, entity routing, facets, invariants, and serializers MUST live in `ServiceConfig`/`FieldSpec` data objects. Shared stage code MUST NOT fork per service.
**Why.** The pipeline shape is common; only the configuration differs.
**Breaks if violated.** Stage logic becomes duplicated and inconsistent across services.

### CONST-11 — Tests are hermetic through fakes, not product bypasses
**Rule.** Offline tests MUST avoid network, LLM, and TERMite calls by injecting fakes, fixtures, or monkeypatched clients through `conftest.py`. They MUST NOT preserve public no-op or alternate stage methods as the testing mechanism.
**Why.** The product path must stay fixed while local test feedback remains cheap and deterministic.
**Breaks if violated.** Test convenience leaks into production behavior.

### CONST-12 — Evaluation is per-step first
**Rule.** Each stage's output MUST be independently scorable against its expected output; `Expected Count` from `docs/PPPK.xlsx` is the end-to-end signal, not the only metric.
**Why.** Decomposition only helps if failures can be attributed to the stage that caused them.
**Breaks if violated.** The project trades one opaque box for several opaque boxes.

### CONST-13 — Secrets are lazy and never committed
**Rule.** Credentials MUST be read only when the stage that needs them is invoked. `.env` and real credential files MUST never be committed. `.env.example` is keys-only.
**Why.** Imports and offline tests must remain safe; VCS must not leak credentials.
**Breaks if violated.** Secret exposure and broken offline imports.

### CONST-14 — Quality gates pass before merge
**Rule.** No implementation change merges unless the quality gates below pass (or a documented docs/spec-only exception applies).
**Why.** The package must stay importable, lint-clean, formatted, and tested.
**Breaks if violated.** Regressions accumulate outside the spec pipeline.

## Technology Stack

| Layer | Technology | Version/Notes | Prohibited alternatives |
|-------|------------|---------------|-------------------------|
| Language | Python | 3.11+ | Rewriting in another language |
| Package/build | `pyproject.toml`, hatchling, uv/pip | Existing layout | Ad-hoc setup scripts |
| Stage orchestration | Fixed Python calls in `pipeline.py` | No public stage backend selection | Stage registries or runtime method options |
| Typed contracts | Pydantic | v2, `src/oppp/models.py` | Untyped stage-boundary dicts |
| Service config | Dataclasses (`ServiceConfig`/`FieldSpec`) | `src/oppp/services/` | Service-specific forks in shared stages |
| Entity recognition | SciBite TERMite toolkit | Required Stage 0 invocation | No-op enhancement or optional TERMite in full runs |
| LLM integration | LangChain/OpenAI-compatible structured output via Portkey | Lazy `llm` extra, `oppp.llm` factory | Free-text LLM output at stage boundaries |
| Grounding | CSV/runtime closed sets, taxonomy indexes, RapidFuzz, LLM enrichment/selection | `taxonomy/index.py` | Prompt-only value generation |
| Runtime filtering | Row execution + runtime closed-set post-filtering | Per-field `PostFilterResult` | Direct open-field hard filters as row-mode substitute |
| Fuzzy matching | RapidFuzz | CSV and runtime closed-set lookup | Bespoke fuzzy matching in core paths |
| Normalization | Fixed field/bucket policy | Closed-set fuzzy correction; conservative open-set cleanup | Runtime normalizer selection |
| HTTP core | `urllib.request` | Count and row execution | Mandatory third-party HTTP client in core |
| CLI | Typer | `src/oppp/cli.py` | Hand-rolled CLI parser |
| UI | Streamlit | Lazy `ui` extra, `src/oppp/ui/app.py` | UI code in core stages |
| Diagram | draw.io XML + PNG | `docs/agent-dag.drawio` as editable source | Registry-derived pluggable-backend diagram |
| Reports | openpyxl | Lazy `report` extra | Mandatory spreadsheet dependency |
| Lint/format | Ruff | `ruff check`, `ruff format --check` | Mixed linters/formatters |
| Tests | pytest | Offline default suite with fakes in `conftest.py` | Networked default tests |

## Development Workflow

### Quality Gates
All four must pass before any implementation change is merged:
1. `python3 -m compileall src/oppp`
2. `ruff check src tests`
3. `ruff format --check src tests`
4. `pytest -q`

### Adding a New Component
1. Start by updating `docs/`; product behavior changes never originate in code.
2. Define or reuse the typed Pydantic contract first.
3. Wire the component into the fixed pipeline path without adding a user-selectable method.
4. Keep any model, TERMite, UI, report, or network dependency lazy at import time.
5. Add hermetic tests using fakes or fixtures in `conftest.py`, plus one integration test if the component changes cross-stage behavior.
6. Add or update per-step evaluation coverage where the output has a gold reference.

### Schema / Data Contract Changes
1. Update the Pydantic model or service dataclass.
2. Update `specs/technical.md` contract table.
3. Update `specs/requirements.md` and `specs/evaluation.md` coverage.
4. Run the Quality Gates.

## Governance
- Product intent changes start in `docs/` and flow through `/mdtechnical`.
- Constitution changes are versioned: MAJOR for reversed principles, MINOR for added principles, PATCH for clarifications.
- `/mdevaluation` audits these principles through `specs/evaluation.md`; a principle without an evaluation criterion is incomplete.
