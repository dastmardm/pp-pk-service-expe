# Project Constitution

## Core Principles

### CONST-1 - Closed sets are authoritative
**Rule.** A closed-set translation MUST emit only values selected from the field's
provided closed set. `[]` or `None` means invalid, and an invalid translation MUST
not narrow API queries, post-filters, facets, or display columns.
**Why.** The redesign exists because generated values created wrong or empty
queries.
**Breaks if violated.** The system silently reintroduces the legacy invented-value
failure mode.

### CONST-2 - Open fields become runtime closed sets
**Rule.** An open-set filter is deferred until datapoints are fetched, its unique
fetched values become a runtime closed set, and the same closed-set translation
contract selects the post-filter values.
**Why.** Open fields cannot be safely grounded before the data reveals their
actual value space.
**Breaks if violated.** Free-text guesses can zero valid results or keep invalid
matches without an audit trail.

### CONST-3 - Stage 1 routes only
**Rule.** The production decomposer MUST segment and route the user's own words
into field components. It MUST NOT normalize, ground, expand, or consult
vocabularies. Gazetteer routing remains an offline double.
**Why.** Routing and value selection are separate, testable concerns.
**Breaks if violated.** The pipeline collapses back into a monolithic translator.

### CONST-4 - Typed contracts at every boundary
**Rule.** Stage boundaries and execution results MUST be represented by typed
contracts, and final machine queries MUST be structurally validated before being
treated as successful.
**Why.** Typed boundaries remove fragile free-text parsing and support per-step
evaluation.
**Breaks if violated.** Malformed payloads and ambiguous traces reach downstream
stages.

### CONST-5 - Boolean intent is explicit
**Rule.** Within-field boolean groups and cross-field boolean assembly MUST be
represented in data, not implied by prose.
**Why.** SME cases distinguish OR, AND, and cross-field retrieval rules.
**Breaks if violated.** Retrieval breadth changes invisibly, especially Q7, Q13,
and Q14 style queries.

### CONST-6 - Hierarchy is reusable grounding logic
**Rule.** Class labels, colloquial groups, curated sets, and effect rollups MUST be
handled by shared taxonomy/runtime grounding helpers, not one-off prompt text.
**Why.** The same parent/child semantics recur across drugs, effects, species,
sources, and indications.
**Breaks if violated.** Fixes for one field do not generalize and class breadth
regresses.

### CONST-7 - Services differ by configuration
**Rule.** Safety, PK, and RTB differences MUST live in service configuration:
field buckets, taxonomies, entity routing, facets, invariants, and serializers.
Shared stage code MUST NOT fork per service.
**Why.** The pipeline shape is common across services.
**Breaks if violated.** Stage logic becomes duplicated and inconsistent.

### CONST-8 - Offline paths remain hermetic
**Rule.** Offline doubles MUST allow tests and offline evaluation to run with no
network, no LLM credentials, and no TERMite credentials. Heavy optional
dependencies MUST be imported lazily.
**Why.** Local development and CI need stable, cheap feedback.
**Breaks if violated.** The default suite becomes flaky, slow, or credential-bound.

### CONST-9 - Evaluation is per-step first
**Rule.** Each stage's output MUST be independently scorable against its gold
column where a gold column exists; count accuracy is an end-to-end signal, not the
only metric.
**Why.** Decomposition only helps if failures can be assigned to the stage that
caused them.
**Breaks if violated.** The project trades one opaque box for several opaque boxes.

### CONST-10 - Secrets are lazy and never committed
**Rule.** Credentials MUST be read only when the selected backend needs them.
`.env` and real credential files MUST never be committed.
**Why.** The deterministic core must run without secrets and VCS must not leak
credentials.
**Breaks if violated.** Secret exposure and broken offline imports.

### CONST-11 - Quality gates pass before merge
**Rule.** No implementation change merges unless the quality gates below pass or a
documented docs/spec-only exception applies.
**Why.** The package must stay importable, lint-clean, formatted, and tested.
**Breaks if violated.** Regressions accumulate outside the spec pipeline.

## Technology Stack
| Layer | Technology | Version/Notes | Prohibited alternatives |
|-------|------------|---------------|-------------------------|
| Language | Python | 3.11+ | Rewriting the pipeline in another language |
| Package/build | `pyproject.toml`, hatchling, uv/pip | Existing package layout | Ad-hoc setup scripts |
| Typed contracts | Pydantic | v2 models in `src/oppp/models.py` | Untyped stage-boundary dicts |
| CLI | Typer | Existing `oppp` command | Hand-rolled CLI parser |
| Matching | RapidFuzz | CSV fuzzy lookup | Bespoke fuzzy matching in core paths |
| Env loading | python-dotenv | Lazy `.env` loading | Reading secrets at import time |
| HTTP core | `urllib.request` | Count and row execution | Adding a mandatory HTTP dependency to core |
| Optional LLM | LangChain/LangChain-OpenAI/LangGraph/DSPy/OpenAI | Lazy `llm` extra | Importing LLM stack in offline paths |
| Optional UI | Streamlit | Lazy `ui` extra | UI code in core stages |
| Optional reports | openpyxl | Lazy report extra | Mandatory spreadsheet dependency |
| Lint/format | Ruff | `ruff check`, `ruff format --check` | Mixed linters/formatters |
| Tests | pytest | Offline default suite | Networked default tests |

## Development Workflow

### Quality Gates
1. `python3 -m compileall src/oppp`
2. `ruff check src tests`
3. `ruff format --check src tests`
4. `pytest -q`

### Adding a New Component
1. Define or reuse the typed contract first.
2. Register the backend by name in the relevant registry.
3. Keep any model/network dependency lazy and provide an offline path.
4. Add focused tests for the component and one integration test if the component
   changes cross-stage behavior.
5. Add or update per-step evaluation where the output has a gold reference.

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
