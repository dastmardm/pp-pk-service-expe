# Requirements

## Functional Requirements

| ID | Priority | Statement |
|----|----------|-----------|
| REQ-001 | MUST | The full pipeline accepts a natural-language PK question and returns a typed `PipelineResult` containing: original query, expansion, decomposition components, TERMite-enhanced annotations (Stage 0 runs after Stage 1 but before Stage 2), Stage-2A machine subqueries, first machine query, execution metadata (`countTotal`), and issues. The field order in `PipelineResult` does not imply stage execution order; the actual order is: Stage -1 expand → Stage 1 decompose → Stage 0 TERMite enhance → annotation reconciliation → Stage 2A translate → Stage 3A aggregate/execute. When row fetch is available, the result additionally contains row execution output, runtime closed sets, runtime translations, post-filter metadata, filtered datapoints, and final filtered count. |
| REQ-002 | MUST | Stage -1 uses the configured LLM to produce a faithful `ExpandedQuery` while preserving `original`. It must not silently degrade to a no-op passthrough for full pipeline runs. |
| REQ-003 | MUST | Stage 0 invokes TERMite for every full pipeline run and every `oppp enhance` command. Missing TERMite configuration or toolkit is a blocking configuration error, not permission to continue with an empty `EnhancedQuery`. |
| REQ-004 | MUST | Stage 1 uses LLM structured output to emit `Component`s with `field`, `nl_fragment`, `type` (exactly `filter` or `question`), `reason`, `source`, and optional `boolean_group`. It must not consult taxonomies or choose canonical values. |
| REQ-005 | MUST | The annotation reconciliation pass deterministically promotes retrieval-defining PK parameters (TERMite type `PARAMETER`) from `question` to `filter` when TERMite recognized the entity, and resolves routing ambiguities using the TERMite type-to-field map. |
| REQ-006 | MUST | Only `type=filter` components enter Stage 2 translation. `type=question` components inform facets, `displayColumns`, and post-retrieval output metadata only. |
| REQ-007 | MUST | Input closed-set fields translate via the documented resolution order: (1) exact match, (2) fuzzy match, (3) LLM pool enrichment + exact/fuzzy retry, (4) LLM selection from closed set, (5) membership assertion/retry with feedback, (6) invalid. |
| REQ-008 | MUST | A closed-set translation result is always a subset of the field's closed set. `[]`, `None`, or out-of-set-only candidates mark the translation invalid. |
| REQ-009 | MUST | Invalid input closed-set translations are recorded in `PipelineResult.issues` and excluded from the API query, facets, display columns, and post-filter set. |
| REQ-010 | MUST | The fixed normalizer corrects CSV-backed closed-set fragments via fuzzy matching, preserves valid class labels, and keeps open-set field cleanup conservative until runtime values exist. The normalizer policy is not selectable at runtime. |
| REQ-011 | MUST | Hierarchy handling supports: drug class label → API server-side subtree resolution; exact species class label → server-side resolution; colloquial species groups without exact class label (e.g. "Monkeys") → member species expansion; document source → FDA/EMA parent label. A specific leaf is never widened. |
| REQ-012 | MUST | Stage 3A aggregates only valid Stage-2A subqueries into a structurally valid first API machine query, applying boolean grouping, PK service invariants (`concomitants` Fasted-or-empty, `tissueSpecific` Not-tissue-specific, `metabolitesEnantiomers` Not-metabolites/enantiomers), facets, and display columns. |
| REQ-013 | MUST | Count execution (`execute_count`) POSTs the validated `MachineQuery` to the PK service URL and returns `ExecutionResult{ok, count_total?, status?, error?}`. `ok=true` indicates the API returned a valid response; `count_total` is absent only when the API response contains no count. |
| REQ-014 | MUST | Row execution (`execute_rows`) paginates the PK API to collect datapoints into a normalized `RowExecutionResult`. Pagination failure produces `ok=false` with a structured issue while leaving count-only execution usable. |
| REQ-015 | MUST | For each deferred open-set filter field, the pipeline derives a `RuntimeClosedSet` from sorted unique non-empty values for that field in the fetched datapoints. |
| REQ-016 | MUST | Runtime open-set translation reuses the `CONTRACT-CLOSED-SET-TRANSLATION` contract over the runtime closed set and emits only a subset of the fetched values. |
| REQ-017 | MUST | Valid runtime translations post-filter datapoints; invalid runtime translations are recorded and leave datapoints unchanged. |
| REQ-018 | MUST | Count-only execution and count proximity evaluation remain usable independently of row fetch. Probe-based open-filter guards (`drop_empty_open_filters`) are available as a v0.1 live-run guard but must not be treated as the row-mode runtime post-filtering path. |
| REQ-019 | MUST | PK service configuration (`src/oppp/services/pk.py`) encodes field buckets, `EARLY_CONTRIBUTOR_THRESHOLD` (default 500), taxonomy paths, facet allow-list, PK invariants, and search URL. Stage code must not contain PK-specific field maps. |
| REQ-020 | MUST | CLI commands (`oppp run`, `oppp enhance`, `oppp decompose`, `oppp field`, `oppp aggregate`, `oppp lookup`, `oppp eval`, `oppp dag`, `oppp services`) expose only service, input, execution, and output controls. No `--enhancer`, `--decomposer`, `--translator`, `--aggregator`, `--normalizer`, or equivalent method-selection flags. The `oppp services` command outputs at minimum the name and search URL of each registered service (e.g. the PK service name and `/v1/pk/search/advanced`). |
| REQ-021 | MUST | The Streamlit UI displays Stage -1 through Stage 3, execution count, and (when rows are available) runtime closed sets, runtime selections, invalid runtime filters, and filtered count. No stage backend selector widgets. |
| REQ-022 | MUST | `oppp dag` and any exported flow text reflect the draw.io-backed fixed pipeline path (eight stage labels: Stage -1, Stage 0, Stage 1, Stage 2A, Stage 3A, Stage 2B, Stage 3B, Stage 2C) and contain no pluggable-backend legend or stage options. |
| REQ-023 | MUST | The evaluation harness (`eval/harness.py`) loads `docs/PPPK.xlsx` → `PK_Query` sheet, runs each of the 47 queries through the full pipeline, compares `countTotal` to `Expected Count`, and reports `valid_rate`, `executed_rate`, `exact_count`, and `within_<tol>`. |
| REQ-024 | MUST | Per-step comparators (`eval/per_step.py`) score Stage 0 TERMite entity (type, label) pairs by set precision/recall, Stage 1 routing/type classification by exact match, Stage 1 NL fragments by LLM-as-judge semantic equivalence, Stage 2 translated field names, and Stage 3 machine-query structure by structural compare plus LLM judge tie-break. |
| REQ-025 | MUST | Regression coverage includes at minimum: species class expansion (e.g. "Rodent" → all rodent species), drug fuzzy match (e.g. "suntinib" → Sunitinib), open-set parameter routing ("AUC or Cmax" → `parameter` OR group), and PK invariant application (concomitants/tissueSpecific/metabolitesEnantiomers defaults). |
| REQ-026 | MUST | Offline tests run with injected fakes, fixtures, or monkeypatched clients and make no network, LLM, or TERMite calls. Test fakes are not public product methods. |
| REQ-027 | MUST | Credentials are read lazily only when the fixed stage that needs them is invoked. `.env` and real credential files are never committed. `.env.example` is keys-only. |
| REQ-028 | SHOULD | Free-text comparator tie-breaks use the typed `LLMJudge` (`eval/judge.py`) when deterministic scoring cannot decide semantic equivalence. Judge verdicts are typed (`match|partial|miss` + reason) and auditable. |

## Non-Functional Requirements

| ID | Statement |
|----|-----------|
| NFR-001 | `python3 -m compileall src/oppp`, `ruff check src tests`, `ruff format --check src tests`, and `pytest -q` all pass before implementation work is merged. |
| NFR-002 | The offline test suite passes with no `.env`, no model credentials, no TERMite credentials, and no network access. |
| NFR-003 | LLM, TERMite, UI (`streamlit`), DAG rendering (`matplotlib`), and report (`openpyxl`) dependencies are imported lazily so `import oppp` and `from oppp.models import *` do not require optional packages or credentials. |
| NFR-004 | Row-fetch failures leave count-only execution usable; `execute_rows` returns a structured `RowExecutionResult` with `ok=false` and an error message rather than raising an unhandled exception. |
| NFR-005 | Public CLI help text and `oppp services` output contain no advertised `noop`, backend, normalizer, decomposer, enhancer, translator, or aggregator method option names. |

## Constraints
- TERMite and LLM model credentials are required for full production pipeline runs.
- The controlled vocabularies (`inputs/*.csv`) and the gold set (`docs/PPPK.xlsx`) are provided inputs; the implementation consumes them and does not curate them. The 47-row count cited in REQ-023 and evaluation criteria reflects the `PK_Query` sheet as of v0.1 spec authoring; evaluation should read the actual row count from the XLSX rather than asserting exactly 47 as a hard constant.
- Live `countTotal` values can drift as the PharmaPendium database updates; count proximity metrics use a configurable tolerance band.
- Tests must stay hermetic by faking external collaborators, not by exposing alternate product methods.
- The PharmaPendium API response shape for datapoint rows must be discovered and handled in `execute.py`; if rows are unavailable for the endpoint, `execute_rows` returns a typed unavailable result.
- Core execution must not require a new mandatory HTTP dependency beyond `urllib.request`.

## Non-Goals
- No general conversational answering or record summarization.
- No vocabulary or gold-set curation by the translator.
- No database, queue, or migration system.
- No user-facing experiment framework for swapping stage implementations.
- No no-op product path for any stage (TERMite, expansion, decomposition, translation, aggregation, normalization).
- Safety and RTB service pipelines are not active product scope in v0.1 (service config files may remain for future activation).

## Acceptance Criteria

| REQ | Criterion |
|-----|-----------|
| REQ-001 | `run_pipeline` returns all listed typed artifacts in count mode; in row mode it additionally returns `row_execution`, `runtime_closed_sets`, `runtime_translations`, `filtered_datapoints`, `final_filtered_count`; unavailable row execution returns a structured issue without crashing count mode. |
| REQ-002 | Expansion preserves `original` in `ExpandedQuery`, records `source=llm`, and tests prove missing LLM config produces a structured issue rather than a silent passthrough. |
| REQ-003 | Full `oppp run` invokes TERMite; missing `TERMITE_HOME` produces a clear blocking configuration error; no enhancement without TERMite for full runs. |
| REQ-004 | Decomposer emits required `Component` shape; unit test proves no taxonomy CSV is loaded during decomposition; fakes are injected through `conftest.py` fixtures. |
| REQ-005 | Annotation reconciliation unit test: `PARAMETER`-typed TERMite annotation promotes a `question` component to `filter` and resolves field routing conflicts. |
| REQ-006 | Only `filter` components appear in the Stage-2A translation input; `question` components appear only in facet/displayColumn derivation. |
| REQ-007 | Closed-set translator tests cover: exact match, fuzzy match, LLM enrichment retry, LLM closed-set selection, membership feedback retry, and invalid fallback (six cases minimum). |
| REQ-008 | Test proves emitted input and runtime selections are proper subsets of their closed sets; out-of-set-only returns are marked invalid. |
| REQ-009 | Invalid input translations appear in `PipelineResult.issues` and the Stage-3A machine query contains no invalid field filter. |
| REQ-010 | Normalizer tests prove: fuzzy correction for a closed-set typo, class label preservation, and conservative open-set passthrough. |
| REQ-011 | Tests cover at minimum: "Rodent" → rodent member species (colloquial group expansion), "Sunitinib" drug exact match, drug class label resolution. |
| REQ-012 | Stage-3A structural test: exactly one top-level `AND` or `OR`; PK invariants present; invalid subqueries absent; facets from allow-list. |
| REQ-013 | Mocked count response yields typed `ExecutionResult` with `ok=true`, `count_total=N`; mocked error yields `ok=false` with `error`. |
| REQ-014 | Mocked paginated row response yields `RowExecutionResult` with normalized `datapoints`; mocked row error yields `ok=false` with issue while count path still works. |
| REQ-015 | Mocked `datapoints` with known field values yield a `RuntimeClosedSet` that is sorted, unique, and non-empty. |
| REQ-016 | Runtime translation test: selected values are a subset of the runtime closed set; out-of-runtime-set proposals are rejected. |
| REQ-017 | Post-filter test: valid selection removes non-matching datapoints; invalid selection leaves datapoints unchanged and adds a warning to issues. |
| REQ-018 | Count-only `oppp eval` works without row fetch enabled; `probe_open_filters=True` drops confirmed zero-count open filters but does not replace post-filtering in row mode. |
| REQ-019 | `src/oppp/services/pk.py` contains all PK field specs; grep for `species` or `drugs` or `route` inside `stages/translate.py` or `stages/aggregate.py` returns no hardcoded field names. |
| REQ-020 | `oppp run --help` output contains no `--enhancer`, `--decomposer`, `--translator`, `--aggregator`, or `--normalizer` flags. `oppp services` produces output that includes the PK service name and search URL. |
| REQ-021 | Streamlit `app.py` code inspection: no `st.selectbox` or similar widget for stage backend selection; runtime panels shown when row data is available. |
| REQ-022 | `oppp dag` output or `dag.py` text contains all eight stage labels (`Stage -1`, `Stage 0`, `Stage 1`, `Stage 2A`, `Stage 3A`, `Stage 2B`, `Stage 3B`, `Stage 2C`) and contains no `--enhancer` or backend registry. |
| REQ-023 | `eval/harness.py` loads `docs/PPPK.xlsx` via openpyxl, reads `PK_Query` sheet, iterates 47 rows, and produces `valid_rate`, `executed_rate`, `exact_count`, `within_<tol>` metrics. |
| REQ-024 | `eval/per_step.py` exports functions for Stage 0 set P/R, Stage 1 field/type exact score, Stage 1 fragment judge call, Stage 2 field name score, Stage 3 structural compare. |
| REQ-025 | `tests/test_stages.py` includes test cases: "Rodent" species expansion, "suntinib" fuzzy drug resolution, "AUC or Cmax" OR-group routing, PK invariants applied without user override. |
| REQ-026 | `pytest -q` passes with no `.env`; `conftest.py` provides fake LLM client and fake TERMite client fixtures; no test imports live LLM or TERMite modules unconditionally. |
| REQ-027 | `config.py` reads secrets lazily; `.gitignore` excludes `.env` and `*.env`; `.env.example` contains only key names with no values. |
| REQ-028 | `eval/judge.py` exports `LLMJudge` and `JudgeVerdict`; tests inject a fake client; judge is called only for fragment, open-pattern, and structure tie-break scoring steps. |
