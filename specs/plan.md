# Implementation Plan

## Summary
The `oppp` v0.1 package implements the fixed PK pipeline through count execution and has typed stage models, service configs, taxonomy indexes, translation/aggregation logic, and evaluation scaffolding. The implementation work is to: (1) add typed row execution, runtime closed-set derivation, and post-filter models; (2) align service configuration to PK-only active scope; (3) update the evaluation harness to load `docs/PPPK.xlsx`; and (4) ensure the fixed-path invariant holds across pipeline, CLI, and UI — no selectable stage methods, no-op bypasses, or stale Safety/RTB-specific references in active code paths.

## Work Breakdown
The WBS has four top-level subtrees under root W1:

- **W1.1 — Contracts and config**: Pydantic models (REQ-001), config/secrets (REQ-027), normalizer interface (REQ-010). These are the shared foundation that all other subtrees import.
- **W1.2 — Service layer**: service base schema (REQ-019) and PK service config (REQ-011, REQ-012). The PK service spec is the authoritative field/bucket/invariant definition that stages consume.
- **W1.3 — Stages and execution**: the six fixed stage implementations (REQ-002 through REQ-018) plus count and row execution (REQ-013, REQ-014). Leaves inside W1.3 are mostly independent; the runtime narrowing and post-filter leaves depend on execution outputs.
- **W1.4 — Surfaces**: pipeline orchestrator (REQ-001, REQ-018), CLI (REQ-020), Streamlit UI (REQ-021), and DAG export (REQ-022). W1.4 leaves consume all prior subtrees.
- **W1.5 — Evaluation and tests**: gold-set harness (REQ-023), per-step comparators (REQ-024), regression cases (REQ-025), hermetic test fixtures (REQ-026), and per-module test files. W1.5 depends on W1.1–W1.4.

Convergent files:
- `src/oppp/models.py` is primarily written by W1.1.1 but W1.3 leaves contribute `PipelineResult` extensions; W1.1 (summary) merges those contributions.
- `pyproject.toml` (dependencies, extras, console script) receives contributions from multiple subtrees; W1 (root) is the convergent owner.

## Execution Model
Leaf nodes within a dependency wave run concurrently. Each summary node waits for all its leaf children to complete, then writes any convergent files it owns, runs a structural review assertion, and reports upward. The root node waits for all summaries, assembles the final `pyproject.toml`, runs the four quality gates, and signals completion.

Parallel leaves in W1.3: expand.py, enhance.py, decompose.py, translate.py (Stage 2A), and aggregate.py (Stage 3) can be developed concurrently once contracts (W1.1) and service config (W1.2) are settled. The row execution leaf (execute.py rows) and the Stage 2B/2C leaves depend on the row result type defined in W1.1.1.

The file-ownership invariant (one owner per file, every file owned) makes parallel leaf execution safe: no two leaves write the same file.

## Key Decisions

| Decision | Options considered | Choice | Rationale |
|----------|--------------------|--------|-----------|
| Row execution API discovery | Defer until runtime; assume same endpoint returns rows | Attempt rows through same endpoint; return `ok=false` typed result if unavailable | Preserves count-only path; avoids hard dependency on undiscovered API shape |
| Gold set loader | `csv` module; `openpyxl` | `openpyxl` (already in `report` extra) | PPPK.xlsx is XLSX; openpyxl is already declared for report export |
| Safety/RTB service files | Delete; keep but mark inactive; keep unchanged | Keep `services/safety.py` and `services/rtb.py` unchanged (not active scope) | Future use; removing would require coordinated test cleanup; docs scope is PK-only |
| Stage 2B/2C implementation | Full implementation now; stub with structured issue | Implement types and stubs that return structured `ok=false` issues | Keeps the contract clean for row mode without breaking v0.1 count-only harness |

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| PharmaPendium row API differs from count API | Medium | Medium | `execute_rows` returns typed unavailable result; count harness unaffected |
| `docs/PPPK.xlsx` column name `Quety number` (typo in source) causes read failure | Low | Medium | Read by column index or accept both spellings |
| openpyxl XLSX read raises on malformed workbook | Low | Low | Wrap in structured error; evaluation reports the issue without crashing |
| LLM structured output contract drift | Low | Medium | Pydantic v2 strict validation at LLM boundary; tests cover schema regression |

## Constitution Check
- **CONST-1 (fixed path)**: row execution and runtime post-filtering are new fixed stages; no user-selectable options introduced. ✓
- **CONST-2 (TERMite mandatory)**: W1.3.2 (enhance.py) preserves TERMite as mandatory. ✓
- **CONST-3 (closed sets)**: W1.3.4 (translate.py) extends to runtime closed sets without relaxing subset-only invariant. ✓
- **CONST-4 (open-field deferral)**: W1.3.5/W1.4.1 wire post-filter paths; v0.1 probe guards remain as count-mode fallback only. ✓
- **CONST-5 (Stage 1 routes only)**: W1.3.3 (decompose.py) explicitly excludes taxonomy imports; `Done-when` asserts no `TaxonomyIndex` import in decompose. ✓
- **CONST-6 (typed contracts)**: W1.1.1 adds `RowExecutionResult`, `RuntimeClosedSet`, `PostFilterResult` before any stage consumes them. ✓
- **CONST-7 (boolean intent explicit)**: W1.3.4 (translate.py) preserves `boolean_group` on `MachineSubquery`; W1.3.5 (aggregate.py) assembles boolean groups into `OR`/`AND` nodes. ✓
- **CONST-8 (normalization fixed)**: W1.1.3 (normalize/strategies.py) implements three named strategies with fixed dispatch; no selectable normalizer option exported. ✓
- **CONST-9 (hierarchy reusable)**: W1.2.5 (taxonomy/index.py) implements shared `parent_id`/`parent_name` traversal used by all taxonomy lookups. ✓
- **CONST-10 (service config)**: PK invariants stay in `services/pk.py`; no service logic enters shared stages. ✓
- **CONST-11 (hermetic tests)**: W1.5.5 (conftest.py) provides fake LLM and TERMite fixtures; `Done-when` asserts no unconditional live imports. ✓
- **CONST-12 (per-step evaluation first)**: W1.5.3 (per_step.py) exports five per-step comparator functions scored before the count harness rolls up. ✓
- **CONST-13 (lazy secrets)**: W1.1.2 keeps secrets lazy; W1.5 fixtures confirm offline test pass. ✓
- **CONST-14 (quality gates)**: root node W1 runs all four quality gates as its `Done-when`. ✓
