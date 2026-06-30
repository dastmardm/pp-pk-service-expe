# Requirements

## Functional Requirements
| ID | Priority | Statement |
|----|----------|-----------|
| REQ-001 | MUST | The pipeline accepts a natural-language question plus service name and returns a typed result containing the original query, expanded query, enhancement, decomposition, Stage-2 subqueries, final machine query, issues, and execution/post-filter metadata when requested. |
| REQ-002 | MUST | Stage -1 preserves the original query and may provide a faithful expanded query without adding, dropping, or changing entities, values, or filters. |
| REQ-003 | MUST | Stage 0 has `noop` and `termite` backends and the pipeline can run end to end with `noop`. |
| REQ-004 | MUST | Stage 1 emits `Component`s with `field`, `nl_fragment`, `type`, `reason`, `source`, and optional boolean group; the production decomposer remains vocab-free. |
| REQ-005 | MUST | Only `type=filter` components enter Stage 2 translation; `type=question` components inform facets, display columns, and answer/reporting metadata. |
| REQ-006 | MUST | Input closed-set fields translate by the documented resolution order: exact match, fuzzy match, LLM pool enrichment with exact/fuzzy retry, closed-set LLM selection, membership assertion/retry, then invalid. |
| REQ-007 | MUST | A closed-set translation result is always a subset of the field's closed set. `[]`, `None`, or out-of-set-only candidates mark the translation invalid. |
| REQ-008 | MUST | Invalid input closed-set translations are recorded and excluded from the API query, entity filters, facets, display columns, and post-filtering. |
| REQ-009 | MUST | Hierarchy handling supports drug class labels, exact species class labels, colloquial species member lists such as "Monkeys", effect rollups, assay-result qualifier stripping for positive Ames Test style phrases, and curated preclinical/non-clinical boolean handling. |
| REQ-010 | MUST | Stage 3 aggregates only valid input closed-set subqueries into a structurally valid first API query with explicit boolean groups, entity filters, service invariants, facets, and display columns. |
| REQ-011 | MUST | Execution supports existing count retrieval and adds row/datapoint retrieval for the validated first API query. |
| REQ-012 | MUST | For each deferred open-set filter, the pipeline derives a runtime closed set from unique non-empty fetched datapoint values for that field. |
| REQ-013 | MUST | Runtime open-set translation reuses the closed-set translator contract and may return only a subset of the fetched runtime closed set. |
| REQ-014 | MUST | Valid runtime translations post-filter datapoints; invalid runtime translations are recorded and do not narrow datapoints. |
| REQ-015 | MUST | The v0.1 zero-count probe path remains available as a count-only/live guard and must not replace row-level runtime post-filtering when rows are available. |
| REQ-016 | MUST | Safety, PK, and RTB service differences remain in `ServiceConfig`/`FieldSpec` data, not forked stage code. |
| REQ-017 | MUST | CLI commands expose full runs and isolated stages, including a way to request or display row/post-filter output without breaking payload-only/count-only workflows. |
| REQ-018 | MUST | The Streamlit UI displays Stage -1 through Stage 3, execution, runtime selections, and final filtered datapoint count when available. |
| REQ-019 | MUST | Evaluation reads `docs/sme_stage_cases.csv`, validates per-step outputs, validates final machine-query structure, and keeps count proximity metrics. |
| REQ-020 | MUST | Regression coverage includes resolved SME cases for Q7, Q12, Q18, Q20, Q23, Q24, and Q25. |
| REQ-021 | MUST | Offline tests run with `noop`/`gazetteer`/`deterministic` paths and make no network, LLM, or TERMite calls. |
| REQ-022 | MUST | Credentials are read lazily only for selected model/entity backends, and `.env` or real credential files are never committed. |
| REQ-023 | SHOULD | Free-text comparator tie-breaks use the typed LLM judge when deterministic scoring cannot decide semantic equivalence. |
| REQ-024 | SHOULD | Row-fetch options allow bounded fetches for debugging and evaluation to avoid accidentally requesting excessive datapoints. |

## Non-Functional Requirements
| ID | Statement |
|----|-----------|
| NFR-001 | `python3 -m compileall src/oppp`, `ruff check src tests`, `ruff format --check src tests`, and `pytest -q` pass before implementation work is considered complete. |
| NFR-002 | The offline test suite must pass with no `.env`, no model credentials, no TERMite credentials, and no network access. |
| NFR-003 | Optional LLM/UI/report dependencies must not be imported by deterministic core imports. |
| NFR-004 | Row-fetch failures must leave the count-only query path usable and report an issue rather than crashing the whole pipeline. |

## Constraints
- The PharmaPendium API response shape for row datapoints must be discovered and
  handled in the execution layer.
- Controlled vocabularies and gold sets are provided inputs; implementation code
  consumes them but does not curate them.
- Live counts can drift; count metrics are tolerance-banded.
- Secrets and external services are optional for offline operation.

## Non-Goals
- No general conversational answering or record summarization.
- No vocabulary or gold-set curation by the translator.
- No database, queue, or migration system.
- No mandatory new HTTP dependency for core execution.

## Acceptance Criteria
- REQ-001 to REQ-005 are satisfied when an offline `run_pipeline` result carries
  expanded, enhanced, decomposition, subquery, machine-query, and issue artifacts,
  and only filter components produce subqueries.
- REQ-006 to REQ-009 are satisfied when closed-set translator tests prove valid
  subset output, invalid dropped filters, Q20 Ames Test, Q23 Monkeys, Q24 ADC, and
  Q25 Columvi behavior.
- REQ-010 is satisfied when Stage 3 validates one top-level query, correct
  AND/OR grouping, entity routing, service invariants, facets, and display
  columns.
- REQ-011 to REQ-014 are satisfied when a mocked row API response produces
  datapoints, derives runtime values, translates an open-set field such as
  `parameterComment`, applies the post-filter, and records invalid runtime
  selections without narrowing rows.
- REQ-015 is satisfied when count-only execution with probes still works and row
  mode bypasses probes in favor of runtime post-filtering.
- REQ-016 is satisfied when service tests verify Safety/PK/RTB configs and no
  stage module owns service-specific field maps.
- REQ-017 and REQ-018 are satisfied when CLI/UI surfaces show row execution and
  runtime post-filter metadata while existing payload/count workflows continue.
- REQ-019 and REQ-020 are satisfied when per-step and regression tests cover the
  resolved SME rows and the evaluation harness still reports valid/count metrics.
- REQ-021 and REQ-022 are satisfied when the full Quality Gates pass with no
  external credentials and `.env` remains untracked.
