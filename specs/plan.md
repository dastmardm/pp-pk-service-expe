# Implementation Plan

## Summary

Replace the monolithic NL→machine-query prompt with a chain of pluggable,
independently-evaluable stages (optional enhance → decompose → translate →
aggregate) for the PharmaPendium Safety service, grounding closed-vocabulary values
against on-disk taxonomies and validating the final query. The deterministic core
and Safety path are already built; the remaining work wires the production model
backends, builds per-step + LLM-as-judge evaluation, completes the inspection UI,
reconciles two known config mismatches (TERMite env-var names; per-step gold-set
location), and extends to PK/RTB.

## Work Breakdown

The project is decomposed as the Work Breakdown Structure in `specs/tasks.md`, cut by
**architectural layer** (`../CONVENTIONS.md` → Work Breakdown Structure). The cut and
its rationale:

- **W1 (root)** owns the single convergent file — `pyproject.toml` — because the
  dependency set is genuinely project-global: every subtree contributes the deps it
  needs and the root declares their union and runs one resolver pass.
- **W2 — Foundation & contracts.** The shared substrate every other layer imports:
  typed contracts (`models.py`), the registry primitive, settings + env template,
  taxonomy grounding/expansion, the misspelling normalizers, and the lazy LLM helper.
  It depends on nothing and resolves first.
- **W3 — Service configuration.** `ServiceConfig`/`FieldSpec` plus the Safety/PK/RTB
  data objects. It carries every per-service difference so stage code stays shared
  (CONST-12). The `services/__init__.py` barrel is its convergent file.
- **W4 — Pipeline stages.** The four stage modules (each a pluggable backend pair).
  The `stages/__init__.py` barrel is its convergent file.
- **W5 — Integration & surfaces.** `pipeline.py` (the orchestrator), the CLI, query
  execution, the DAG export, and the Streamlit inspector.
- **W6 — Evaluation.** The count-based harness, per-field compare, the per-step
  comparators, the LLM-as-judge, and the per-step gold-set builder; `eval/__init__.py`
  is its convergent barrel.
- **W7 — Offline test suite.** One leaf per test module, gating the whole tree on a
  green hermetic `pytest -q`.

This cut keeps every node's `Owns` list disjoint and the union equal to the
`skeleton.md` file set. Ordering is carried by the tree plus the dependency edges
(intra-subtree `After`, inter-layer cross-tree edges), not by sequential "phase"
bands: the effective order is foundation → services → stages → integration →
evaluation → tests, and the combined edge set is acyclic.

## Execution Model

`/implement` runs the WBS as a **fork-join** over the tree:

- Leaf nodes with no unmet dependency form a **wave** and run **concurrently** —
  safely, because the file-ownership invariant guarantees no two active nodes ever
  write the same file (no locks, no worktree isolation needed).
- A **summary** node blocks until **all** its children resolve, then in order:
  (1) writes any **convergent file** it owns from its children's reported
  contributions — the package barrels (`services/__init__.py`, `stages/__init__.py`,
  `eval/__init__.py`) assembled append-only, and at the **root** the `pyproject.toml`
  manifest whose dependency union is declared once and resolved with a single
  package-manager invocation; (2) runs its **`Review`** integration check;
  (3) reports a structured status upward.
- The **root** resolves last; its Review is the project-level gate (ruff clean,
  `pytest -q` green offline, an offline `oppp run --no-execute` producing a validated
  Safety query).

The file-ownership invariant is the sole parallel-safety guarantee. Because of it,
**the same tree walked sequentially in bottom-up (post-order) order produces an
identical result** — concurrency is an optimisation, not a correctness requirement.
A node that fails reports `FAIL` upward; its parent reports a partial result naming
the failed subtree, and dependents are skipped (reported), never blocked.

## Key Decisions

| Decision | Options considered | Choice | Rationale |
|----------|--------------------|--------|-----------|
| Pipeline shape | one prompt; agentic free-form; fixed staged chain | fixed staged chain | Each stage is small, testable, and isolatable (CONST-4/8). |
| WBS cut | by layer; by feature/service vertical | by architectural layer | Files group by layer; a layer cut keeps `Owns` lists disjoint and the dependency order linear (foundation→…→tests). |
| Decomposition vocabulary | vocab-aware routing; vocab-free | vocab-free (`llm`); `gazetteer` only as offline double | Separates routing from grounding (CONST-2). |
| Grounding mechanism | inline vocab in prompt; tool look-up | tool look-up whose output is the value | Enforces grounding and is auditable (CONST-1). |
| Aggregation | model emits raw JSON; model emits structure only | structure-only plan, rendered+validated deterministically | Output is always legal (CONST-3). |
| Hermeticity | live-only; doubles | offline doubles for every model step | Tests/eval run with no creds/network (CONST-8). |
| Per-service variation | fork stage code; config object | `ServiceConfig` data | Shared stage code (CONST-12). |
| Eval (now) vs (target) | count-only; per-step + judge | count-based now (W6.1/W6.2); per-step + judge as forward work (W6.3/W6.4) | Ship a baseline; build per-step as the dataset matures. |

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| TERMite env-var names in `.env` don't match `config.py` | High (present) | Med (enhancer can't auth) | Reconcile in W2.3; enhancer is optional so core unaffected. |
| Per-step gold set at `docs/sme_stage_cases.csv` but builder writes `inputs/` | High (present) | Med (eval reads wrong file) | Reconcile path in W6.5; spec/skeleton follow the docs location. |
| LLM-as-judge gives non-reproducible scores | Med | Med | Constrain to a typed verdict, log reasons, prefer deterministic comparators, spot-check vs SME (W6.4). |
| Result counts drift with DB updates | High | Low | Tolerance band; treat as signal not gate (NFR/REQ-019). |
| Heavy extras leak into the core import path | Low | High | Lazy imports (NFR-005); offline test guards (CONST-8); W2.6 confirms the core imports clean. |
| Gold set small & Safety-centric | High | Med | W3.3/W3.4 add PK/RTB; future negative/ambiguity cases. |
| Cross-tree edges between layers add scheduling coupling | Med | Low | Edges are coarse (consumer→producer summary) and acyclic; sequential bottom-up execution satisfies them trivially. |

## Constitution Check

No principle from `specs/constitution.md` is violated by this plan:
- The hermetic offline core (CONST-8) is preserved: model backends are real work but
  the offline doubles remain the test/eval default, and W2.6/W7 assert the core imports
  and the suite runs with no network/LLM.
- Grounding (CONST-1), vocab-free decomposition (CONST-2), explicit booleans (CONST-5),
  and typed boundaries (CONST-3) are foundation/stage invariants carried through every
  node's `Done-when`.
- The two known mismatches (TERMite env names, per-step dataset path) are
  **implementation defects**, not principle conflicts; W2.3 and W6.5 resolve them.
- New services (W3.3/W3.4) are added as `ServiceConfig` data only (CONST-12).
- **Tension:** REQ-020/021/023 are SHOULD and only partly realised today (per-step +
  judge eval, full UI selectors). This is forward work (W6.3/W6.4/W5.5), not a
  violation — the MUST core (REQ-001…REQ-018, REQ-024…027) is satisfied by the
  already-built foundation/services/stages/integration leaves.
