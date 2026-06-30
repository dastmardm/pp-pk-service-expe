# Technical Specification

## Sources
- `specs/product.md`
- `./docs/` concrete files read: `docs/README.md`, `docs/index.md`,
  `docs/agent-dag.png`, `docs/sme_stage_cases.csv`,
  `docs/00-overview/glossary.md`, `docs/00-overview/problem-statement.md`,
  `docs/01-current-system/legacy-architecture.md`,
  `docs/01-current-system/pain-points.md`,
  `docs/02-domain-inputs/csv-catalog.md`,
  `docs/02-domain-inputs/field-taxonomy.md`,
  `docs/02-domain-inputs/machine-query-schema.md`,
  `docs/03-proposed-design/architecture.md`,
  `docs/03-proposed-design/grounding-and-tool-calling.md`,
  `docs/03-proposed-design/misspelling-strategy.md`,
  `docs/03-proposed-design/stage-1-decomposition.md`,
  `docs/03-proposed-design/stage-2-subquery-translation.md`,
  `docs/03-proposed-design/stage-3-aggregation.md`,
  `docs/04-examples/worked-examples.md`,
  `docs/05-evaluation/gold-set-and-metrics.md`,
  `docs/06-implementation/build-status.md`,
  `docs/06-implementation/operations.md`,
  `docs/06-implementation/streamlit-ui.md`,
  `docs/06-implementation/tech-stack.md`.
- Existing code files read: `pyproject.toml`, `.env.example`,
  `.claude/settings.json`, `src/oppp/__init__.py`, `src/oppp/models.py`,
  `src/oppp/config.py`, `src/oppp/registry.py`, `src/oppp/llm.py`,
  `src/oppp/pipeline.py`, `src/oppp/execute.py`, `src/oppp/cli.py`,
  `src/oppp/dag.py`, `src/oppp/stages/expand.py`,
  `src/oppp/stages/enhance.py`, `src/oppp/stages/decompose.py`,
  `src/oppp/stages/translate.py`, `src/oppp/stages/aggregate.py`,
  `src/oppp/taxonomy/index.py`, `src/oppp/normalize/base.py`,
  `src/oppp/normalize/strategies.py`, `src/oppp/services/base.py`,
  `src/oppp/services/safety.py`, `src/oppp/services/pk.py`,
  `src/oppp/services/rtb.py`, `src/oppp/eval/harness.py`,
  `src/oppp/eval/per_step.py`, `src/oppp/eval/judge.py`,
  `src/oppp/ui/app.py`, `utils/build_sme_stage_cases.py`,
  `utils/fill_stage_cases_from_pipeline.py`, `utils/ppendium/__init__.py`,
  `utils/ppendium/prompts.py`.
- Existing tests read: `tests/test_pipeline.py`, `tests/test_stages.py`,
  `tests/test_eval.py`, `tests/test_per_step_eval.py`,
  `tests/test_normalize.py`, `tests/test_services.py`,
  `tests/test_taxonomy.py`.
- Existing planning artefacts read for conventions before regeneration:
  `specs/constitution.md`, `specs/requirements.md`, `specs/plan.md`,
  `specs/tasks.md`, `specs/skeleton.md`, `specs/evaluation.md`,
  `specs/git.md`.

## Architecture Overview
The system is a registry-backed local package with a staged data flow:

```text
raw query
  -> Stage -1 expand
  -> Stage 0 enhance
  -> Stage 1 decompose
  -> Stage 2A translate input closed-set filters
  -> Stage 3 aggregate first API query
  -> execute and fetch datapoints
  -> Stage 2B translate deferred open-set filters over runtime closed sets
  -> Stage 3 post-filter datapoints and return audit metadata
```

Existing code already implements Stage -1, Stage 0, Stage 1, Stage 2A, Stage 3
query assembly, count execution, zero-count open-filter probes, per-step
evaluation scaffolding, Safety/PK/RTB configs, CLI, and Streamlit UI. The
remaining technical delta is to materialize row-level execution and the runtime
closed-set post-filter pass while preserving the current count/probe behavior as
a fallback/compatibility path.

## Data Contracts
| Contract | Definition |
|----------|------------|
| `CONTRACT-EXPANDED-QUERY` | `ExpandedQuery{text, original, source}`. `original` is the exact user input; `text` is the faithful rewrite used downstream. |
| `CONTRACT-ENHANCED-QUERY` | `EnhancedQuery{text, annotations, source}` where each `EntityAnnotation` has `surface`, `label`, optional `entity_type`, and synonyms. |
| `CONTRACT-COMPONENT` | Stage-1 `Component{field, nl_fragment, type, reason, source, boolean_group?}`. `type` is exactly `filter` or `question`; filter components enter translation. |
| `CONTRACT-SUBQUERY` | Stage-2A `MachineSubquery{field, operator, value|pattern, boolean_group?, entity_name?, collapse_to?, grounding?, notes?, dropped}`. `dropped=true` excludes invalid closed-set filters from downstream query assembly. |
| `CONTRACT-MACHINE-QUERY` | Stage-3 request envelope `MachineQuery{query, entityFilters, facets, displayColumns, sortColumns, leafOnly}`. `query` has exactly one top-level operator when valid. |
| `CONTRACT-CLOSED-SET-TRANSLATION` | `translate_closed_set(field, pool, closed_set, context) -> selected subset`. The result is always a subset of `closed_set`; `[]` or `None` means invalid and has no downstream filtering effect. Resolution order is exact, fuzzy, LLM pool enrichment with exact/fuzzy retry, closed-set LLM selection, membership assertion/retry, then invalid. |
| `CONTRACT-GROUNDING` | `Grounding{matched:[GroundingHit], expanded_from?, confidence}` records the rows, class/term/runtime source, and confidence behind emitted values. |
| `CONTRACT-RUNTIME-CLOSED-SET` | For each deferred open-set filter field, collect sorted unique non-empty field values from fetched datapoints. That list is the `closed_set` for Stage 2B. |
| `CONTRACT-POST-FILTER` | Runtime translation output `{field, pool, runtime_closed_set, selected, valid, reason}`. Valid selections keep only datapoints whose field value is in `selected`; invalid selections leave datapoints unchanged and produce a warning. |
| `CONTRACT-EXECUTION-COUNT` | Count execution returns `{ok, count_total?, status?, error?}` from `data.countTotal`. |
| `CONTRACT-EXECUTION-ROWS` | Row execution returns `{ok, count_total?, datapoints:[dict], status?, error?, next_cursor?/page?}`. Pagination continues until all requested rows are collected or an API error occurs. |
| `CONTRACT-SERVICE-CONFIG` | `ServiceConfig` and `FieldSpec` define field buckets (`closed`, `open`, `enum`, `boolean`), taxonomies, emitted API fields, entity routing, display columns, facets, and service invariants. |
| `CONTRACT-GOLD-PERSTEP` | `docs/sme_stage_cases.csv` has `nl query, counts, termite, decompose, translate, aggregate, machine query`. |
| `CONTRACT-GOLD-PERFIELD` | `inputs/sme_expected_cases.csv` has one row per SME case plus per-field expected values and expected count `s`. |

## Schema
The durable schema is the Pydantic model set in `src/oppp/models.py`, the
dataclass service schema in `src/oppp/services/base.py`, the taxonomy CSV headers
under `inputs/`, and the two gold-set CSV shapes above.

Required model additions:
- Add row execution and runtime filtering models, or equivalent typed Pydantic
  contracts, for `CONTRACT-EXECUTION-ROWS`, `CONTRACT-RUNTIME-CLOSED-SET`, and
  `CONTRACT-POST-FILTER`.
- Extend `PipelineResult` with row execution and runtime post-filter metadata
  without breaking existing count-only callers.
- Keep `MachineSubquery.dropped` semantics for invalid input closed-set filters;
  add equivalent runtime invalid metadata for open-set filters.

## Component Interfaces
| Component | Interface |
|-----------|-----------|
| Expander | `expand(query, service) -> ExpandedQuery`; backends `llm`, `noop`. |
| Enhancer | `enhance(query, service) -> EnhancedQuery`; backends `termite`, `noop`. |
| Decomposer | `decompose(query, service) -> Decomposition`; production `llm` remains vocab-free, `gazetteer` remains an offline double. |
| Translator Stage 2A | `translate(component, service, normalizer, annotations) -> MachineSubquery | None` for input closed sets, enums, booleans, and current direct open-field fallback. |
| Translator Stage 2B | `translate_runtime(component, runtime_values, context) -> PostFilterResult` using `CONTRACT-CLOSED-SET-TRANSLATION`. It must not emit values outside the fetched runtime set. |
| Aggregator | `aggregate(decomp, subqueries, service) -> (MachineQuery, issues)` plus `apply_runtime_post_filters(datapoints, runtime_results) -> filtered_datapoints, issues`. |
| Execution | `execute_count(machine_query, service, timeout) -> ExecutionResult`; add `execute_rows(machine_query, service, limit/page_size/timeout) -> RowExecutionResult`. |
| Pipeline | `run_pipeline(...) -> PipelineResult`; when row execution is enabled, it defers open-set filters, fetches rows with valid input closed-set filters, derives runtime closed sets, translates open filters, and post-filters rows. |
| CLI | Expose current count/payload behavior and a row-fetch/post-filter mode without changing existing defaults unexpectedly. |
| UI | Show Stage -1 expansion, Stage 0 annotations, Stage 1 components, Stage 2A subqueries, Stage 3 query, row execution, Stage 2B runtime selections, and final filtered counts when available. |
| Evaluation | Score per-step outputs against `docs/sme_stage_cases.csv`; add coverage for runtime post-filter outcomes and resolved SME cases Q7, Q12, Q23, Q24, Q25. |

## Infrastructure
- Python 3.11+ package with `src/` layout and a Typer CLI.
- Local CSV taxonomies under `inputs/`; `OPPP_INPUTS_DIR` can override location.
- HTTP execution uses standard-library networking in the core.
- Optional extras remain lazy: LLM stack, UI, diagram rendering, and report export.
- No database, queue, container runtime, or migration system is required.

## Configuration and Secrets
- `OPPP_INPUTS_DIR` controls taxonomy/gold-set location.
- `PORTKEY_ENDPOINT`, `PORTKEY_API_KEY`, `PORTKEY_PROVIDER`, `TOOL_MODEL`, and
  `LLM_SEED` configure model-backed stages and the judge.
- `TERMITE_HOME`, `TERMITE_AUTH_URL`, `TERMITE_CLIENT_NAME`, and
  `TERMITE_CLIENT_SECRET` configure the optional TERMite enhancer.
- `.env.example` is keys-only; real `.env` files and credentials are never
  committed.
- Row fetching must reuse the existing service URLs and timeout pattern; if the
  API requires pagination parameters, keep them in execution-layer options rather
  than hard-coding them into stages.

## Technology Decisions
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language/package | Python 3.11+ with `pyproject.toml` | Matches existing code and documented local workflow. |
| Typed boundaries | Pydantic models | Replaces legacy free-text JSON scraping and supports per-stage validation. |
| Stage selection | Existing `Registry[T]` pattern | Keeps every backend selectable and testable by name. |
| Closed-set grounding | In-memory CSV indexes plus RapidFuzz and LLM fallback | Enforces "subset of closed set" while tolerating synonyms and misspellings. |
| Runtime open-set handling | Fetch rows, derive unique values, reuse closed-set translator, post-filter | Implements the documented open-set design without introducing a separate translation philosophy. |
| Service variation | `ServiceConfig`/`FieldSpec` data | Safety/PK/RTB differences remain config, not forked stage code. |
| HTTP | `urllib.request` in core | Preserves the no-extra core dependency rule. |
| Quality gates | `python3 -m compileall src/oppp`, `ruff check`, `ruff format --check`, `pytest -q` | Compile, lint, style, and hermetic tests cover the implementation delta. |
| UI | Streamlit | Existing inspection surface; extend rather than replace. |

## Open Questions
No product ambiguity remains. Two implementation details must be discovered while
implementing row fetch: the exact API pagination parameters for datapoint rows,
and the response key that contains row items for each service. If the live API
does not expose rows through the same endpoint, keep `execute_count` as the
fallback and report runtime post-filtering as unavailable for that run.
