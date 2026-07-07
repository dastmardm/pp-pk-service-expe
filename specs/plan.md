# Implementation Plan

## Summary
Align the package with the documented fixed pipeline: required TERMite, no public
stage/normalizer method options, fixed normalization policy, row-level runtime
closed-set translation, and post-filtering. The work keeps stage inspection and
count evaluation, but those surfaces run fixed methods and tests stay hermetic
through injected fakes rather than product bypasses.

## Work Breakdown
The WBS in `specs/tasks.md` is cut into five subtrees:
- **W1.1 Contracts and configuration.** Owns runtime models, required credential
  settings, env-template wording, and the fixed normalizer API.
- **W1.2 Service and registry boundaries.** Keeps services configurable while
  preventing the generic registry pattern from implying selectable stage methods.
- **W1.3 Fixed stages, execution, and filtering.** Owns expansion, TERMite,
  decomposition, translation, aggregation/post-filtering, and row execution.
- **W1.4 Orchestration and user surfaces.** Wires the fixed path into pipeline,
  CLI, UI, and diagram export.
- **W1.5 Evaluation and tests.** Updates scoring, fakes, and regressions so the
  fixed path is verifiable without network or credentials.

This cut keeps file ownership disjoint. The summary-level order follows the
interfaces: contracts/config first, service boundaries second, stages third,
surfaces fourth, evaluation/tests last.

## Execution Model
Leaves run when their declared dependencies are satisfied. Summary nodes wait for
children, run their review assertion, and report upward. Parallel execution is
safe because each file has exactly one WBS owner and the union of owner file
lists matches `specs/skeleton.md`. A sequential bottom-up walk is equivalent.

## Key Decisions
| Decision | Options considered | Choice | Rationale |
|----------|--------------------|--------|-----------|
| Stage method surface | Keep registries/options; fix defaults; remove public method choices | Remove public stage/normalizer choices and no-op product methods | The docs state the path is fixed and TERMite is mandatory. |
| TERMite failure | Continue with empty annotations; fail clearly | Fail clearly for full/stage runs | A silent empty enhancement hides a required dependency. |
| Test strategy | Keep `noop`/gazetteer/deterministic as product backends; inject fakes privately | Inject fakes through fixtures/monkeypatching | Maintains hermetic tests without leaking bypasses into product behavior. |
| Open-set implementation | Keep direct MATCH/REGEX probes; add row-runtime pass | Add row-runtime pass and retain count-only as evaluation/debug mode | Runtime closed sets are the documented product design. |
| Translator reuse | Separate open-field matcher; reuse closed-set contract | Reuse closed-set contract for runtime values | Ensures every emitted value is a subset of a known set. |
| Execution shape | Replace count execution; add row execution beside it | Keep `execute_count`, add `execute_rows` | Count metrics remain useful while row mode enables post-filtering. |
| Diagram behavior | Keep registry-derived PNG; use draw.io source | Align `oppp dag`/PNG with `docs/agent-dag.drawio` | The diagram must reflect docs, not live backend registries. |

## Risks and Mitigations
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Removing public test doubles breaks many tests | High | Medium | Add shared fake clients/fixtures before changing stage signatures. |
| API row response shape differs by service | Medium | High | Keep parsing in `execute.py`; return structured unavailable/error results and preserve count-only metrics. |
| Runtime translation accidentally filters on out-of-set values | Low | High | Reuse closed-set membership assertion and test invalid runtime outputs. |
| CLI/UI users lose familiar debugging knobs | Medium | Medium | Keep isolated fixed-stage commands and richer trace output. |
| TERMite dependency blocks local smoke runs | Medium | Medium | Keep imports lazy and provide fake TERMite fixtures for tests; production runs fail with actionable config errors. |
| Diagram export drifts from draw.io source | Medium | Low | Make code read or mirror the draw.io-backed fixed flow and test for absence of pluggable legends. |

## Constitution Check
- CONST-1 and CONST-2 drive the no-options and required TERMite implementation
  tasks.
- CONST-3 and CONST-4 are implemented by closed-set and runtime closed-set
  contracts.
- CONST-5 remains intact: Stage 1 routes only.
- CONST-6 and CONST-7 are preserved by typed row/post-filter metadata and
  explicit boolean grouping.
- CONST-8 is implemented by replacing normalizer options with a fixed policy.
- CONST-9 is preserved by shared hierarchy/runtime grounding helpers.
- CONST-10 is preserved by service config ownership.
- CONST-11 is preserved by test fakes rather than public bypasses.
- CONST-12 is preserved by extending per-step and per-field evaluation.
- CONST-13 and CONST-14 are covered by lazy config, secret rules, and quality
  gates.
