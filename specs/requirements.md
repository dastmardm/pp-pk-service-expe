# Requirements

## Functional Requirements

| ID | Priority | Statement |
| --- | --- | --- |
| REQ-001 | MUST | The production PK pipeline accepts a natural-language PK question and executes the fixed staged order: expansion -> decomposition -> field-scoped TERMite enrichment -> early small-closed translation -> aggregate/count -> `1000` count gate -> row filtering or staged non-early translation -> final row count. |
| REQ-002 | MUST | Expansion preserves the original question and produces expanded text that becomes the only text input to decomposition. |
| REQ-003 | MUST | Decomposition emits typed components containing `field`, `nl_fragment`, `type`, `reason`, `source`, and optional boolean grouping metadata, without depending on TERMite hints or controlled-vocabulary translation. |
| REQ-004 | MUST | TERMite enrichment runs after decomposition for each component, using that component's `field` as context and `nl_fragment` as the text to enrich; annotations remain bound to the originating component. |
| REQ-005 | MUST | PK service metadata classifies fields into `small_closed`, `closed`, `open`, `enum`, and `boolean` buckets with `EARLY_CONTRIBUTOR_THRESHOLD = 1000`. |
| REQ-006 | MUST | The small closed / early fields are exactly `species`, `routes`, `documentSource`, and `documentYear`; `drugs` is closed but not early because its value count is greater than `1000`. |
| REQ-007 | MUST | The documented PK field spelling is `studyGroups`; existing singular `studyGroup` usage is migrated or explicitly aliased so generated queries, facets, row filtering, tests, CLI output, and UI output use the plural spelling. |
| REQ-008 | MUST | The first translation stage translates all and only early small-closed filter components, preserving boolean grouping metadata needed by aggregation. |
| REQ-009 | MUST | Translation supports deterministic staged selection for non-early closed, enum, boolean, and open fields when the count remains `>= 1000`, while recording which components remain pending for possible local row filtering. |
| REQ-010 | MUST | Aggregation is callable after every staged translation set and produces a structurally valid PK advanced search machine query that preserves boolean grouping, applies PK invariant constraints, validates field names and facets, enforces the query constraint budget, and records issues. |
| REQ-011 | MUST | `MachineQuery.to_payload()` emits the `/v1/pk/search/advanced` payload with `query`, `entityFilters`, `facets`, `sortColumns`, `displayColumns`, `leafOnly`, `mixtureExpansion`, and `limitation`, with field leaves normalized into boolean nodes before execution. |
| REQ-012 | MUST | Every staged API count attempt is executed through `execute_count`, records the machine query and returned `countTotal`, and remains visible in `PipelineResult`. |
| REQ-013 | MUST | A staged count `< 1000` triggers `execute_rows` for that staged query and then applies all remaining untranslated filters locally against the fetched datapoints. |
| REQ-014 | MUST | A staged count `>= 1000` triggers another deterministic non-early translation stage when pending filters remain; when no pending filters remain, the final API `countTotal` becomes `final_row_count`. |
| REQ-015 | MUST | Local row filtering supports at least `drugs`, `parameter`, `parameterDisplay`, `studyGroups`, `age`, `dose`, `duration`, `sex`, `isPreclinical`, `concomitants`, `tissueSpecific`, and `metabolitesEnantiomers`. |
| REQ-016 | MUST | Row filter output records input row count, locally applied filters, output row count, and warnings or errors for filters that cannot be applied locally. |
| REQ-017 | MUST | `PipelineResult` exposes expanded query, decomposition, field-scoped TERMite annotations, translated subqueries, staged API attempts, per-attempt `countTotal`, execution mode (`row_filter` or `full_api_count`), fetched rows when used, final filtered rows when used, `final_row_count`, validation issues, and execution issues. |
| REQ-018 | MUST | CLI command `oppp run --execute` runs the staged count/row path and displays `final_row_count` plus execution mode; debug commands label the stages as expand, decompose, field-scoped TERMite enrichment, staged translation, and aggregate/count/row-filter. |
| REQ-019 | MUST | The Streamlit UI displays the same stage order as the production pipeline and shows decomposition reasons, per-component TERMite annotations, staged count attempts, execution mode, final row count, and row-filter counts when available. |
| REQ-020 | MUST | The evaluation harness reads only `docs/PPPK.xlsx`, sheet `PK_Query`, columns `Quety number`, `Query`, and `Expected Count`, runs each query through the production staged PK pipeline, and scores only exact equality of `final_row_count` and `Expected Count`. |
| REQ-021 | MUST | Scored evaluation requires execution of the staged pipeline; `execute=False` may remain only as an offline validity/debug mode and must not produce scored exact-count results. |
| REQ-022 | MUST | Evaluation report exports align with count-only scoring and include query number, question, expected count, final row count, execution mode, exact match, issues, and execution error. |
| REQ-023 | MUST | Configuration and secrets remain behind `src/oppp/config.py`; PharmaPendium, OpenAI/Portkey, and TERMite credentials are read lazily only when the stage that needs them runs. |
| REQ-024 | MUST | Offline tests use deterministic or fake backends and do not require network access, PharmaPendium credentials, LLM credentials, TERMite credentials, or optional UI/report/graph packages. |
| REQ-025 | MUST | The implementation uses existing `oppp` package boundaries (`models.py`, `services/`, `stages/`, `pipeline.py`, `execute.py`, `eval/`, `cli.py`, and `ui/`) and does not introduce a second PK-only pipeline stack, service process, or database. |
| REQ-026 | SHOULD | CSV/XLSX report exports, stage inspection commands, and offline debug output remain available when they do not alter count-only scoring semantics. |

## Non-Functional Requirements

| ID | Statement |
| --- | --- |
| NFR-001 | `python3 -m compileall src/oppp`, `ruff check src tests`, `ruff format --check src tests`, and `pytest -q` pass before implementation changes are merged. |
| NFR-002 | `import oppp` and `from oppp.models import *` succeed without `.env`, PharmaPendium credentials, LLM credentials, TERMite credentials, Streamlit, matplotlib, or openpyxl. |
| NFR-003 | The offline test suite completes with no network access and no live external-service credentials. |
| NFR-004 | The strict row gate uses the single value `1000`; tests cover counts `999`, `1000`, and `1001`. |
| NFR-005 | Row retrieval or local-filter failure returns structured execution issues without crashing count-only staged execution. |
| NFR-006 | The final count used by evaluation is always exposed as `PipelineResult.final_row_count`; public surfaces do not require consumers to infer the final value from staged `countTotal` entries. |

## Constraints

- Product and behavior changes must start in `docs/` and be propagated through the spec pipeline.
- The main external endpoint is `/v1/pk/search/advanced`.
- The gold evaluation workbook is `docs/PPPK.xlsx`; the only scored sheet is `PK_Query`.
- Evaluation uses exact count matching against `Expected Count`; tolerance bands and alternate sheets are out of scope.
- The PK row gate is exactly `1000`; `< 1000` means row filtering, and `>= 1000` means staged non-early translation unless all filters are already translated.
- The existing package targets Python `>=3.11` and retains its `pyproject.toml` packaging model.
- Runtime credentials are supplied through environment variables or `.env`, never through committed files.
- No new service process, queue, migration system, or database is required.

## Non-Goals

- The system does not answer PK questions in prose.
- The system does not score per-step qualitative labels, tolerance bands, or workbook sheets other than `PK_Query`.
- The system does not curate the gold workbook or PharmaPendium vocabularies as part of translation.
- The system does not expose user-selectable production alternatives for the fixed PK staged path.
- The system does not run TERMite as a global pre-decomposition rewrite.
- Safety, RTB, or other non-PK service pipelines are not active scope for this requirements set.

## Acceptance Criteria

| REQ | Criterion |
| --- | --- |
| REQ-001 | A pipeline integration test records stage events in the required order and proves no API count is attempted before expansion, decomposition, field-scoped TERMite enrichment, early translation, and aggregation complete. |
| REQ-002 | Expansion tests show the original question is preserved and the expanded text is passed to decomposition. |
| REQ-003 | Decomposition tests assert every component has `field`, `nl_fragment`, `type`, `reason`, `source`, and optional boolean grouping, and that decomposition can run with fake LLM output before TERMite is invoked. |
| REQ-004 | TERMite tests use two components with different fields and prove each call receives that component's field and `nl_fragment`, not the global query or `reason`. |
| REQ-005 | PK service metadata exposes all five bucket values and a test asserts `EARLY_CONTRIBUTOR_THRESHOLD == 1000`. |
| REQ-006 | PK metadata tests assert `species`, `routes`, `documentSource`, and `documentYear` are `small_closed`, while `drugs` is `closed` and absent from the first early translation set. |
| REQ-007 | A compatibility test proves singular `studyGroup` input, if accepted, resolves to the documented `studyGroups` field in generated queries and row filtering. |
| REQ-008 | A staged translation test proves the first translation batch contains every early component and no non-early component. |
| REQ-009 | A staged translation test with a `>= 1000` early count proves pending non-early components are translated in deterministic order and tracked as no longer pending. |
| REQ-010 | Aggregation tests assert boolean grouping is preserved, PK invariants are present, invalid fields/facets are reported, and the staged attempt is not hidden. |
| REQ-011 | Payload tests assert `MachineQuery.to_payload()` includes the required top-level keys and normalizes field constraints inside boolean nodes. |
| REQ-012 | Execution tests with a fake count backend assert each staged attempt records the query and returned `countTotal` in `PipelineResult`. |
| REQ-013 | A fake count of `999` triggers row fetch and local filtering of pending filters. |
| REQ-014 | Fake counts of `1000` and `1001` trigger non-early translation when pending filters remain, and use final API `countTotal` only after all filters are translated. |
| REQ-015 | Row-filter tests cover each required local-filter field at least once. |
| REQ-016 | Row-filter tests assert input count, applied filters, output count, and unsupported-filter warnings or errors are recorded. |
| REQ-017 | `PipelineResult` serialization tests assert every required runtime field is present for both `row_filter` and `full_api_count` modes. |
| REQ-018 | CLI tests assert `oppp run --execute` reports final row count and execution mode, and stage/help output uses the new stage labels without legacy stage numbering. |
| REQ-019 | UI code or component tests assert the stage panels and runtime details are present and no UI-only execution path bypasses the production pipeline. |
| REQ-020 | Evaluation harness tests create a temporary workbook with `PK_Query`, run fake staged pipeline results, and assert exact-match scoring uses only `final_row_count == Expected Count`. |
| REQ-021 | Evaluation tests assert `execute=False` results are marked offline/debug and excluded from scored exact-count evaluation. |
| REQ-022 | Report-export tests assert the required count-only columns are present and no tolerance or per-step score column is required for scored output. |
| REQ-023 | Config tests assert importing package modules does not read secrets and that missing credentials fail only when the corresponding live stage is invoked. |
| REQ-024 | The default `pytest -q` suite passes without network or external credentials by using fake clients/backends. |
| REQ-025 | Code inspection or tests assert staged orchestration is implemented through the existing package modules and no second PK-only runner/service/database is introduced. |
