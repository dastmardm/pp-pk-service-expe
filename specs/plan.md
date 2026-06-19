# Implementation Plan

## Summary

Replace the monolithic NL→machine-query prompt with a chain of pluggable,
independently-evaluable stages (optional enhance → decompose → translate →
aggregate) for the PharmaPendium Safety service, grounding closed-vocabulary
values against on-disk taxonomies and validating the final query. The
deterministic core and Safety path are already built; the remaining work wires the
production model backends, builds per-step + LLM-as-judge evaluation, completes the
inspection UI, and reconciles two known config mismatches before extending to PK/RTB.

## Phases

### Phase 1 — Foundation *(built)*
**Goal**: a hermetic, deterministic core with the Safety service end to end.
**Deliverable**: typed contracts (`models.py`), registries (`registry.py`),
taxonomy grounding + hierarchy expansion (`taxonomy/index.py`), the four stages
with offline doubles, `ServiceConfig` for Safety, the sequential pipeline, the CLI,
count-based evaluation, the Streamlit baseline, and the offline test suite.
**Success signal**: `pytest -q` green offline; `oppp run --no-execute` produces a
valid Safety query with the doubles.

### Phase 2 — Production model backends
**Goal**: the model-backed defaults (`llm` decompose, `tool` translate, `llm`
aggregate, `termite` enhance) verified live.
**Deliverable**: working structured-output decomposition/aggregation, the LLM term
selector, and a credential-reconciled TERMite enhancer.
**Success signal**: `oppp run "<q>"` (defaults) returns a valid query; `oppp run
--case N --execute` returns a count; TERMite resolves a synonym/brand case.

### Phase 3 — Per-step & judge evaluation
**Goal**: realise CAP-8 beyond count accuracy.
**Deliverable**: per-step comparators against `docs/sme_stage_cases.csv` (set match
for enhance, routing/type/boolean for decompose, set-F1 for closed-vocab translate,
structural for aggregate) plus the constrained LLM-as-judge for the free-text
steps; reconcile the per-step dataset location.
**Success signal**: a per-step report prints per-stage scores; judge verdicts are
typed and logged.

### Phase 4 — Inspection UI completion
**Goal**: realise the full inspector described in `docs/06-implementation/streamlit-ui.md`.
**Deliverable**: per-step backend selectors (Enhancer/Translator/Aggregator/Execute),
a Stage-0 output panel, and the gold-set question picker.
**Success signal**: every stage's backend is selectable and every stage's output is
shown, including Stage 0; picking a gold question runs it.

### Phase 5 — Coverage expansion
**Goal**: broaden beyond Safety and the documented open questions.
**Deliverable**: PK and RTB `ServiceConfig`s (RTB `where_clause` serializer), a
`targets` resolution path, MedDRA effect roll-ups, and negative/ambiguity gold
cases.
**Success signal**: PK/RTB questions produce valid queries; class/roll-up cases
match SME expansions.

## Key Decisions

| Decision | Options considered | Choice | Rationale |
|----------|--------------------|--------|-----------|
| Pipeline shape | one prompt; agentic free-form; fixed staged chain | fixed staged chain | Each stage is small, testable, and isolatable (CONST-4/8). |
| Decomposition vocabulary | vocab-aware routing; vocab-free | vocab-free (`llm`); `gazetteer` only as offline double | Separates routing from grounding (CONST-2). |
| Grounding mechanism | inline vocab in prompt; tool look-up | tool look-up whose output is the value | Enforces grounding and is auditable (CONST-1). |
| Aggregation | model emits raw JSON; model emits structure only | structure-only plan, rendered+validated deterministically | Output is always legal (CONST-3). |
| Hermeticity | live-only; doubles | offline doubles for every model step | Tests/eval run with no creds/network (CONST-8). |
| Per-service variation | fork stage code; config object | `ServiceConfig` data | Shared stage code (CONST-12). |
| Eval (now) vs (target) | count-only; per-step + judge | count-based now, per-step+judge as Phase 3 | Ship a baseline; build per-step as the dataset matures. |

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| TERMite env-var names in `.env` don't match `config.py` | High (present) | Med (enhancer can't auth) | Reconcile in Phase 2; enhancer is optional so core unaffected. |
| Per-step gold set at `docs/sme_stage_cases.csv` but builder writes `inputs/` | High (present) | Med (eval reads wrong file) | Reconcile path in Phase 3; spec/skeleton follow the docs location. |
| LLM-as-judge gives non-reproducible scores | Med | Med | Constrain to a typed verdict, log reasons, prefer deterministic comparators, spot-check vs SME. |
| Result counts drift with DB updates | High | Low | Tolerance band; treat as signal not gate (NFR/REQ-019). |
| Heavy extras leak into the core import path | Low | High | Lazy imports (NFR-005); offline test guards (CONST-8). |
| Gold set small & Safety-centric | High | Med | Phase 5 adds PK/RTB, negative, and ambiguity cases. |

## Constitution Check

No principle is violated by this plan:
- Phases preserve the hermetic offline core (CONST-8): model backends arrive in
  Phase 2 but the doubles remain the test/eval default.
- Grounding (CONST-1), vocab-free decomposition (CONST-2), and explicit booleans
  (CONST-5) are Phase-1 foundations carried through all phases.
- The two known mismatches (TERMite env names, per-step dataset path) are
  **implementation defects**, not principle conflicts; Phases 2–3 resolve them.
- New services (Phase 5) are added as `ServiceConfig` data only (CONST-12).
**Tension:** REQ-020/021/023 are SHOULD and only partly realised today; this is a
phased rollout, not a violation — the MUST core (REQ-001…REQ-018, REQ-024…027) is
satisfied in Phase 1.
