# Technical Specification

## Sources
- `specs/product.md` (this run's product specification)
- `docs/README.md`, `docs/index.md`, `docs/00-overview/problem-statement.md`,
  `docs/00-overview/glossary.md`, `docs/02-domain-inputs/csv-catalog.md`,
  `docs/02-domain-inputs/field-taxonomy.md`, `docs/02-domain-inputs/machine-query-schema.md`,
  `docs/03-proposed-design/architecture.md`, `docs/03-proposed-design/stage-1-decomposition.md`,
  `docs/03-proposed-design/stage-2-subquery-translation.md`,
  `docs/03-proposed-design/stage-3-aggregation.md`,
  `docs/03-proposed-design/grounding-and-tool-calling.md`,
  `docs/03-proposed-design/misspelling-strategy.md`,
  `docs/04-examples/worked-examples.md`, `docs/05-evaluation/gold-set-and-metrics.md`,
  `docs/06-implementation/build-status.md`, `docs/06-implementation/operations.md`,
  `docs/06-implementation/streamlit-ui.md`, `docs/06-implementation/tech-stack.md`
- Existing implementation read: `pyproject.toml`, `src/oppp/__init__.py`,
  `src/oppp/config.py`, `src/oppp/llm.py`, `src/oppp/models.py`,
  `src/oppp/pipeline.py`, `src/oppp/execute.py`, `src/oppp/cli.py`,
  `src/oppp/dag.py`, `src/oppp/registry.py`,
  `src/oppp/stages/expand.py`, `src/oppp/stages/enhance.py`,
  `src/oppp/stages/decompose.py`, `src/oppp/stages/translate.py`,
  `src/oppp/stages/aggregate.py`, `src/oppp/normalize/base.py`,
  `src/oppp/normalize/strategies.py`, `src/oppp/taxonomy/index.py`,
  `src/oppp/services/base.py`, `src/oppp/services/pk.py`,
  `src/oppp/eval/harness.py`, `src/oppp/eval/per_step.py`,
  `src/oppp/eval/judge.py`, `src/oppp/eval/compare.py`, `src/oppp/ui/app.py`
- Existing tests read: `tests/test_pipeline.py`, `tests/test_stages.py`,
  `tests/test_eval.py`, `tests/test_per_step_eval.py`, `tests/test_normalize.py`,
  `tests/test_services.py`, `tests/test_taxonomy.py`
- Input schemas sampled: `inputs/drugs.csv`, `inputs/species.csv`, `inputs/route.csv`,
  `inputs/sources.csv`, `inputs/document_year.csv`, `inputs/enums.csv`,
  `inputs/fields.csv`, `inputs/query_criteria_fields.csv`

## Architecture Overview
The system is a Python package (`src/oppp/`) with a fixed staged data flow for converting PK natural-language questions into PharmaPendium API machine queries:

```text
NL query
  -> Stage -1: LLM expansion (preserves original)
  -> Stage 1:  LLM vocab-free decomposition into single-field components
  -> Stage 0:  required TERMite NER over per-field fragments (annotations + preferred labels)
  -> Stage 2A: input closed-set translation (CSV-backed fields, enums, booleans)
  -> Stage 3A: aggregate early-contributor subqueries, apply PK invariants, execute API query
  [row-level design]
  -> Stage 2B: runtime narrowing of large closed-set fields against early-contributor datapoints
  -> Stage 3B: assemble all contributor subqueries, execute final API query
  -> Stage 2C: open-set post-filtering against Stage 3B datapoint unique values
```

In v0.1, `execute.py` reads `countTotal` only; row fetch and runtime post-filtering are the intended row-level path. Open-set fields currently emit direct `MATCH`/`REGEX` constraints guarded by optional zero-count probes. The implementation delta is: add typed row execution, runtime closed-set derivation, and runtime translation/post-filter models; align service configs to PK-only active scope; update evaluation harness to load `docs/PPPK.xlsx`.

## Data Contracts

| Contract | Definition |
|----------|------------|
| `CONTRACT-EXPANDED-QUERY` | `ExpandedQuery{text, original, source}`. `original` is the exact user input; `text` is the Stage -1 faithful rewrite. Stage -1 failure is a reported configuration/execution error, never a silent passthrough. |
| `CONTRACT-ENHANCED-QUERY` | `EnhancedQuery{text, annotations, source}` where each `EntityAnnotation` has `surface`, `label`, optional `entity_type`, and `synonyms`. Source must record TERMite. An absent or empty annotation set from a no-op enhancer is not acceptable for full pipeline runs. |
| `CONTRACT-COMPONENT` | Stage-1 `Component{field, nl_fragment, type, reason, source, boolean_group?}`. `type` is exactly `filter` or `question`. Production decomposition is LLM-only and must not consult taxonomies. TERMite type mappings: `DRUG→drugs`, `SPECIES→species`, `ROUTE→route`, `PARAMETER→parameter`, `AGE→age`. |
| `CONTRACT-CLOSED-SET` | For input fields: the full valid value list from CSV taxonomies, inline enums, or boolean domains. For runtime fields: the sorted unique non-empty fetched datapoint values for that field. |
| `CONTRACT-CLOSED-SET-TRANSLATION` | `translate_closed_set(field, pool, closed_set, context) -> selected_subset`. Resolution order: (1) exact match, (2) fuzzy match, (3) LLM pool enrichment + exact/fuzzy retry, (4) LLM selection from closed set, (5) membership assertion/retry with feedback, (6) invalid. Result is always a subset of `closed_set`; `[]` or `None` means invalid. |
| `CONTRACT-SUBQUERY` | Stage-2A `MachineSubquery{field, operator, value\|pattern, boolean_group?, grounding?, dropped}`. `dropped=true` excludes invalid input closed-set filters from downstream assembly. Invalid translations with `dropped=true` are accumulated in `PipelineResult.issues`, which is the audit trail referenced in product documentation. |
| `CONTRACT-GROUNDING` | `Grounding{matched:[GroundingHit], expanded_from?, confidence}`. Each `GroundingHit` has `name`, `id?`, `parent_id?`, `parent_name?`, `score`, `match` (exact/fuzzy/termite/class/expand/llm/runtime/unmatched), `count?`. |
| `CONTRACT-MACHINE-QUERY` | Stage-3 request envelope `MachineQuery{query, entityFilters?, facets?, displayColumns?, sortColumns?, leafOnly?}`. `query` has exactly one top-level operator when valid. `entityFilters` is unused by PK in v0.1. |
| `CONTRACT-EXECUTION-COUNT` | `ExecutionResult{ok: bool, count_total?: int, status?: int, error?: str}`. `ok=true` when the API returned a valid response; `count_total` is absent only when the API response contains no count. Used for evaluation and debugging. |
| `CONTRACT-EXECUTION-ROWS` | `{ok, count_total?, datapoints:[dict], status?, error?, page_state?}`. Pagination continues to requested bound, all rows, or API error. `datapoints` is normalized flat record dicts keyed by service display field names. `page_state` is opaque execution metadata. |
| `CONTRACT-RUNTIME-CLOSED-SET` | For each deferred field: sorted unique non-empty values collected from fetched `datapoints[field]`. This is the closed set for Stage 2B/2C translation. |
| `CONTRACT-POST-FILTER` | `{field, pool, runtime_closed_set, selected, valid, reason}`. Valid selections keep only datapoints with `field` value in `selected`; invalid selections leave datapoints unchanged and emit a warning. |
| `CONTRACT-SERVICE-CONFIG` | `ServiceConfig` and `FieldSpec` define field buckets (`closed`/`open`/`enum`/`boolean`), `EARLY_CONTRIBUTOR_THRESHOLD` (default 500), backing taxonomy paths, emitted API fields, facet allow-list, service invariants (`concomitants`, `tissueSpecific`, `metabolitesEnantiomers`), and search URL. `EARLY_CONTRIBUTOR_THRESHOLD` is the maximum closed-set vocabulary size that qualifies a field for Stage 2A translation before the first API call; fields whose closed-set row count is at or above this threshold are deferred to Stage 2B runtime narrowing. The PK service defines exactly 16 fields: `drugs` (closed, drugs.csv), `species` (closed, species.csv), `routes` (closed, route.csv), `documentSource` (closed, sources.csv), `documentYear` (closed, document_year.csv), `sex` (enum: Male/Female/Both), `concomitants` (enum: Fed/Fasted), `tissueSpecific` (enum: Tissue-specific/Not tissue-specific), `metabolitesEnantiomers` (enum: Not metabolites/enantiomers/Metabolite/Enantiomer), `isPreclinical` (boolean), `parameter` (open), `parameterDisplay` (open), `studyGroup` (open), `age` (open), `dose` (open), `duration` (open). |
| `CONTRACT-GOLD-SET` | `docs/PPPK.xlsx` → `PK_Query` sheet. Columns: `Quety number`, `Query`, `Expected Count`. 47 rows. Read by `eval/harness.py` for count-based evaluation. |
| `CONTRACT-FIXED-STAGE-PATH` | Public pipeline (`run_pipeline`), CLI, Streamlit UI, and eval entry points expose service/execute/fetch controls but no stage implementation choices, normalizer selectors, or no-op bypasses. |
| `CONTRACT-NORMALIZER` | `normalize(fragment, field, bucket, context) -> {normalized, candidates?, changed, confidence, note?}`. Policy is fixed: `closed` → fuzzy closed-set correction; `open` → conservative surface cleanup; `drugs` → drug-specific normalizer. |

## Schema
The durable schema is:
- Pydantic models in `src/oppp/models.py`: `ExpandedQuery`, `EntityAnnotation`, `EnhancedQuery`, `Component`, `BooleanGroup`, `GroundingHit`, `Grounding`, `MachineSubquery`, `MachineQuery`, `PipelineResult`, `ExecutionResult`, `RowExecutionResult`, `RuntimeClosedSet`, `PostFilterResult`.
- Service dataclasses in `src/oppp/services/base.py`: `FieldSpec`, `ServiceConfig`.
- Taxonomy CSV headers under `inputs/` (five CSVs: `drugs`, `species`, `route`, `sources`, `document_year`, each with `name,id[,parent_id,parent_name][,count]`).
- Gold set schema: `docs/PPPK.xlsx` → `PK_Query` sheet (`Quety number`, `Query`, `Expected Count`).

Required model additions (not yet present in v0.1):
- `RowExecutionResult` with `ok`, `count_total`, `datapoints`, `status`, `error`, `page_state`.
- `RuntimeClosedSet` per field.
- `PostFilterResult` per open-set filter.
- Extend `PipelineResult` with `row_execution`, `runtime_closed_sets`, `runtime_translations`, `filtered_datapoints`, `final_filtered_count`.

## Component Interfaces

| Component | Interface |
|-----------|-----------|
| Expander | `expand_query(query: str, service: ServiceConfig) -> ExpandedQuery`. LLM-backed, preserves `original`, fails with issue when LLM unavailable. No `noop` product method. |
| TERMite enhancer | `enhance(query: str, service: ServiceConfig) -> EnhancedQuery`. Reads `TERMITE_*` settings lazily. Missing TERMite config/toolkit is a blocking configuration error for full runs. Runs over decomposed per-field fragments (after Stage 1). |
| Decomposer | `decompose(query: str, service: ServiceConfig, annotations: EnhancedQuery) -> Decomposition`. LLM structured output, seeded by TERMite annotations; no taxonomy lookup. Tests inject a fake LLM client. |
| Annotation reconciliation | `reconcile_with_annotations(decomp: Decomposition, service: ServiceConfig, annotations: EnhancedQuery) -> None`. Deterministic post-annotation pass: resolves routing ambiguities, promotes retrieval-defining PK parameters (`PARAMETER` type) from `question` to `filter`. |
| Normalizer | `normalize(fragment: str, field: str, bucket: str, context) -> NormalizationResult`. Fixed field/bucket policy (`closed`/`open`/`drugs`). Not a selectable option. |
| Translator Stage 2A | `translate_input_filter(component: Component, service: ServiceConfig, annotations) -> MachineSubquery | None`. Closed-set fields, enums, booleans use `CONTRACT-CLOSED-SET-TRANSLATION`. Open-set fields are deferred. |
| Translator Stage 2B | `translate_runtime_filter(component: Component, runtime_values: list[str], context) -> PostFilterResult`. Reuses `CONTRACT-CLOSED-SET-TRANSLATION` over the narrowed runtime list. |
| Aggregator Stage 3A | `aggregate_query(decomp, subqueries, service) -> (MachineQuery, issues)`. Boolean grouping, service invariants, facets, displayColumns, structural validation. |
| Aggregator Stage 3B | Same assembly rules as 3A but includes all resolved contributor subqueries. |
| Post-filter applier | `apply_post_filters(datapoints, post_filter_results) -> (filtered_datapoints, issues)`. Applies valid runtime `selected` subsets as row-level filters. |
| Execution (count) | `execute_count(machine_query: MachineQuery, service: ServiceConfig, timeout: int) -> ExecutionResult`. POSTs to `service.search_url`, reads `data.countTotal`. |
| Execution (rows) | `execute_rows(machine_query: MachineQuery, service: ServiceConfig, limit: int, page_size: int, timeout: int) -> RowExecutionResult`. Paginates through the API until `limit`, all rows, or error. |
| Pipeline | `run_pipeline(query: str, service: str, *, fetch_rows=False, row_limit=None, execute=True, probe_open_filters=False) -> PipelineResult`. Fixed stage order; no stage method parameters. |
| CLI | `oppp run/enhance/decompose/field/aggregate/lookup/eval/dag/services`. No `--enhancer`, `--decomposer`, `--translator`, `--aggregator`, `--normalizer`, or method selection flags. |
| Streamlit UI | Shows Stage -1 through Stage 3, execution, runtime closed sets, runtime selections, filtered count. No stage backend selectors. |
| Evaluation harness | Loads `docs/PPPK.xlsx` (`PK_Query` sheet), runs each query, compares `countTotal` to `Expected Count`. Per-step comparators score Stage 0 labels, Stage 1 routing/type, Stage 2 field names, Stage 3 query structure. |
| LLM-as-judge | `LLMJudge.judge(step, input, expected, actual) -> JudgeVerdict{match|partial|miss, reason}`. Invoked only for free-text steps (Stage 1 fragments, Stage 2 runtime open-set selections, Stage 3 structural tie-breaks). Tests inject a fake client. |

## Infrastructure
- Python 3.11+ package with `src/` layout; `uv` or `pip` install; `pyproject.toml` with hatchling build backend.
- Local taxonomy CSVs under `inputs/`; `OPPP_INPUTS_DIR` env var overrides location.
- Gold evaluation workbook at `docs/PPPK.xlsx`.
- Core HTTP uses `urllib.request`; no mandatory third-party HTTP dependency.
- LLM, TERMite, UI (`streamlit`), DAG rendering (`matplotlib`), and report export (`openpyxl`) are lazy imports gated by extras.
- No database, queue, container runtime, or migration system.
- `docs/agent-dag.drawio` is the editable diagram source; `docs/agent-dag.png` is the exported PNG.

## Configuration and Secrets

| Variable | Purpose | Required for |
|----------|---------|--------------|
| `OPPP_INPUTS_DIR` | Override default `inputs/` directory | Custom data location |
| `PORTKEY_ENDPOINT` | Portkey/OpenAI-compatible base URL | LLM-backed stages, judge |
| `PORTKEY_API_KEY` | API key for the LLM endpoint | Same |
| `PORTKEY_PROVIDER` | Provider prefix for LangChain model name | Same |
| `TOOL_MODEL` | Default model suffix for `oppp.llm.get_chat_model()` | Same |
| `LLM_SEED` | Optional decoding seed (defaults to 7) | Reproducible LLM calls |
| `TERMITE_HOME` | TERMite service URL | Required Stage 0 enhancer |
| `TERMITE_AUTH_URL` | TERMite OAuth token URL | Required Stage 0 enhancer |
| `TERMITE_CLIENT_NAME` | TERMite OAuth client name | Required Stage 0 enhancer |
| `TERMITE_CLIENT_SECRET` | TERMite OAuth client secret | Required Stage 0 enhancer |

`.env.example` is keys-only and identifies which settings are required for full runs. Real `.env` files and credential files are never committed. `load_dotenv_if_present()` reads `.env` lazily when needed.

## Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python 3.11+ | Matches existing codebase |
| Typed boundaries | Pydantic v2 | Validated contracts at every stage boundary |
| Stage orchestration | Fixed Python calls in `pipeline.py` | No runtime stage selection; satisfies the fixed-path product requirement |
| Entity recognition | SciBite TERMite at Stage 0 | Required source of preferred labels, entity types, and synonyms |
| LLM calls | `oppp.llm` factory with LangChain structured output | Consistent model config and seed across all LLM-backed stages |
| Closed-set grounding | CSV indexes + RapidFuzz + LLM enrichment/selection | Enforces subset-of-closed-set output while tolerating synonyms and misspellings |
| Normalization | Fixed field/bucket policy in `normalize/` | Deterministic correction behavior, not a runtime experiment |
| Runtime open-set handling | Fetch rows, derive unique values, reuse closed-set translator, post-filter rows | Implements the documented open-set design with the same grounding contract |
| Service variation | `ServiceConfig`/`FieldSpec` dataclasses | Keeps PK (and future service) differences out of shared stage logic |
| HTTP | `urllib.request` in core | Preserves the no-extra-dependency rule for core execution |
| CLI | Typer | Existing command surface; testable option parsing |
| UI | Streamlit (lazy `ui` extra) | Existing debug surface |
| Reports | openpyxl (lazy `report` extra) | XLSX report export for `oppp eval --output` |
| Diagram | draw.io XML + PNG | `docs/agent-dag.drawio` as editable source of truth |
| Quality gates | `python3 -m compileall src/oppp`, `ruff check src tests`, `ruff format --check src tests`, `pytest -q` | Compile, lint, style, and hermetic tests |
| Gold set | `docs/PPPK.xlsx` → `PK_Query` sheet (47 PK questions + expected counts) | The SME evaluation reference; read by `eval/harness.py` via openpyxl |

## Open Questions
None. The only open implementation detail is discovering the PharmaPendium API's exact pagination parameters and row response key for `execute_rows`; if rows are unavailable, `RowExecutionResult` returns `ok=false` with a structured issue and the pipeline falls back to count-only mode.
