# Implementation Plan

## Summary
Implement the row-level runtime closed-set path described in the docs while
preserving the existing count-only pipeline. The work adds typed row/post-filter
contracts, row execution, Stage 2B runtime translation, Stage 3 post-filtering,
pipeline/CLI/UI exposure, and regression/evaluation coverage for the clarified
SME cases.

## Work Breakdown
The WBS in `specs/tasks.md` is cut into three subtrees:
- **W1.1 Contracts, execution, and filtering.** Owns the core data contracts,
  row API execution, runtime translation entry point, and post-filter application.
- **W1.2 Orchestration and user surfaces.** Wires the new two-pass flow into the
  pipeline and exposes it through CLI and UI without breaking current count-only
  workflows.
- **W1.3 Evaluation and tests.** Extends per-step/count evaluation and adds
  regression coverage for the resolved SME rows and runtime post-filter behavior.

This cut keeps ownership disjoint and lets implementation proceed in dependency
waves: W1.1 defines the runtime interfaces, W1.2 consumes them, W1.3 verifies the
integrated behavior.

## Execution Model
Leaves run when their declared dependencies are satisfied. Summary nodes wait for
children, run their review assertion, and report upward. Parallel execution is
safe because each file has exactly one WBS owner and the union of owner file lists
matches `specs/skeleton.md`. Sequential bottom-up execution is equivalent.

## Key Decisions
| Decision | Options considered | Choice | Rationale |
|----------|--------------------|--------|-----------|
| Open-set implementation | Keep direct MATCH/REGEX only; add row-runtime pass | Add row-runtime pass and retain probes as fallback | Matches docs and keeps v0.1 behavior available. |
| Translator reuse | Separate open-field matcher; reuse closed-set contract | Reuse closed-set contract for runtime values | Ensures open-set output is still a subset of a known set. |
| Execution shape | Replace count execution; add row execution beside it | Add `execute_rows` beside `execute_count` | Existing eval/count workflows remain stable. |
| Metadata | Only return filtered rows; return rows plus audit metadata | Return audit metadata | Users need to know which runtime filters were invalid or applied. |
| Testing | Live API integration; mocked row responses | Mocked row responses in default suite | Keeps tests hermetic and deterministic. |

## Risks and Mitigations
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| API row response shape differs by service | Medium | High | Keep parsing in `execute.py`; return structured errors and preserve count fallback. |
| Row fetches are too large for dev workflows | Medium | Medium | Add bounded fetch options and defaults suitable for debugging. |
| Runtime translation accidentally filters on out-of-set values | Low | High | Reuse closed-set membership assertion and test invalid runtime outputs. |
| Existing count eval changes unexpectedly | Medium | Medium | Preserve count-only defaults and add regression tests around `oppp eval --no-execute`. |
| UI becomes cluttered | Medium | Low | Add compact runtime panels only when row mode is enabled or results exist. |

## Constitution Check
- CONST-1 and CONST-2 are directly implemented by runtime closed-set contracts.
- CONST-3 remains intact: Stage 1 still routes only.
- CONST-4 and CONST-5 are preserved by typed row/post-filter metadata and explicit
  boolean grouping.
- CONST-6 is preserved by reusing translation/grounding helpers.
- CONST-7 is preserved by keeping service differences in config.
- CONST-8 is preserved by mocking row execution in tests and keeping offline
  defaults.
- CONST-9 is preserved by extending per-step/evaluation coverage.
- CONST-10 and CONST-11 are covered by existing lazy settings and the quality
  gates.
