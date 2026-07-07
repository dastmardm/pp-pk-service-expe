# Technical Specification

## Sources
- `specs/product.md`
- `./docs/` files read: `docs/README.md`, `docs/index.md`,
  `docs/agent-dag.drawio`, `docs/agent-dag.png`,
  `docs/sme_stage_cases.csv`, `docs/00-overview/glossary.md`,
  `docs/00-overview/problem-statement.md`,
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
- Existing implementation context read: `pyproject.toml`, `.env.example`,
  `.gitignore`, `.claude/settings.json`, `src/oppp/__init__.py`,
  `src/oppp/registry.py`, `src/oppp/config.py`, `src/oppp/llm.py`,
  `src/oppp/models.py`, `src/oppp/pipeline.py`, `src/oppp/execute.py`,
  `src/oppp/cli.py`, `src/oppp/dag.py`, `src/oppp/stages/__init__.py`,
  `src/oppp/stages/expand.py`, `src/oppp/stages/enhance.py`,
  `src/oppp/stages/decompose.py`, `src/oppp/stages/translate.py`,
  `src/oppp/stages/aggregate.py`, `src/oppp/normalize/__init__.py`,
  `src/oppp/normalize/base.py`, `src/oppp/normalize/strategies.py`,
  `src/oppp/taxonomy/index.py`, `src/oppp/services/__init__.py`,
  `src/oppp/services/base.py`, `src/oppp/services/safety.py`,
  `src/oppp/services/pk.py`, `src/oppp/services/rtb.py`,
  `src/oppp/eval/__init__.py`, `src/oppp/eval/compare.py`,
  `src/oppp/eval/harness.py`, `src/oppp/eval/judge.py`,
  `src/oppp/eval/per_step.py`, `src/oppp/ui/app.py`.
- Existing tests read: `tests/test_pipeline.py`, `tests/test_stages.py`,
  `tests/test_eval.py`, `tests/test_per_step_eval.py`,
  `tests/test_normalize.py`, `tests/test_services.py`,
  `tests/test_taxonomy.py`.
- Input schemas sampled/read: `inputs/document_year.csv`,
  `inputs/dose_type.csv`, `inputs/drugs.csv`, `inputs/effects.csv`,
  `inputs/enums.csv`, `inputs/fields.csv`, `inputs/indications.csv`,
  `inputs/query_criteria_fields.csv`, `inputs/route.csv`,
  `inputs/sme_expected_cases.csv`, `inputs/sources.csv`,
  `inputs/species.csv`, `inputs/toxicity_parameters.csv`.
- Existing planning artefacts read before regeneration:
  `specs/constitution.md`, `specs/requirements.md`, `specs/plan.md`,
  `specs/tasks.md`, `specs/skeleton.md`, `specs/evaluation.md`,
  `specs/git.md`.

## Architecture Overview
The system is a Python package with a fixed staged data flow:

```text
raw query
  -> Stage -1 LLM expansion
  -> Stage 0 required TERMite enhancement
  -> Stage 1 LLM vocab-free decomposition
  -> Stage 2A closed-set translation for input-known fields
  -> Stage 3 aggregation and first API query
  -> row execution and runtime closed-set derivation
  -> Stage 2B closed-set translation for runtime-known fields
  -> Stage 3 runtime post-filtering and final result
```

The current code already has typed stage models, service configs, taxonomy
indexes, translation/aggregation logic, count execution, evaluation scaffolding,
CLI, and Streamlit UI. The implementation delta is to align that code with the
documented product path:

- remove user-selectable stage methods and normalizer choices;
- remove or confine `noop`, `gazetteer`, and `deterministic` as product backends;
- make TERMite Stage 0 mandatory for full pipeline and stage inspection;
- keep tests hermetic through injected fakes, fixtures, and monkeypatching rather
  than exposed product methods;
- implement row execution, runtime closed-set derivation, runtime translation,
  and post-filtering;
- update CLI/UI/evaluation/diagram code so they no longer advertise pluggable
  stage backends.

## Data Contracts
| Contract | Definition |
|----------|------------|
| `CONTRACT-EXPANDED-QUERY` | `ExpandedQuery{text, original, source}`. `original` is the exact user input; `text` is the faithful Stage -1 rewrite. Stage -1 failure is a reported configuration/execution failure, not a silent pass-through. |
| `CONTRACT-ENHANCED-QUERY` | `EnhancedQuery{text, annotations, source}` where `source` is TERMite and every `EntityAnnotation` has `surface`, `label`, optional `entity_type`, and `synonyms`. A full pipeline run cannot continue with an empty no-op enhancer substitute. |
| `CONTRACT-COMPONENT` | Stage-1 `Component{field, nl_fragment, type, reason, source, boolean_group?}`. `type` is exactly `filter` or `question`; production decomposition is LLM segmentation seeded by TERMite annotations and must not consult taxonomies. |
| `CONTRACT-CLOSED-SET` | For input fields, the closed set is the full valid value list from CSV taxonomies, inline enums, or boolean domains. For runtime fields, it is the unique non-empty fetched datapoint values for that field. |
| `CONTRACT-CLOSED-SET-TRANSLATION` | `translate_closed_set(field, pool, closed_set, context) -> selected subset`. Resolution order is exact match, fuzzy match, LLM pool enrichment with exact/fuzzy retry, LLM selection from the closed set, membership assertion/retry with feedback, then invalid. The result is always a subset of `closed_set`; `[]` or `None` means invalid. |
| `CONTRACT-SUBQUERY` | Stage-2A `MachineSubquery{field, operator, value|pattern, boolean_group?, entity_name?, collapse_to?, grounding?, notes?, dropped}`. `dropped=true` excludes invalid input closed-set filters from downstream query assembly. |
| `CONTRACT-GROUNDING` | `Grounding{matched:[GroundingHit], expanded_from?, confidence}` records matched rows, class/term/runtime source, and confidence behind emitted values. |
| `CONTRACT-MACHINE-QUERY` | Stage-3 request envelope `MachineQuery{query, entityFilters, facets, displayColumns, sortColumns, leafOnly}`. `query` has exactly one top-level operator when valid. |
| `CONTRACT-EXECUTION-COUNT` | Count execution returns `{ok, count_total?, status?, error?}` from `data.countTotal`. This remains an evaluation/debug signal. |
| `CONTRACT-EXECUTION-ROWS` | Row execution returns `{ok, count_total?, datapoints:[dict], status?, error?, page_state?}`. Pagination continues until the requested bound, all rows, or an API error. |
| `CONTRACT-RUNTIME-CLOSED-SET` | For each deferred open-set filter field, collect sorted unique non-empty field values from fetched datapoints. That list is the closed set for Stage 2B. |
| `CONTRACT-POST-FILTER` | Runtime translation output `{field, pool, runtime_closed_set, selected, valid, reason}`. Valid selections keep only datapoints whose field value is in `selected`; invalid selections leave datapoints unchanged and produce a warning. |
| `CONTRACT-SERVICE-CONFIG` | `ServiceConfig` and `FieldSpec` define field buckets (`closed`, `open`, `enum`, `boolean`), taxonomies, emitted API fields, entity routing, display columns, facets, invariants, and service output serialization. |
| `CONTRACT-GOLD-PERSTEP` | `docs/sme_stage_cases.csv` has `nl query, counts, termite, decompose, translate, aggregate, machine query`. |
| `CONTRACT-GOLD-PERFIELD` | `inputs/sme_expected_cases.csv` has one row per SME case plus per-field expected values and expected count `s`. |
| `CONTRACT-FIXED-STAGE-PATH` | Public pipeline, CLI, UI, and evaluation entry points expose service/execute/fetch controls but do not expose stage implementation choices, normalizer choices, or no-op bypasses. |

## Schema
The durable schema is the Pydantic model set in `src/oppp/models.py`, the
dataclass service schema in `src/oppp/services/base.py`, the taxonomy CSV headers
under `inputs/`, and the two gold-set CSV shapes.

Required model and schema changes:
- Add typed row execution, runtime closed-set, and post-filter result models for
  `CONTRACT-EXECUTION-ROWS`, `CONTRACT-RUNTIME-CLOSED-SET`, and
  `CONTRACT-POST-FILTER`.
- Extend `PipelineResult` with row execution, runtime closed sets, runtime
  translations, filtered datapoints, and final filtered count.
- Preserve `MachineSubquery.dropped` for invalid input closed-set filters.
- Add equivalent runtime invalid metadata for open-set post-filter failures.
- Keep TERMite annotations explicit on `EnhancedQuery`; do not use absence of
  annotations as an acceptable no-op enhancer result for full pipeline execution.
- Represent fixed method identity in `source` fields for audit, not as user
  selectable backend names.

## Component Interfaces
| Component | Interface |
|-----------|-----------|
| Expander | `expand_query(query, service) -> ExpandedQuery`. Uses the configured LLM and fails with a clear issue when unavailable; no `noop` product method. |
| TERMite enhancer | `enhance_with_termite(query, service) -> EnhancedQuery`. Reads TERMite settings lazily at invocation, calls SciBite TERMite, and returns annotations plus a hints block. Missing TERMite config/dependency is a blocking configuration error for full runs. |
| Decomposer | `decompose_query(enhanced_query, service) -> Decomposition`. Uses the configured LLM, stays vocab-free, and receives TERMite hints/annotations. Tests may inject a fake structured model, but no public gazetteer method is selectable. |
| Annotation reconciliation | `reconcile_with_annotations(decomp, service, annotations) -> None`. Deterministically handles target mechanism routing and retrieval-defining tox parameters using TERMite annotations. |
| Normalizer | `normalize_fragment(fragment, field, bucket) -> NormalizationResult`. The policy is fixed: fuzzy closed-set normalization, conservative open-set cleanup, and no selectable normalizer registry. |
| Translator Stage 2A | `translate_input_filter(component, service, annotations) -> MachineSubquery | None`. Input closed-set fields, enums, and booleans use `CONTRACT-CLOSED-SET-TRANSLATION`; open-set filters are deferred for row mode instead of emitted as hard free-text constraints. |
| Translator Stage 2B | `translate_runtime_filter(component, runtime_values, context) -> PostFilterResult`. Reuses `CONTRACT-CLOSED-SET-TRANSLATION` and never emits values outside the fetched runtime set. |
| Aggregator | `aggregate_first_query(decomp, subqueries, service) -> (MachineQuery, issues)` and `apply_runtime_post_filters(datapoints, runtime_results) -> filtered_datapoints, issues`. Aggregation uses LLM planning plus deterministic rendering/validation; no user-selectable deterministic backend. |
| Execution | `execute_count(machine_query, service, timeout) -> ExecutionResult`; `execute_rows(machine_query, service, limit, page_size, timeout) -> RowExecutionResult`. Row parsing and pagination stay in `execute.py`. |
| Pipeline | `run_pipeline(query, service, *, fetch_rows=False, row_limit=None, execute=True) -> PipelineResult`. It always follows the fixed stage path; execution controls may skip external API calls, but stage methods are not parameters. |
| CLI | `oppp run`, fixed isolated stage commands, `oppp eval`, and `oppp dag` expose only service/input/execution/output options. They must not expose `--enhancer`, `--decomposer`, `--translator`, `--aggregator`, `--normalizer`, or equivalent method selection. |
| UI | Streamlit shows the same fixed path and may toggle execution/row bounds. It must not show stage backend or normalizer selectors. |
| Evaluation | Scores per-step outputs, per-field gold values, final machine-query structure, count proximity, row/runtime post-filter behavior, and required regressions. It uses injected fakes for hermetic tests rather than no-op product methods. |

## Infrastructure
- Python 3.11+ package with `src/` layout and a Typer CLI.
- Local CSV taxonomies under `inputs/`; `OPPP_INPUTS_DIR` can override location.
- Core HTTP execution uses `urllib.request`.
- LLM, TERMite, UI, diagram rendering, and report export dependencies remain
  lazily imported so core imports do not require credentials or heavy extras.
- Full production runs require model settings and TERMite settings at invocation.
- No database, queue, container runtime, or migration system is required.
- `docs/agent-dag.drawio` is the editable diagram source; any generated PNG or
  CLI diagram export must reflect the fixed path rather than live stage registries.

## Configuration and Secrets
- `OPPP_INPUTS_DIR` controls taxonomy/gold-set location.
- `PORTKEY_ENDPOINT`, `PORTKEY_API_KEY`, `PORTKEY_PROVIDER`, `TOOL_MODEL`, and
  `LLM_SEED` configure the LLM-backed stages and judge.
- `TERMITE_HOME`, `TERMITE_AUTH_URL`, `TERMITE_CLIENT_NAME`, and
  `TERMITE_CLIENT_SECRET` configure required Stage 0 TERMite invocation.
- `.env.example` is keys-only and must identify which settings are required for
  full runs. Real `.env` files and credentials are never committed.
- Row fetching reuses service URLs and timeout patterns. API pagination
  parameters and row item response keys stay in the execution layer.

## Technology Decisions
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language/package | Python 3.11+ with `pyproject.toml` and hatchling | Matches existing package layout and workflow. |
| Typed boundaries | Pydantic models plus service dataclasses | Gives every stage and execution result a validated contract. |
| Stage orchestration | Fixed Python calls in `pipeline.py` | Satisfies the no-options product path and avoids silent method drift. |
| Entity recognition | SciBite TERMite at Stage 0 | Required source of entity labels, types, and synonyms before decomposition. |
| LLM calls | Central `oppp.llm` structured-output factory | Keeps model configuration, seed, and provider wiring consistent. |
| Closed-set grounding | CSV indexes plus RapidFuzz plus LLM enrichment/selection | Enforces subset-of-closed-set output while tolerating synonyms and misspellings. |
| Normalization | Fixed field/bucket policy | Implements the docs' normalizer behavior without a separate stage choice. |
| Runtime open-set handling | Fetch rows, derive unique values, reuse closed-set translator, post-filter | Implements the documented open-set design with the same grounding contract. |
| Service variation | `ServiceConfig`/`FieldSpec` data | Keeps Safety/PK/RTB differences out of shared stage logic. |
| HTTP | `urllib.request` in core | Preserves the no-extra core dependency rule. |
| CLI | Typer | Existing command surface and testable option parsing. |
| UI | Streamlit | Existing debug surface; extend rather than replace. |
| Diagram source | draw.io XML plus generated PNG | Matches the documentation source-of-truth for the flow diagram. |
| Quality gates | `python3 -m compileall src/oppp`, `ruff check src tests`, `ruff format --check src tests`, `pytest -q` | Compile, lint, style, and hermetic tests cover the implementation delta. |

## Open Questions
No product ambiguity remains. Two implementation details must be discovered while
implementing row fetch: the exact API pagination parameters for datapoint rows,
and the response key that contains row items for each service. If the live API
does not expose rows through the same endpoint, `execute_rows` must return a
typed unavailable result and the pipeline must report that runtime post-filtering
could not run for that execution.
