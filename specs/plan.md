# Implementation Plan

## Summary

Implement the documented PK staged count pipeline inside the existing `oppp` package boundaries. The work replaces the older linear enhance-before-decompose flow with expansion, decomposition, field-scoped TERMite enrichment, early small-closed translation, strict `1000` count gating, row filtering or staged non-early translation, and a shared `final_row_count` result used by CLI, UI, and evaluation.

## Work Breakdown

The WBS is cut along ownership boundaries that already exist in the codebase:

| Subtree | Responsibility | Rationale |
| --- | --- | --- |
| `W1.1` | Contracts and PK field metadata | The rest of the work depends on the result model, bucket names, threshold, and documented field spelling. |
| `W1.2` | Stage behavior | Decomposition, field-scoped TERMite, staged translation, and aggregation can be updated after contracts are stable. |
| `W1.3` | Orchestration and execution | Pipeline control flow and API count/row execution converge the stage interfaces. |
| `W1.4` | Public surfaces and evaluation | CLI, UI, and workbook evaluation consume the completed pipeline result contract. |
| `W1.5` | Tests | Test updates cover service metadata, stage behavior, orchestration, evaluation, and boundary counts. |

`src/oppp/pipeline.py` is the main convergent integration file and is owned by a single orchestration leaf to avoid parallel edits to the same control flow. Public surfaces are separated from the orchestrator so they can consume the final interface without owning stage internals.

## Execution Model

The WBS is a fork-join tree. Leaves may run concurrently only inside a dependency wave when their `Owns` lists are disjoint and their `After` constraints are satisfied. Summary nodes wait for children, review the subtree interfaces, and report upward. The root resolves after all children and the quality gates complete.

The same tree can also be walked sequentially from leaves upward. Concurrency is an optimization; correctness comes from the file-ownership invariant in `specs/skeleton.md` and `specs/tasks.md`.

## Key Decisions

| Decision | Options considered | Choice | Rationale |
| --- | --- | --- | --- |
| Pipeline location | New PK runner, existing `pipeline.py`, CLI-only orchestration | Existing `src/oppp/pipeline.py` | Keeps one production path for CLI, UI, and evaluation. |
| Early field representation | Derive ad hoc in translation, add `small_closed` bucket, keep all fields as `closed` | Add `small_closed` bucket | Makes early eligibility auditable in service metadata. |
| Threshold source | Inline constants, env var, service constant | Single constant `EARLY_CONTRIBUTOR_THRESHOLD = 1000` | Matches docs and allows focused tests for `999`, `1000`, and `1001`. |
| TERMite order | Global pre-decomposition enhancement, field-scoped post-decomposition enrichment | Field-scoped post-decomposition enrichment | Matches the product contract and prevents wrong-field annotation binding. |
| Evaluation metric | Tolerance band, per-step score, exact final row count | Exact `final_row_count == Expected Count` | Matches the only documented scored assertion. |
| `studyGroup` spelling | Keep singular, rename to plural only, support alias | Use documented `studyGroups` and allow compatibility alias where needed | Aligns outputs with docs while avoiding brittle input breakage. |

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Existing tests encode the old `500` threshold and singular `studyGroup` field | High | Tests fail for the intended behavior | Update tests under the WBS test leaves to assert the new docs-derived behavior. |
| Field-scoped TERMite API differs from the current global enhancer API | Medium | Enrichment can be wired incorrectly | Add a narrow component-level enrichment interface and keep the old global method only for compatibility/debug use. |
| Row filtering can silently skip unsupported fields | Medium | `final_row_count` can be wrong | Row filter results must record applied filters and warnings/errors for unsupported filters. |
| Staged aggregation can drift from payload validation | Medium | API calls can use invalid field leaves | Keep aggregation, validation, and `MachineQuery.to_payload()` tests together around the same normalized payload shape. |
| Evaluation accidentally keeps tolerance or per-step score fields | High | The harness reports success on the wrong metric | Replace summary and report columns with exact count-only fields and tests that reject tolerance as a scored metric. |
| Live API/TERMite/LLM credentials are unavailable in local development | High | CI or local tests become blocked | Keep default tests offline with fakes and lazy credential reads. |

## Constitution Check

No principle in `specs/constitution.md` is intentionally violated.

| Principle | Status | Notes |
| --- | --- | --- |
| `CONST-1` | Satisfied | This plan implements docs-derived behavior from `docs/`. |
| `CONST-2` | Satisfied | The WBS follows the fixed staged PK order. |
| `CONST-3` | Satisfied | Field buckets and threshold are contract/metadata work in `W1.1`. |
| `CONST-4` | Satisfied | Decomposition and field-scoped TERMite are separated in `W1.2`. |
| `CONST-5` | Satisfied | Staged translation and repeatable aggregation are explicit tasks. |
| `CONST-6` | Satisfied | Boundary-count behavior is covered by orchestration and tests. |
| `CONST-7` | Satisfied | `final_row_count` is the shared public result contract. |
| `CONST-8` | Satisfied | Evaluation scope is limited to `PK_Query` exact counts. |
| `CONST-9` | Satisfied | Typed contracts are updated before orchestration. |
| `CONST-10` | Satisfied | Tests and imports remain offline/lazy. |
| `CONST-11` | Satisfied | Runtime observability fields are part of the model contract. |
| `CONST-12` | Satisfied | The plan preserves the required quality gates. |
