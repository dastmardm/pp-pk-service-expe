# Requirements

## Functional Requirements
| ID | Priority | Statement |
|----|----------|-----------|
| REQ-001 | MUST | The full pipeline accepts a natural-language question plus service name and returns a typed result containing original query, expansion, TERMite enhancement, decomposition, input translations, first machine query, execution metadata, runtime closed sets, runtime translations, post-filter metadata, final datapoints/count, and issues. |
| REQ-002 | MUST | Stage -1 uses the configured LLM to produce a faithful expanded query while preserving the exact original query. It must not silently degrade to a no-op pass-through product method. |
| REQ-003 | MUST | Stage 0 invokes TERMite for every full pipeline run and stage inspection; missing TERMite configuration or toolkit support produces a blocking configuration error. |
| REQ-004 | MUST | Stage 1 uses LLM structured output to emit `Component`s with `field`, `nl_fragment`, `type`, `reason`, `source`, and optional boolean group, and it must not consult taxonomies or choose canonical values. |
| REQ-005 | MUST | The public pipeline, CLI, UI, and evaluation entry points do not expose selectable stage methods, normalizer choices, or no-op bypasses. |
| REQ-006 | MUST | Only `type=filter` components enter translation; `type=question` components inform facets, display columns, and answer/reporting metadata. |
| REQ-007 | MUST | Input closed-set fields translate by the documented resolution order: exact match, fuzzy match, LLM pool enrichment with exact/fuzzy retry, LLM closed-set selection, membership assertion/retry with feedback, then invalid. |
| REQ-008 | MUST | A closed-set translation result is always a subset of the field's closed set. `[]`, `None`, or out-of-set-only candidates mark the translation invalid. |
| REQ-009 | MUST | Invalid input closed-set translations are recorded and excluded from the API query, entity filters, facets, display columns, and runtime post-filtering. |
| REQ-010 | MUST | The fixed normalizer policy corrects CSV-backed closed-set fragments conservatively, preserves valid class labels, and keeps open-set cleanup conservative until runtime values exist. |
| REQ-011 | MUST | Hierarchy handling supports drug class labels, exact species class labels, colloquial species member lists such as "Monkeys", effect families, assay-result qualifier stripping for positive Ames Test style phrases, curated preclinical/non-clinical handling, and brand/synonym resolution such as Columvi to Glofitamab. |
| REQ-012 | MUST | Stage 3 aggregates only valid input closed-set subqueries into a structurally valid first API query with explicit boolean groups, entity filters, service invariants, facets, and display columns. |
| REQ-013 | MUST | Execution supports existing count retrieval and row/datapoint retrieval for the validated first API query. |
| REQ-014 | MUST | For each deferred open-set filter, the pipeline derives a runtime closed set from unique non-empty fetched datapoint values for that field. |
| REQ-015 | MUST | Runtime open-set translation reuses the closed-set translator contract and may return only a subset of the fetched runtime closed set. |
| REQ-016 | MUST | Valid runtime translations post-filter datapoints; invalid runtime translations are recorded and do not narrow datapoints. |
| REQ-017 | MUST | Count-only execution and count proximity evaluation remain available, but probe-based open-field guards must not replace row-level runtime post-filtering when rows are available. |
| REQ-018 | MUST | Safety, PK, and RTB service differences remain in `ServiceConfig`/`FieldSpec` data, not forked stage code. |
| REQ-019 | MUST | CLI commands expose full runs and isolated fixed stages, including row/post-filter output, without accepting stage method or normalizer selection flags. |
| REQ-020 | MUST | The Streamlit UI displays Stage -1 through Stage 3, execution, runtime closed sets, runtime selections, invalid runtime filters, and final filtered datapoint count without stage backend selectors. |
| REQ-021 | MUST | `oppp dag` and any generated flow artifact reflect the draw.io-backed fixed pipeline and do not advertise pluggable stage backends. |
| REQ-022 | MUST | Evaluation reads `docs/sme_stage_cases.csv`, validates per-step outputs, validates per-field gold values, validates final machine-query structure, and keeps count proximity metrics. |
| REQ-023 | MUST | Regression coverage includes resolved SME cases for Q7, Q12, Q18, Q20, Q23, Q24, and Q25. |
| REQ-024 | MUST | Offline tests run with injected fakes/fixtures and make no network, LLM, or TERMite calls; test fakes are not public product methods. |
| REQ-025 | MUST | Credentials are read lazily only when the fixed stage that needs them is invoked, and `.env` or real credential files are never committed. |
| REQ-026 | MUST | Row-fetch options allow bounded fetches for debugging and evaluation, and row-fetch failures return structured issues while preserving the count-only path. |
| REQ-027 | SHOULD | Free-text comparator tie-breaks use the typed LLM judge when deterministic scoring cannot decide semantic equivalence. |

## Non-Functional Requirements
| ID | Statement |
|----|-----------|
| NFR-001 | `python3 -m compileall src/oppp`, `ruff check src tests`, `ruff format --check src tests`, and `pytest -q` pass before implementation work is considered complete. |
| NFR-002 | The offline test suite passes with no `.env`, no model credentials, no TERMite credentials, and no network access. |
| NFR-003 | LLM, TERMite, UI, diagram, and report dependencies are imported lazily so deterministic imports of `oppp` and core model modules do not require optional packages or credentials. |
| NFR-004 | Row-fetch failures leave count-only execution usable and report an issue rather than crashing the whole pipeline. |
| NFR-005 | Public command/help text contains no advertised `noop`, backend, normalizer, decomposer, enhancer, translator, or aggregator method options. |

## Constraints
- TERMite and model credentials are required for full production pipeline runs.
- Controlled vocabularies and gold sets are provided inputs; implementation code
  consumes them but does not curate them.
- Live counts can drift; count metrics are tolerance-banded.
- Tests must stay hermetic by faking external collaborators, not by exposing
  alternate product methods.
- The PharmaPendium API response shape for row datapoints must be discovered and
  handled in the execution layer.
- Core execution must not require a new mandatory HTTP dependency.

## Non-Goals
- No general conversational answering or record summarization.
- No vocabulary or gold-set curation by the translator.
- No database, queue, or migration system.
- No user-facing experiment framework for swapping stage implementations.
- No no-op product path for TERMite, expansion, decomposition, translation,
  aggregation, or normalization.

## Acceptance Criteria
- REQ-001 is satisfied when `run_pipeline` returns all listed typed artifacts in
  full row mode and returns structured issues for unavailable execution pieces.
- REQ-002 is satisfied when expansion preserves `original`, records LLM source,
  and tests prove missing LLM support is reported rather than exposed as a no-op
  stage method.
- REQ-003 is satisfied when full runs invoke TERMite and fail with a clear
  configuration error if TERMite settings/toolkit are missing.
- REQ-004 is satisfied when the decomposer emits the required component shape,
  has no taxonomy lookup dependency, and test fakes are injected through private
  fixtures rather than public method flags.
- REQ-005 is satisfied when pipeline signatures, CLI help, UI controls, and eval
  configuration have no stage method or normalizer selectors.
- REQ-006 is satisfied when only filter components produce translations and
  question components appear only in output/facet/display behavior.
- REQ-007 is satisfied when closed-set translator tests cover exact, fuzzy, LLM
  enrichment retry, LLM closed-set selection, membership feedback retry, and
  invalid fallback.
- REQ-008 is satisfied when tests prove emitted input and runtime selections are
  subsets of their closed sets and out-of-set-only returns are invalid.
- REQ-009 is satisfied when invalid input closed-set translations are visible in
  issues and absent from the first API query and post-filter set.
- REQ-010 is satisfied when normalizer tests prove fixed closed-set typo
  correction, valid class preservation, and conservative open-set cleanup.
- REQ-011 is satisfied when tests cover Q18 MTD, Q20 Ames Test, Q23 Monkeys, Q24
  ADC, Q25 Columvi, preclinical handling, and class/family expansion.
- REQ-012 is satisfied when Stage 3 validates one top-level query, correct AND/OR
  grouping, entity routing, service invariants, facets, and display columns.
- REQ-013 is satisfied when mocked count and row API responses produce typed
  count and datapoint execution results.
- REQ-014 is satisfied when mocked datapoints derive sorted unique runtime values
  for deferred open fields such as `parameterComment`.
- REQ-015 is satisfied when runtime translation uses the same closed-set
  resolution and membership assertion over fetched runtime values.
- REQ-016 is satisfied when valid runtime selections filter datapoints and
  invalid selections leave datapoints unchanged with a warning.
- REQ-017 is satisfied when count-only execution/evaluation still works and row
  mode uses runtime post-filtering instead of zero-count probes.
- REQ-018 is satisfied when service tests verify Safety/PK/RTB configs and no
  stage module owns service-specific field maps.
- REQ-019 is satisfied when CLI commands run the fixed methods, show runtime
  metadata, and reject/omit old method-selection flags.
- REQ-020 is satisfied when UI tests or code inspection show runtime panels and
  no backend selector widgets.
- REQ-021 is satisfied when diagram generation or exported flow text matches
  `docs/agent-dag.drawio` and contains no pluggable-backend legend.
- REQ-022 is satisfied when evaluation loads both SME gold sources and reports
  per-step, per-field, machine-query, and count metrics.
- REQ-023 is satisfied when regression tests explicitly cover Q7, Q12, Q18, Q20,
  Q23, Q24, and Q25.
- REQ-024 is satisfied when the full Quality Gates pass without `.env`, network,
  model credentials, or TERMite credentials.
- REQ-025 is satisfied when config loads secrets only at invocation, `.gitignore`
  excludes real env files, and `.env.example` contains keys only.
- REQ-026 is satisfied when row execution supports bounded fetch options and
  structured failure issues while count-only execution remains usable.
