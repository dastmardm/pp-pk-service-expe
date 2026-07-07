# Project Constitution

## Core Principles

### CONST-1 - The stage path is fixed
**Rule.** The public pipeline, CLI, UI, and evaluation harness MUST run the fixed
sequence: LLM expansion, TERMite enhancement, LLM decomposition, grounded
translation, LLM aggregation with deterministic validation, execution, runtime
translation, and post-filtering. They MUST NOT expose selectable stage methods,
normalizer choices, or no-op bypasses.
**Why.** The product is an auditable workflow, not a menu of interchangeable
agents.
**Breaks if violated.** A run can silently skip required grounding or use a
method the docs do not describe.

### CONST-2 - TERMite is mandatory
**Rule.** Stage 0 MUST call TERMite for every full pipeline run and fixed stage
inspection. Missing TERMite credentials or toolkit support is a blocking
configuration error, not permission to continue with an empty enhancement.
**Why.** TERMite supplies labels, entity types, and synonyms that the later stages
depend on for routing and grounding.
**Breaks if violated.** Brand names, scientific names, target mechanisms, and
retrieval-defining terms can be lost before translation.

### CONST-3 - Closed sets are authoritative
**Rule.** A closed-set translation MUST emit only values selected from the
field's provided closed set. `[]` or `None` means invalid, and an invalid
translation MUST not narrow API queries, runtime post-filters, facets, or display
columns.
**Why.** The redesign exists because invented values created wrong or empty
queries.
**Breaks if violated.** The system reintroduces the legacy hallucinated-filter
failure mode.

### CONST-4 - Open fields become runtime closed sets
**Rule.** An open-set filter is deferred until datapoints are fetched. Its unique
fetched values become a runtime closed set, and the same closed-set translation
contract selects post-filter values.
**Why.** Open fields cannot be safely grounded before the data reveals their
actual value space.
**Breaks if violated.** Free-text guesses can zero valid results or keep invalid
matches without an audit trail.

### CONST-5 - Stage 1 routes only
**Rule.** The decomposer MUST segment and route the user's own words into field
components. It MUST NOT normalize, ground, expand, or consult controlled
vocabularies.
**Why.** Routing and value selection are separate, testable concerns.
**Breaks if violated.** The pipeline collapses back into a monolithic translator.

### CONST-6 - Typed contracts at every boundary
**Rule.** Stage boundaries, execution results, runtime closed sets, and
post-filter results MUST be represented by typed contracts. Final machine queries
MUST be structurally validated before being treated as successful.
**Why.** Typed boundaries remove fragile free-text parsing and support per-step
evaluation.
**Breaks if violated.** Malformed payloads and ambiguous traces reach downstream
stages.

### CONST-7 - Boolean intent is explicit
**Rule.** Within-field boolean groups and cross-field boolean assembly MUST be
represented in data, not implied by prose.
**Why.** SME cases distinguish OR, AND, and cross-field retrieval rules.
**Breaks if violated.** Retrieval breadth changes invisibly, especially
multi-value SME regressions.

### CONST-8 - Normalization policy is fixed
**Rule.** Misspelling and cleanup behavior MUST follow the documented field/bucket
policy. It MUST NOT be exposed as a selectable stage or `noop` option.
**Why.** Normalization is part of deterministic translation safety, not a runtime
experiment.
**Breaks if violated.** Closed-set matching can drift between runs and open-set
filters can be handled by undocumented rules.

### CONST-9 - Hierarchy is reusable grounding logic
**Rule.** Class labels, colloquial groups, curated sets, and effect rollups MUST
be handled by shared taxonomy/runtime grounding helpers, not one-off prompt text.
**Why.** The same parent/child semantics recur across drugs, effects, species,
sources, and indications.
**Breaks if violated.** Fixes for one field do not generalize and class breadth
regresses.

### CONST-10 - Services differ by configuration
**Rule.** Safety, PK, and RTB differences MUST live in service configuration:
field buckets, taxonomies, entity routing, facets, invariants, and serializers.
Shared stage code MUST NOT fork per service.
**Why.** The pipeline shape is common across services.
**Breaks if violated.** Stage logic becomes duplicated and inconsistent.

### CONST-11 - Tests are hermetic through fakes, not product bypasses
**Rule.** Offline tests MUST avoid network, LLM, and TERMite calls by injecting
fakes, fixtures, or monkeypatched clients. They MUST NOT preserve public no-op or
alternate stage methods as the testing mechanism.
**Why.** The product path must stay fixed while local feedback remains cheap and
deterministic.
**Breaks if violated.** Test convenience leaks into production behavior.

### CONST-12 - Evaluation is per-step first
**Rule.** Each stage's output MUST be independently scorable against its gold
column where a gold column exists; count accuracy is an end-to-end signal, not
the only metric.
**Why.** Decomposition only helps if failures can be assigned to the stage that
caused them.
**Breaks if violated.** The project trades one opaque box for several opaque
boxes.

### CONST-13 - Secrets are lazy and never committed
**Rule.** Credentials MUST be read only when the fixed stage that needs them is
invoked. `.env` and real credential files MUST never be committed.
**Why.** Imports and tests must remain safe, and VCS must not leak credentials.
**Breaks if violated.** Secret exposure and broken offline imports.

### CONST-14 - Quality gates pass before merge
**Rule.** No implementation change merges unless the quality gates below pass or
a documented docs/spec-only exception applies.
**Why.** The package must stay importable, lint-clean, formatted, and tested.
**Breaks if violated.** Regressions accumulate outside the spec pipeline.

## Technology Stack
| Layer | Technology | Version/Notes | Prohibited alternatives |
|-------|------------|---------------|-------------------------|
| Language | Python | 3.11+ | Rewriting the pipeline in another language |
| Package/build | `pyproject.toml`, hatchling, uv/pip | Existing package layout | Ad-hoc setup scripts |
| Stage orchestration | Fixed Python calls in `pipeline.py` | No public stage backend selection | Stage registries/options for product methods |
| Typed contracts | Pydantic | v2 models in `src/oppp/models.py` | Untyped stage-boundary dicts |
| Service config | Dataclasses and service registry | `ServiceConfig`/`FieldSpec` | Service-specific forks inside shared stages |
| Entity recognition | SciBite TERMite toolkit | Required Stage 0 invocation | No-op enhancement or optional TERMite in full runs |
| LLM integration | LangChain/OpenAI-compatible structured output via Portkey | Lazy `llm` extra and `oppp.llm` factory | Free-text LLM output at stage boundaries |
| Grounding | CSV/runtime closed sets, taxonomy indexes, RapidFuzz, LLM selection | Exact/fuzzy/enriched closed-set resolution | Prompt-only value generation |
| Runtime filtering | Row execution plus runtime closed-set post-filtering | Open-set filters become fetched-value closed sets | Direct open-field hard filters as row-mode substitute |
| Matching | RapidFuzz | CSV/runtime fuzzy lookup | Bespoke fuzzy matching in core paths |
| Normalization | Fixed field/bucket policy | Closed-set fuzzy correction, conservative open-set cleanup | Runtime normalizer options |
| HTTP core | `urllib.request` | Count and row execution | Mandatory third-party HTTP client in core |
| CLI | Typer | Existing `oppp` command | Hand-rolled CLI parser |
| UI | Streamlit | Lazy `ui` extra | UI code in core stages |
| Diagram | draw.io XML plus PNG | `docs/agent-dag.drawio` as editable source | Registry-derived pluggable-backend diagram |
| Reports | openpyxl | Lazy report extra | Mandatory spreadsheet dependency |
| Lint/format | Ruff | `ruff check`, `ruff format --check` | Mixed linters/formatters |
| Tests | pytest | Offline default suite with fakes | Networked default tests |

## Development Workflow

### Quality Gates
1. `python3 -m compileall src/oppp`
2. `ruff check src tests`
3. `ruff format --check src tests`
4. `pytest -q`

### Adding a New Component
1. Start by updating `docs/`; product behavior changes never originate in code.
2. Define or reuse the typed contract first.
3. Wire the component into the fixed path without adding a user-selectable method.
4. Keep any model, TERMite, UI, report, or network dependency lazy at import time.
5. Add hermetic tests using fakes or fixtures, plus one integration test if the
   component changes cross-stage behavior.
6. Add or update per-step evaluation where the output has a gold reference.

### Schema / Data Contract Changes
1. Update the model/dataclass contract.
2. Update `specs/technical.md` contract text.
3. Update `specs/requirements.md` and `specs/evaluation.md` coverage.
4. Run the Quality Gates.

## Governance
- Product intent changes start in `docs/` and flow through `/mdtechnical`.
- Constitution changes are versioned semantically: MAJOR for reversed principles,
  MINOR for added principles, PATCH for clarifications.
- `/mdevaluation` audits these principles through `specs/evaluation.md`; a
  principle without an evaluation criterion is incomplete.
