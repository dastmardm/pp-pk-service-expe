# Technical Specification

## Sources

- `specs/product.md`
- `docs/README.md`
- `docs/domain.md`
- `docs/evaluation.md`
- `docs/examples.md`
- `docs/implementation.md`
- `docs/index.md`
- `docs/pipeline.md`
- `docs/agent-dag.drawio`
- `docs/PPPK.xlsx`
- `pyproject.toml`
- `src/oppp/models.py`
- `src/oppp/pipeline.py`
- `src/oppp/execute.py`
- `src/oppp/cli.py`
- `src/oppp/config.py`
- `src/oppp/llm.py`
- `src/oppp/dag.py`
- `src/oppp/registry.py`
- `src/oppp/services/base.py`
- `src/oppp/services/pk.py`
- `src/oppp/stages/expand.py`
- `src/oppp/stages/decompose.py`
- `src/oppp/stages/enhance.py`
- `src/oppp/stages/translate.py`
- `src/oppp/stages/aggregate.py`
- `src/oppp/eval/harness.py`
- `src/oppp/eval/compare.py`
- `src/oppp/ui/app.py`
- `tests/test_pipeline.py`
- `tests/test_services.py`
- `tests/test_stages.py`
- `tests/test_eval.py`

## Architecture Overview

The implementation remains a Python package named `oppp` with stage registries, PK service metadata, a CLI, a Streamlit debug UI, and an evaluation harness. The architecture must be changed from a linear "enhance before decompose, translate all filters, aggregate once" flow into a staged PK execution flow:

```text
query expansion
  -> query decomposition
  -> TERMite enrichment scoped by decomposed field
  -> translate small closed / early components
  -> aggregate and API count
  -> if count < 1000: fetch rows and locally filter remaining components
  -> if count >= 1000: translate additional components, aggregate, and count again
  -> final row count
```

The package already contains most necessary boundaries:

- `src/oppp/models.py` owns serializable pipeline contracts.
- `src/oppp/services/base.py` and `src/oppp/services/pk.py` own field metadata.
- `src/oppp/stages/*` own expansion, decomposition, enrichment, translation, and aggregation.
- `src/oppp/pipeline.py` owns orchestration.
- `src/oppp/execute.py` owns PK API count and row retrieval.
- `src/oppp/eval/harness.py` owns workbook loading and score calculation.
- `src/oppp/cli.py` and `src/oppp/ui/app.py` expose the pipeline.

The new behavior should use those existing boundaries instead of introducing a parallel pipeline stack.

## Data Contracts

### Decomposition

`Component` already carries the required decomposition shape:

- `field: str`
- `nl_fragment: str`
- `type: ComponentType`
- `reason: str`
- `source: str`
- `boolean_group: BooleanGroup | None`

The `reason` field remains decomposition audit metadata. TERMite must be applied to `nl_fragment` using `field` as the field context; TERMite must not use `reason` as the text to enrich.

### Field Buckets

`ServiceField.bucket` must support these values:

- `small_closed`
- `closed`
- `open`
- `enum`
- `boolean`

Small closed / early fields are closed fields whose value count is below `EARLY_CONTRIBUTOR_THRESHOLD`. `EARLY_CONTRIBUTOR_THRESHOLD` must be `1000`.

PK field metadata must classify:

| Field | Bucket | Notes |
| --- | --- | --- |
| `drugs` | `closed` | `5226` values, not early |
| `species` | `small_closed` | `285` values |
| `routes` | `small_closed` | `203` values |
| `documentSource` | `small_closed` | `55` values |
| `documentYear` | `small_closed` | `117` values |
| `parameter` | `open` | locally filterable when not translated |
| `parameterDisplay` | `open` | locally filterable when not translated |
| `studyGroups` | `open` | plural spelling is the documented field name |
| `age` | `open` | locally filterable when not translated |
| `dose` | `open` | locally filterable when not translated |
| `duration` | `open` | locally filterable when not translated |
| `sex` | `enum` | values: `Male`, `Female`, `Both` |
| `isPreclinical` | `boolean` | boolean filter |
| `concomitants` | `enum` | invariant default remains supported |
| `tissueSpecific` | `enum` | invariant default remains supported |
| `metabolitesEnantiomers` | `enum` | invariant default remains supported |

Any existing singular `studyGroup` usage in PK field metadata, facets, generated queries, row filtering, tests, CLI output, and UI output must be migrated or explicitly aliased to the documented `studyGroups` spelling.

### Runtime Execution

`PipelineResult` must expose enough runtime state for CLI, UI, tests, and evaluation:

- expanded query
- decomposition
- field-scoped TERMite annotations
- translated subqueries
- staged API query attempts
- `countTotal` for each API count attempt
- execution mode: `row_filter` or `full_api_count`
- fetched rows when row filtering is used
- final filtered rows when row filtering is used
- `final_row_count`
- validation and execution issues

The existing `row_execution`, `runtime_closed_sets`, `runtime_translations`, `filtered_datapoints`, and `final_filtered_count` fields can be retained if they are wired into the staged flow, but all public surfaces should consistently report `final_row_count`.

### Evaluation

Evaluation reads only:

- workbook: `docs/PPPK.xlsx`
- sheet: `PK_Query`
- columns: `Quety number`, `Query`, `Expected Count`

The scored assertion is:

```text
final_row_count == Expected Count
```

Tolerance metrics, per-step qualitative assessment, alternate workbook sheets, and label-level scoring are out of scope for the PK evaluation harness.

## Schema

### Advanced Search Payload

`MachineQuery.to_payload()` must produce the PK advanced search request used by `/v1/pk/search/advanced`. The payload must include the aggregated query plus the stable request controls already documented for PK:

- `query`
- `entityFilters`
- `facets`
- `sortColumns`
- `displayColumns`
- `leafOnly`
- `mixtureExpansion`
- `limitation`

The implementation must keep API leaf shape consistent across translation, aggregation, validation, tests, and docs. Field leaves are represented as field/value constraints inside boolean nodes; any internal wrapper form must be normalized before the request is sent.

### Row Filtering

When a staged count is below `1000`, `execute_rows` fetches matching datapoints. Remaining untranslated components are applied against the fetched rows. Row filter output must preserve:

- input row count
- filters applied locally
- output row count
- any filter that could not be applied locally as a warning or error according to severity

Local filtering must support at least the documented non-early PK fields that can remain after the early query:

- `drugs`
- `parameter`
- `parameterDisplay`
- `studyGroups`
- `age`
- `dose`
- `duration`
- `sex`
- `isPreclinical`
- `concomitants`
- `tissueSpecific`
- `metabolitesEnantiomers`

## Component Interfaces

### Expansion

`get_expander(...).expand(question, service)` stays first. The expanded text is the input to decomposition; the original text remains available for audit.

### Decomposition

`get_decomposer(...).decompose(expanded_text, service)` emits all typed components. Decomposition must not depend on pre-decomposition TERMite hints. The `reason` field explains routing decisions and remains visible in UI/debug output.

### TERMite Enrichment

`get_enhancer("termite").enhance_component(component, service)` or an equivalent field-scoped API must enrich each component after decomposition. The existing global `enhance(text, service)` API may remain for compatibility, but production PK orchestration must use field-scoped enrichment.

The enrichment stage must bind annotations to the corresponding component and field. Multi-value same-field components must not reuse the first annotation of a type for every fragment.

### Translation

Translation must support staged selection. It needs to translate:

1. all small closed / early filters for the first count query;
2. additional non-early filters in deterministic stages when the count remains `>= 1000`;
3. enough metadata to know which decomposition components are still pending for local row filtering.

Closed, enum, boolean, and open-field translation behavior should continue using the existing normalizer and service vocabularies. `drugs` is translated after the early stage because it is closed but not small closed.

### Aggregation

Aggregation must be callable after each staged translation set. It must:

- preserve boolean grouping from decomposition;
- add PK invariant constraints;
- keep facets and display columns consistent with question components;
- validate field names and allowed facets;
- enforce the query constraint budget;
- return issues without hiding the staged execution path.

### Execution

`execute_count(machine_query, service)` remains the count operation. `execute_rows(machine_query, service, ...)` must be used once a staged count is below `1000`.

The orchestrator must record every staged count attempt and use strict threshold semantics:

- `< 1000`: fetch rows and apply remaining filters locally;
- `>= 1000`: translate another stage or, if none remain, use the final API count.

### CLI

`oppp run` must show the final row count and the execution mode. When `--execute` is used, it must run the staged count/row path, not a single final `countTotal` call disconnected from pipeline state.

Stage commands should remain useful for debugging, but labels must reflect the new stage order:

1. expand
2. decompose
3. field-scoped TERMite enrichment
4. staged translation
5. aggregate/count/row-filter

### UI

The Streamlit UI must display the same stage order and final row count. It should show decomposition reasons, per-component TERMite annotations, staged count attempts, execution mode, and row-filter counts when available.

### Evaluation Harness

`evaluate(...)` must run the production PK staged pipeline and compare `PipelineResult.final_row_count` with `Expected Count`. `execute=False` may remain as an offline validity/debug mode, but scored evaluation requires execution because the only assessment is final row count.

Report exports may remain CSV/XLSX, but summary fields must align with count-only evaluation. Required case columns are:

- query number
- question
- expected count
- final row count
- execution mode
- exact match
- issues
- execution error

## Infrastructure

The package targets Python `>=3.11` and keeps the existing packaging model from `pyproject.toml`.

Runtime dependencies:

- Pydantic
- Typer
- RapidFuzz
- python-dotenv

Optional extras remain:

- LLM and graph support: LangChain/OpenAI/Portkey/LangGraph/DSPy packages as configured in `pyproject.toml`.
- UI: Streamlit.
- Visualization: matplotlib.
- Reports: openpyxl.
- Development: pytest and Ruff.

No new service process or database is required for this change.

## Configuration and Secrets

The existing settings model in `src/oppp/config.py` remains the configuration boundary. Required external credentials continue to come from environment variables or `.env`:

- PharmaPendium API base URL and token.
- OpenAI or Portkey configuration when LLM stages are selected.
- SciBite TERMite URL and API key when TERMite enrichment is selected.

Generated specs and tests must not require secrets. Offline tests use deterministic or fake backends.

## Technology Decisions

- Preserve the current package and registry architecture.
- Implement the staged execution model in `src/oppp/pipeline.py` instead of creating a separate PK-only runner.
- Represent small closed / early fields explicitly in service metadata so tests can validate the product classification.
- Keep the row gate threshold as a single constant equal to `1000`.
- Prefer exact count evaluation over tolerance-based metrics to match the documented workbook contract.
- Keep the gold workbook path under `docs/` because the docs identify it as the evaluation input.

## Open Questions

None.
