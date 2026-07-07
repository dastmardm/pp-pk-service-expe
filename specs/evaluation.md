# Evaluation Criteria

## Sources
- `specs/requirements.md` — functional and non-functional requirements
- `specs/technical.md` — data contracts, component interfaces, technology decisions
- `specs/constitution.md` — core principles and technology stack
- `specs/skeleton.md` — promised files and their owners
- `specs/plan.md` — risk mitigations and constitution check
- `specs/product.md` — core capabilities and operational model

## How to read this file
Each criterion is a single objectively-decidable check. `/mdevaluation` assigns PASS / PARTIAL / FAIL / N/A per criterion by inspecting the codebase, and cites file:line evidence. BLOCKED is the escape hatch if the criterion itself is defective. This file defines WHAT; `/mdevaluation` defines HOW.

## Criteria

| ID | Source ref | Category | Criterion (objectively decidable) | Evidence to look for | Severity |
|----|------------|----------|-----------------------------------|----------------------|----------|
| EVAL-001 | REQ-001 | Requirement | `run_pipeline` returns a typed `PipelineResult` with fields `original`, `expanded`, `enhanced`, `decomposition`, `subqueries`, `machine_query`, `execution`, `issues` | `src/oppp/models.py`: `PipelineResult` class with all listed fields; `src/oppp/pipeline.py`: `run_pipeline` return type annotation | BLOCKER |
| EVAL-002 | REQ-001 | Requirement | In row mode (`fetch_rows=True`), `PipelineResult` additionally has `row_execution`, `runtime_closed_sets`, `runtime_translations`, `filtered_datapoints`, `final_filtered_count` | `src/oppp/models.py`: `PipelineResult` has these fields; `pipeline.py`: populates them in row-mode branch | MAJOR |
| EVAL-003 | REQ-002 | Requirement | `expand_query` preserves `ExpandedQuery.original` equal to input query and records `source` | `src/oppp/stages/expand.py`: function signature returns `ExpandedQuery`; `models.py`: `ExpandedQuery.original` field present | BLOCKER |
| EVAL-004 | REQ-002 | Requirement | `expand_query` raises `ConfigError` (not silently returns a no-op result) when LLM settings are absent | `tests/test_stages.py`: test asserts `ConfigError` on missing `PORTKEY_ENDPOINT` | MAJOR |
| EVAL-005 | REQ-003 | Requirement | `enhance` calls TERMite for every invocation; missing `TERMITE_HOME` raises `ConfigError` | `src/oppp/stages/enhance.py`: TERMite call present; `tests/test_stages.py`: missing config test | BLOCKER |
| EVAL-006 | REQ-003, CONST-2 | Constitution | TERMite client is NOT imported at module load time in `enhance.py` (lazy import) | `src/oppp/stages/enhance.py`: TERMite import inside function body or conditional block, not at top-level | MAJOR |
| EVAL-007 | REQ-004 | Requirement | `decompose` does not import or call any taxonomy CSV or `TaxonomyIndex` | `src/oppp/stages/decompose.py`: no import of `taxonomy.index` or any CSV reader; grep for `TaxonomyIndex` in `decompose.py` returns nothing | BLOCKER |
| EVAL-008 | REQ-004 | Requirement | `Component` Pydantic model has `field`, `nl_fragment`, `type` (enum `filter`\|`question`), `reason`, `source`, optional `boolean_group` | `src/oppp/models.py`: `Component` class with all five required fields plus optional `boolean_group` | BLOCKER |
| EVAL-009 | REQ-005 | Requirement | `reconcile_with_annotations` promotes a TERMite `PARAMETER`-typed annotation from `question` to `filter` type | `src/oppp/stages/decompose.py`: `reconcile_with_annotations` function; `tests/test_stages.py`: test case with mocked PARAMETER annotation | MAJOR |
| EVAL-010 | REQ-006 | Requirement | Only `type=filter` components are passed to `translate_input_filter`; `type=question` components are routed only to facets/displayColumns logic | `src/oppp/pipeline.py` or `stages/translate.py`: filter condition on `component.type == "filter"` before translation | BLOCKER |
| EVAL-011 | REQ-007 | Requirement | `translate_input_filter` implements all six resolution steps: exact match, fuzzy match, LLM pool enrichment + retry, LLM closed-set selection, membership assertion/retry, invalid | `src/oppp/stages/translate.py`: six distinct resolution code paths; `tests/test_stages.py`: six test cases (one per step) | BLOCKER |
| EVAL-012 | REQ-008, CONST-3 | Constitution | `translate_input_filter` result is always a subset of the field's closed set; `[]` or `None` result marks translation `dropped=True` | `src/oppp/stages/translate.py`: membership check before any value is accepted; `tests/test_stages.py`: out-of-set assertion test | BLOCKER |
| EVAL-013 | REQ-009 | Requirement | `MachineSubquery.dropped=True` translations do not appear in the Stage-3A `MachineQuery.query` | `src/oppp/stages/aggregate.py`: filter on `not subquery.dropped` before assembly; `tests/test_stages.py`: invalid-translation exclusion test | MAJOR |
| EVAL-014 | REQ-010 | Requirement | `normalize` dispatches to `ClosedSetNormalizer` for `bucket="closed"`, `ConservativeNormalizer` for `bucket="open"`, and `DrugNormalizer` for `field="drugs"` | `src/oppp/normalize/strategies.py`: three classes present; `normalize/__init__.py`: dispatch logic; `tests/test_normalize.py`: three cases pass | MAJOR |
| EVAL-015 | REQ-011 | Requirement | Colloquial species group "Rodent" expands to member species (not widened to a higher-level class) | `src/oppp/taxonomy/index.py`: colloquial-group expansion logic; `tests/test_stages.py` or `test_taxonomy.py`: "Rodent" → member species list | MAJOR |
| EVAL-016 | REQ-011 | Requirement | "suntinib" fuzzy lookup resolves to "Sunitinib" without being dropped as invalid | `tests/test_stages.py`: drug fuzzy correction test case | MAJOR |
| EVAL-017 | REQ-012 | Requirement | Stage-3A `MachineQuery` has exactly one top-level constraint in `query` | `src/oppp/stages/aggregate.py`: validation assert; `tests/test_stages.py`: Stage-3 structural test | BLOCKER |
| EVAL-018 | REQ-012 | Requirement | PK service invariants (`concomitants` Fasted-or-empty, `tissueSpecific` Not-tissue-specific, `metabolitesEnantiomers` Not-metabolites/enantiomers) are applied in Stage-3A when not already present in the user query | `src/oppp/stages/aggregate.py`: invariant application code; `src/oppp/services/pk.py`: invariants list; `tests/test_stages.py`: invariants test | BLOCKER |
| EVAL-019 | REQ-013 | Requirement | `execute_count` returns `ExecutionResult` with `ok`, `count_total`, `status`, `error` fields | `src/oppp/execute.py`: `execute_count` function; `src/oppp/models.py`: `ExecutionResult` with all four fields; `tests/test_stages.py` or `test_pipeline.py`: mocked count test | MAJOR |
| EVAL-020 | REQ-014 | Requirement | `execute_rows` returns `RowExecutionResult` with `ok`, `count_total`, `datapoints`, `status`, `error`, `page_state` fields | `src/oppp/execute.py`: `execute_rows` function; `src/oppp/models.py`: `RowExecutionResult` with all six fields | MAJOR |
| EVAL-021 | REQ-014 | Requirement | `execute_rows` returns `ok=false` with `error` (no unhandled exception) when rows are unavailable | `src/oppp/execute.py`: exception handling around row fetch; `tests/test_pipeline.py`: row-unavailable test | MAJOR |
| EVAL-022 | REQ-015 | Requirement | `RuntimeClosedSet` is derived from sorted unique non-empty values for each deferred field in fetched `datapoints` | `src/oppp/models.py`: `RuntimeClosedSet` type; `src/oppp/stages/aggregate.py` or `pipeline.py`: derivation code; `tests/test_runtime_post_filters.py`: derivation test | MAJOR |
| EVAL-023 | REQ-016 | Requirement | `translate_runtime_filter` emits only values that are members of the runtime closed set | `src/oppp/stages/translate.py`: `translate_runtime_filter` membership check; `tests/test_runtime_post_filters.py`: runtime subset test | MAJOR |
| EVAL-024 | REQ-017 | Requirement | `apply_post_filters` with a valid selection keeps only datapoints whose field value is in `selected`; with an invalid selection leaves datapoints unchanged and adds a warning to issues | `src/oppp/stages/aggregate.py`: `apply_post_filters` function; `tests/test_runtime_post_filters.py`: valid and invalid cases | MAJOR |
| EVAL-025 | REQ-018 | Requirement | `count-only` execution (`fetch_rows=False`) remains usable independently of row mode | `src/oppp/pipeline.py`: `fetch_rows=False` branch does not call `execute_rows`; `tests/test_pipeline.py`: count-only test | MAJOR |
| EVAL-026 | REQ-019 | Requirement | `src/oppp/services/pk.py` defines all 16 PK fields with correct `bucket` values; no PK field names appear hardcoded in `stages/translate.py` or `stages/aggregate.py` | `services/pk.py`: 16 `FieldSpec` entries; grep for `"species"`, `"drugs"` etc. in `translate.py` and `aggregate.py` returns no hardcoded field names | MAJOR |
| EVAL-027 | REQ-020 | Requirement | `oppp run --help` output does not contain `--enhancer`, `--decomposer`, `--translator`, `--aggregator`, or `--normalizer` | `tests/test_cli.py`: asserts absence of these flags in help output | MAJOR |
| EVAL-028 | REQ-021 | Requirement | `src/oppp/ui/app.py` loads questions from `docs/PPPK.xlsx` (`PK_Query` sheet) | `ui/app.py`: openpyxl read of `docs/PPPK.xlsx`; `PK_Query` sheet referenced | MAJOR |
| EVAL-029 | REQ-021 | Requirement | `app.py` contains no `st.selectbox` or equivalent widget for stage backend or normalizer selection | `ui/app.py`: grep for `st.selectbox` with `enhancer`/`backend`/`normalizer`/`decomposer` labels returns nothing | MAJOR |
| EVAL-030 | REQ-022 | Requirement | `dag.py` exported stage list contains all seven labels: Stage -1, Stage 0, Stage 1, Stage 2A, Stage 3A, Stage 2B, Stage 3B, Stage 2C | `src/oppp/dag.py`: string constants or list with all seven stage names; `tests/test_dag.py`: assertion | MAJOR |
| EVAL-031 | REQ-023 | Requirement | `eval/harness.py` reads `docs/PPPK.xlsx` → `PK_Query` sheet; handles `Quety number` column (typo); iterates 47 rows | `src/oppp/eval/harness.py`: openpyxl read with sheet name `PK_Query`; handles `Quety number`; `tests/test_eval.py`: 47-row assertion | BLOCKER |
| EVAL-032 | REQ-023 | Requirement | Harness reports `valid_rate`, `executed_rate`, `exact_count`, `within_<tol>` metrics | `src/oppp/eval/harness.py`: four metric computations; `tests/test_eval.py`: metric assertions | MAJOR |
| EVAL-033 | REQ-024 | Requirement | `eval/per_step.py` exports Stage 0 entity set P/R function, Stage 1 field/type exact score function, Stage 1 fragment judge function, Stage 2 field name score function, Stage 3 structural compare function | `src/oppp/eval/per_step.py`: five exported functions; `tests/test_per_step_eval.py`: five test cases | MAJOR |
| EVAL-034 | REQ-025 | Requirement | Test suite covers "AUC or Cmax" → `parameter` OR-group regression case | `tests/test_stages.py`: test with `AUC or Cmax` input verifying boolean group `op="OR"` on `parameter` field | MAJOR |
| EVAL-035 | REQ-026, CONST-11 | Constitution | `pytest -q` passes with no `.env`, no network, no LLM credentials, no TERMite credentials | CI or local run: `pytest -q` exit code 0 without any `.env`; `tests/conftest.py`: fake fixtures present | BLOCKER |
| EVAL-036 | REQ-027, CONST-13 | Constitution | `.env.example` lists all 10 env var names with empty values; `.gitignore` excludes `.env` and `*.env`; `config.py` loads credentials only inside function calls | `.env.example`: 10 keys, no values; `.gitignore`: `.env` pattern; `config.py`: no top-level credential reads | BLOCKER |
| EVAL-037 | REQ-028 | Requirement | `eval/judge.py` exports `LLMJudge` with an injectable LLM client and `JudgeVerdict` Pydantic model with `verdict` (match/partial/miss) and `reason` fields | `src/oppp/eval/judge.py`: `LLMJudge` class accepting client param; `JudgeVerdict` with `verdict` enum and `reason`; `tests/test_per_step_eval.py`: fake judge test | MINOR |
| EVAL-038 | NFR-001 | Non-functional | `python3 -m compileall src/oppp` exits 0 | Run `python3 -m compileall src/oppp` and check exit code | BLOCKER |
| EVAL-039 | NFR-001 | Non-functional | `ruff check src tests` exits 0 | Run `ruff check src tests` and check exit code | MAJOR |
| EVAL-040 | NFR-001 | Non-functional | `ruff format --check src tests` exits 0 | Run `ruff format --check src tests` and check exit code | MAJOR |
| EVAL-041 | NFR-003, CONST-13 | Constitution | `import oppp` and `from oppp.models import PipelineResult` do not trigger LangChain, TERMite, Streamlit, matplotlib, or openpyxl imports | Python REPL: `import oppp; import sys; assert "langchain" not in sys.modules; assert "streamlit" not in sys.modules` | MAJOR |
| EVAL-042 | NFR-004 | Non-functional | `execute_rows` failure leaves `execute_count` usable; `pipeline.py` count-only path unaffected by row-fetch failure | `src/oppp/execute.py`: no exception propagation from `execute_rows`; `tests/test_pipeline.py`: row-fail + count-still-works test | MAJOR |
| EVAL-043 | NFR-005 | Non-functional | No public CLI command help text contains the words `noop`, `gazetteer`, `backend`, `enhancer` (as a flag name), `decomposer` (as a flag name), or `normalizer` (as a flag name) | `tests/test_cli.py`: asserts absence of these strings in help output; grep `cli.py` for these option names | MAJOR |
| EVAL-044 | CONST-1 | Constitution | `run_pipeline` signature has no parameter named `enhancer`, `decomposer`, `translator`, `aggregator`, or `normalizer` | `src/oppp/pipeline.py`: `run_pipeline` function signature | BLOCKER |
| EVAL-045 | CONST-4 | Constitution | Open-set fields (`parameter`, `parameterDisplay`, `studyGroup`, `age`, `dose`, `duration`) do not appear as hard closed-set `MATCH` constraints in Stage-3A assembly when `fetch_rows=True` | `src/oppp/stages/aggregate.py`: open-set fields deferred in row mode; or `pipeline.py`: open-set filter path branches on `fetch_rows` | MAJOR |
| EVAL-046 | CONST-6 | Constitution | `MachineQuery` is validated (structural check) before being treated as a successful query output | `src/oppp/stages/aggregate.py`: validation function called before returning `MachineQuery`; `tests/test_stages.py`: invalid-structure test produces issues | BLOCKER |
| EVAL-047 | CONST-7 | Constitution | Filters sharing a `BooleanGroup` with `op="OR"` are combined under an `OR` node in the final `MachineQuery`; filters with `op="AND"` under an `AND` node | `src/oppp/stages/aggregate.py`: boolean group assembly logic; `tests/test_stages.py`: AUC OR Cmax structural test | MAJOR |
| EVAL-048 | CONST-10 | Constitution | `stages/translate.py` contains no hardcoded PK field names; `stages/aggregate.py` reads invariants from `service.invariants` | `stages/translate.py`: grep for string literals `"species"`, `"drugs"`, `"route"` returns no field-specific branching; `aggregate.py`: `service.invariants` iterated | MAJOR |
| EVAL-049 | CONST-14 | Constitution | All four quality gates pass together (compile + ruff check + ruff format + pytest) | Run all four gates in sequence; all exit 0 | BLOCKER |

### Skeleton file existence

| ID | Source ref | Category | Criterion | Evidence | Severity |
|----|------------|----------|-----------|----------|----------|
| EVAL-050 | skeleton.md | Skeleton/Structure | `src/oppp/models.py` exists and is non-empty | File present at path; `wc -l` > 0 | BLOCKER |
| EVAL-051 | skeleton.md | Skeleton/Structure | `src/oppp/stages/enhance.py` exists | File present at path | BLOCKER |
| EVAL-052 | skeleton.md | Skeleton/Structure | `src/oppp/stages/decompose.py` exists | File present at path | BLOCKER |
| EVAL-053 | skeleton.md | Skeleton/Structure | `src/oppp/stages/translate.py` exists | File present at path | BLOCKER |
| EVAL-054 | skeleton.md | Skeleton/Structure | `src/oppp/stages/aggregate.py` exists | File present at path | BLOCKER |
| EVAL-055 | skeleton.md | Skeleton/Structure | `src/oppp/execute.py` exists | File present at path | BLOCKER |
| EVAL-056 | skeleton.md | Skeleton/Structure | `src/oppp/eval/harness.py` exists | File present at path | BLOCKER |
| EVAL-057 | skeleton.md | Skeleton/Structure | `src/oppp/eval/per_step.py` exists | File present at path | MAJOR |
| EVAL-058 | skeleton.md | Skeleton/Structure | `src/oppp/eval/judge.py` exists | File present at path | MAJOR |
| EVAL-059 | skeleton.md | Skeleton/Structure | `src/oppp/services/pk.py` exists | File present at path | BLOCKER |
| EVAL-060 | skeleton.md | Skeleton/Structure | `tests/conftest.py` exists | File present at path | BLOCKER |
| EVAL-061 | skeleton.md | Skeleton/Structure | `tests/test_runtime_post_filters.py` exists | File present at path | MAJOR |
| EVAL-062 | skeleton.md | Skeleton/Structure | `tests/test_cli.py` exists | File present at path | MAJOR |
| EVAL-063 | skeleton.md | Skeleton/Structure | `tests/test_dag.py` exists | File present at path | MINOR |
| EVAL-064 | skeleton.md | Skeleton/Structure | `.env.example` exists at repo root | File present at `.env.example` | MAJOR |

## Coverage Map

| Source item | Covered by |
|-------------|------------|
| REQ-001 | EVAL-001, EVAL-002 |
| REQ-002 | EVAL-003, EVAL-004 |
| REQ-003 | EVAL-005, EVAL-006 |
| REQ-004 | EVAL-007, EVAL-008 |
| REQ-005 | EVAL-009 |
| REQ-006 | EVAL-010 |
| REQ-007 | EVAL-011 |
| REQ-008 | EVAL-012 |
| REQ-009 | EVAL-013 |
| REQ-010 | EVAL-014 |
| REQ-011 | EVAL-015, EVAL-016 |
| REQ-012 | EVAL-017, EVAL-018 |
| REQ-013 | EVAL-019 |
| REQ-014 | EVAL-020, EVAL-021 |
| REQ-015 | EVAL-022 |
| REQ-016 | EVAL-023 |
| REQ-017 | EVAL-024 |
| REQ-018 | EVAL-025 |
| REQ-019 | EVAL-026 |
| REQ-020 | EVAL-027 |
| REQ-021 | EVAL-028, EVAL-029 |
| REQ-022 | EVAL-030 |
| REQ-023 | EVAL-031, EVAL-032 |
| REQ-024 | EVAL-033 |
| REQ-025 | EVAL-034 |
| REQ-026 | EVAL-035 |
| REQ-027 | EVAL-036 |
| REQ-028 | EVAL-037 |
| NFR-001 | EVAL-038, EVAL-039, EVAL-040 |
| NFR-002 | EVAL-035 |
| NFR-003 | EVAL-041 |
| NFR-004 | EVAL-042 |
| NFR-005 | EVAL-043 |
| CONST-1 (fixed path) | EVAL-044 |
| CONST-2 (TERMite mandatory) | EVAL-005, EVAL-006 |
| CONST-3 (closed sets) | EVAL-012 |
| CONST-4 (open-field deferral) | EVAL-045 |
| CONST-5 (Stage 1 routes only) | EVAL-007 |
| CONST-6 (typed contracts) | EVAL-046 |
| CONST-7 (boolean intent) | EVAL-047 |
| CONST-8 (normalization fixed) | EVAL-014 |
| CONST-9 (hierarchy reusable) | EVAL-015 |
| CONST-10 (service config) | EVAL-048 |
| CONST-11 (hermetic tests) | EVAL-035 |
| CONST-12 (per-step evaluation) | EVAL-033 |
| CONST-13 (lazy secrets) | EVAL-036, EVAL-041 |
| CONST-14 (quality gates) | EVAL-049 |
| CONTRACT-EXPANDED-QUERY | EVAL-003 |
| CONTRACT-ENHANCED-QUERY | EVAL-005 |
| CONTRACT-COMPONENT | EVAL-008 |
| CONTRACT-CLOSED-SET | EVAL-012 |
| CONTRACT-CLOSED-SET-TRANSLATION | EVAL-011, EVAL-012 |
| CONTRACT-GROUNDING | EVAL-019 |
| CONTRACT-SUBQUERY | EVAL-013 |
| CONTRACT-MACHINE-QUERY | EVAL-017, EVAL-046 |
| CONTRACT-EXECUTION-COUNT | EVAL-019 |
| CONTRACT-EXECUTION-ROWS | EVAL-020 |
| CONTRACT-RUNTIME-CLOSED-SET | EVAL-022 |
| CONTRACT-POST-FILTER | EVAL-024 |
| CONTRACT-SERVICE-CONFIG | EVAL-026 |
| CONTRACT-GOLD-SET | EVAL-031 |
| CONTRACT-FIXED-STAGE-PATH | EVAL-044 |
| CONTRACT-NORMALIZER | EVAL-014 |
| skeleton.md files | EVAL-050 through EVAL-064 |

## Out of Scope
- **Safety and RTB service configs** (`services/safety.py`, `services/rtb.py`): inactive product scope in v0.1; files must compile but are not evaluated for field correctness.
- **LangGraph graph correctness** (`build_langgraph()`): the LangGraph wrapper is a convenience surface over the same fixed stages; its graph topology is not separately evaluated.
- **`oppp dag` PNG rendering** (matplotlib): the `viz` extra is evaluated only for the fixed stage label list, not for visual rendering quality.
- **PharmaPendium API live count accuracy**: `Expected Count` values in `docs/PPPK.xlsx` can drift with database updates; count proximity is a signal, not a hard gate.
- **`docs/PPPK.xlsx` `PP_PK_content` and `Parameter_PK_Taxo_new` sheets**: informational; the harness only reads `PK_Query`.
