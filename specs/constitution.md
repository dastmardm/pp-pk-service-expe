# Project Constitution

The binding rules every contributor and AI assistant follows unconditionally when
working on `oppp` (the decomposed NL→machine-query translator). Each principle
states the rule, why it exists, and what breaks if it is violated.

## Core Principles

### CONST-1 — Ground, don't generate
**Rule.** For a closed-vocabulary field, the emitted value MUST be selected from
that field's controlled vocabulary (`CONTRACT-TAXONOMY-CSV`). On no match, surface
the gap (flag / "not found") — never substitute a model-invented value.
**Why.** The legacy monolith's defining failure was inventing field values absent
from the vocabulary.
**Breaks if violated.** Queries silently retrieve wrong/empty record sets and the
core promise (grounding) is lost.

### CONST-2 — Decomposition is vocab-free
**Rule.** The production Stage-1 decomposer (`llm`) MUST only segment and route
using the user's words and the field catalogue; it MUST NOT resolve, normalise, or
consult any vocabulary. The vocab-using `gazetteer` decomposer is an **offline
test/eval double only** and MUST NOT be presented as production behaviour.
**Why.** Keeps "what is asked" separate from "how to express it"; grounding belongs
to Stage 2.
**Breaks if violated.** Routing and grounding concerns entangle, re-creating the
monolith's untestability.

### CONST-3 — Typed contracts everywhere; the final query is always validated
**Rule.** Every stage boundary MUST exchange a validated Pydantic model
(`models.py`). Model-backed steps MUST prefer structured/typed output over
free-text-then-parse. The final `MachineQuery` MUST pass Stage-3 structural
validation regardless of how it was produced.
**Why.** Validation replaces the legacy regex/brace JSON scraping; the schema is
the contract end to end.
**Breaks if violated.** Malformed queries reach the API; the legacy parse-failure
class of bug returns.

### CONST-4 — One field, one translator
**Rule.** Per-field translation MUST be isolatable and testable for a single field
without running the rest of the chain.
**Why.** A regression in one field must be catchable in isolation.
**Breaks if violated.** Field rules become mutually entangled and un-regression-testable.

### CONST-5 — Boolean structure is explicit
**Rule.** Within-field booleans MUST be decided in Stage 2 (boolean groups);
cross-field booleans MUST be decided in Stage 3. Boolean intent MUST never be
implicit in prose.
**Why.** Auditable, correct AND/OR/NOT semantics.
**Breaks if violated.** Silent logic errors in retrieval breadth.

### CONST-6 — Hierarchy is a first-class operation
**Rule.** Class→members / category→terms / parent→children expansion MUST be a
documented, reusable operation over the generic `parent_id`/`parent_name`
structure — not ad-hoc per field.
**Why.** The gold set's class/roll-up questions require correct breadth.
**Breaks if violated.** Over- or under-broad result sets (the legacy "Rodent vs
rat+mouse" class of error).

### CONST-7 — Enhancement is optional
**Rule.** Stage 0 MUST default to `noop`; the pipeline MUST function end-to-end
with no enhancer. TERMite is an opt-in booster, never a required pre-step.
**Why.** The system must run without external NER/creds.
**Breaks if violated.** The core becomes coupled to an external service.

### CONST-8 — Pluggable, isolatable, and hermetic by default
**Rule.** Every stage MUST be selectable by name from a registry and runnable
alone. Offline doubles (`noop`/`gazetteer`/`deterministic`) MUST keep the test
suite and per-stage evaluation runnable with **no LLM call and no network**.
**Why.** Isolation/evaluation and CI depend on a hermetic core.
**Breaks if violated.** Tests/eval require credentials and network; CI becomes
flaky and expensive.

### CONST-9 — Per-step evaluability
**Rule.** Each step MUST be scorable against a gold reference
(`CONTRACT-GOLD-PERFIELD`, `CONTRACT-GOLD-PERSTEP`). Steps whose output has no
canonical form (Stage-1 fragments, Stage-2 open-field patterns, Stage-3 structure
tie-breaks) MUST be scored by a constrained LLM-as-judge returning a typed verdict,
not by exact match; deterministic comparators MUST be used wherever the output is
canonicalisable.
**Why.** Breaking the monolith into steps only pays off if each step is measurable.
**Breaks if violated.** We trade one opaque box for four; regressions become
untraceable.

### CONST-10 — Secrets are external, lazy, and never committed
**Rule.** Credentials MUST be read from the project `.env` only when a model/entity
backend is actually invoked. The deterministic core MUST need none. `.env` and any
credential file MUST NOT be committed.
**Why.** The core must run offline; secrets must not leak into VCS.
**Breaks if violated.** Secret exposure; the offline guarantee is lost.

### CONST-11 — Quality gates pass before merge
**Rule.** No change merges unless the Quality Gates below pass.
**Why.** Style and the offline behavioural contract stay green continuously.
**Breaks if violated.** Drift and silent breakage accumulate.

### CONST-12 — Service variation lives in config, not stage code
**Rule.** Differences between Safety/PK/RTB (fields, buckets, facet allow-list,
entity routing, invariants, output surface) MUST be carried by `ServiceConfig`
data; stage code stays shared.
**Why.** The pipeline shape is identical across services.
**Breaks if violated.** Per-service forks of stage logic proliferate.

## Technology Stack

| Layer | Technology | Version / Notes | Prohibited alternatives |
|-------|------------|-----------------|-------------------------|
| Language | Python | ≥ 3.11 (`requires-python`) | Other languages for pipeline code |
| Typed contracts | Pydantic | v2 (`>=2.6`) | Hand-rolled dict validation; regex JSON scraping |
| Pluggability | `Registry[T]` (in-repo) | one per stage + services | Hard-wired `if backend == …` dispatch |
| Per-service config | `ServiceConfig`/`FieldSpec` dataclasses | `services/base.py` | Per-service forks of stage code |
| Fuzzy matching | rapidfuzz | `>=3.6` | Bespoke edit-distance in core paths |
| CLI | Typer | `>=0.12` | argparse hand-rolled command tree |
| HTTP execution | stdlib `urllib` | core, no extra dep | Adding `requests`/`httpx` to the core |
| Env loading | python-dotenv | `>=1.0`; lazy | Reading secrets at import time |
| Model stack *(extra `llm`)* | LangChain, LangChain-OpenAI, LangGraph, DSPy, openai | imported lazily | Importing these in the deterministic core |
| Interactive UI *(extra `ui`)* | Streamlit | `>=1.36` | UI logic in the core package |
| Diagram export *(extra `viz`)* | matplotlib | `>=3.7` | System Graphviz dependency |
| Lint + format | Ruff | `>=0.5`; line-length 100; `E,F,I,UP,B,SIM` | Other linters/formatters |
| Tests | pytest | `>=8.0`; `testpaths=tests`, `pythonpath=src` | Network/credential-dependent tests in the default suite |
| Env / packaging | uv + hatchling (`pyproject.toml`) | extras gate heavy stacks | Ad-hoc pip; committing a lockfile-bypassing setup |
| NER *(external, optional)* | SciBite TERMite | opt-in Stage 0 only | Making TERMite mandatory |
| Search service *(external)* | PharmaPendium search API | POST JSON payload | — |

## Development Workflow

### Quality Gates
Ordered checks that MUST pass before any change is merged (mirror these in
`specs/git.md` → Pre-Commit Gates and in `.claude/settings.json`):

1. `ruff check src tests` — lint clean.
2. `ruff format --check src tests` — formatting clean.
3. `pytest -q` — the offline suite passes with **no network and no LLM** (uses the
   `noop`/`gazetteer`/`deterministic` doubles).

### Adding a New Component
1. Implement the stage's typed protocol (see `specs/technical.md` → Component
   Interfaces).
2. `register`/`add` it under a string name in the relevant registry.
3. If it is model-backed, provide or confirm an **offline double** so the hermetic
   suite still runs (CONST-8); import heavy deps lazily.
4. Add unit tests under `tests/` exercising the offline path.
5. Add/extend the per-step evaluation hook and gold expectation (CONST-9).
6. For a new service, add a `ServiceConfig` only — do not fork stage code (CONST-12).

### Schema / Data Contract Changes
1. Change the Pydantic model / dataclass in `models.py` / `services/base.py`.
2. Update the matching `CONTRACT-*` entry in `specs/technical.md`.
3. Update the affected `EVAL-NNN` criteria in `specs/evaluation.md`.
4. Run the Quality Gates. A contract change with no evaluation-criterion update is
   incomplete.

## Governance
- **Amendment.** Principles are amended by editing `./docs/` (the human source of
  truth) and re-running `/technical`, which re-propagates here. Specs are never
  hand-edited to diverge from `./docs/`.
- **Versioning.** Semantic: MAJOR = a principle removed/reversed; MINOR = a
  principle or stack entry added; PATCH = clarification. Record material changes in
  the commit per `specs/git.md`.
- **Compliance.** `/evaluation` audits the codebase against `specs/evaluation.md`,
  which encodes these principles as criteria. A constitution change that is not
  reflected in the evaluation criteria is not in force.
