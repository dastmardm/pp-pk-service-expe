# Requirements

Derived from `specs/product.md` (capabilities CAP-1…CAP-9) and `specs/technical.md`
(contracts) / `specs/constitution.md` (principles).

## Functional Requirements

| ID | Priority | Statement |
|----|----------|-----------|
| REQ-001 | MUST | Given a natural-language question and a service, produce a `MachineQuery` payload for the Safety service. *(CAP-1)* |
| REQ-002 | MUST | The produced `query` tree has exactly one top-level constraint; every `OR`/`AND` node has ≥2 children and every `NOT` exactly 1; all operators are from the allowed set and upper-case. *(CAP-1, CONTRACT-MACHINE-QUERY)* |
| REQ-003 | MUST | A Stage-0 enhancer exists, defaults to `noop`, and offers a `termite` backend; the pipeline runs end-to-end with the `noop` enhancer. *(CAP-2, CONST-7)* |
| REQ-004 | MUST | Stage 1 decomposes the question into `Component`s each carrying `field`, `nl_fragment`, `type` (`filter`\|`question`), and a one-sentence `reason`; the production `llm` decomposer is vocab-free. *(CAP-3, CONST-2)* |
| REQ-005 | MUST | Only `filter` components are translated into machine subqueries; `question` components are carried forward and inform facets/display columns. *(CAP-3, CAP-6)* |
| REQ-006 | MUST | For a closed-vocabulary field, Stage 2 grounds the value against that field's taxonomy and never emits a value absent from it. *(CAP-4, CONST-1)* |
| REQ-007 | MUST | When the user names a class or roll-up, Stage 2 expands it along the taxonomy hierarchy (`parent_id`/`parent_name`) to the intended member/term set. *(CAP-4, CONST-6)* |
| REQ-008 | MUST | Each grounded closed-vocabulary subquery carries an auditable `Grounding` block (matched rows, `expanded_from`, confidence). *(CAP-4, CONTRACT-GROUNDING)* |
| REQ-009 | MUST | Open fields receive a model-decided value rendered as the appropriate operator (`REGEX` for free text, `RANGE` for numeric, `MATCH` for short qualifiers). *(CAP-4)* |
| REQ-010 | SHOULD | A misspelling normalizer runs on the fragment before value production, defaults to `noop`, offers `fuzzy`, and is conservative on open fields. *(CAP-5)* |
| REQ-011 | MUST | Stage 3 combines per-field filters with the correct boolean structure both within a field (per Stage-1 boolean group) and across fields (default `AND`). *(CAP-6, CONST-5)* |
| REQ-012 | MUST | Stage 3 routes fields that require a linked entity into `entityFilters` per the service config, leaving direct fields in `query`. *(CAP-6)* |
| REQ-013 | MUST | Stage 3 attaches `facets`/`displayColumns` derived from `question` components and the service facet allow-list. *(CAP-6)* |
| REQ-014 | MUST | Stage 3 applies the service's always-on invariants via the service `invariants` hook. *(CAP-6, CONST-12)* |
| REQ-015 | MUST | Stage 3 validates the assembled query and records `ValidationIssue`s; `PipelineResult.ok` is false when any error-level issue is present. *(CAP-6, CONST-3)* |
| REQ-016 | MUST | Every stage is selectable by name from a registry and via a corresponding CLI flag/subcommand. *(CAP-7, CONST-8)* |
| REQ-017 | MUST | The full pipeline runs with the offline doubles (`noop`/`gazetteer`/`deterministic`) making no LLM call and no network call. *(CAP-7, CONST-8)* |
| REQ-018 | MUST | Each stage is runnable in isolation from the CLI (`enhance`, `decompose`, `field`, `aggregate`). *(CAP-7)* |
| REQ-019 | MUST | An evaluation harness scores against the per-field gold set by comparing the executed `countTotal` to the expected `s`, reporting valid / executed / exact / within-tolerance rates. *(CAP-8, CONTRACT-GOLD-PERFIELD)* |
| REQ-020 | SHOULD | A per-step evaluation scores each stage's output against its column in `docs/sme_stage_cases.csv` with a per-step comparator. *(CAP-8, CONTRACT-GOLD-PERSTEP)* |
| REQ-021 | SHOULD | Free-text steps (Stage-1 fragment, Stage-2 open-field pattern, Stage-3 structure tie-break) are scored by a constrained LLM-as-judge returning a typed verdict. *(CAP-8, CONST-9)* |
| REQ-022 | MUST | An interactive UI runs a question through the pipeline and displays each stage's intermediate output. *(CAP-9)* |
| REQ-023 | SHOULD | The UI lets the user select each stage's backend and pick a question from the gold set. *(CAP-9)* |
| REQ-024 | MUST | On a closed-vocabulary no-match, the system surfaces the gap rather than emitting an invented value. *(CAP-1, CONST-1)* |
| REQ-025 | MUST | Credentials are read only when a model/entity backend is invoked; the deterministic core requires none. *(CONST-10)* |
| REQ-026 | MUST | Typed Pydantic contracts are exchanged at every stage boundary. *(CONST-3)* |
| REQ-027 | MUST NOT | The system must not commit `.env` or any credential file. *(CONST-10)* |

## Non-Functional Requirements

| ID | Statement (measurable) |
|----|------------------------|
| NFR-001 | The default test suite (`pytest -q`) passes with no network access and no model credentials present. |
| NFR-002 | `ruff check src tests` and `ruff format --check src tests` report no findings. |
| NFR-003 | The deterministic core (taxonomy lookup, decomposition via `gazetteer`, translation via `deterministic`, aggregation via `deterministic`, validation, eval bookkeeping) imports and runs without the `llm`, `ui`, or `viz` extras installed. |
| NFR-004 | A single offline `oppp run` on one question completes in well under 5 s on a developer laptop (in-memory lookups; no external calls). |
| NFR-005 | Heavy dependencies (`langchain*`, `dspy`, `openai`, `streamlit`, `matplotlib`) are imported lazily, so absence of an extra never breaks an unrelated code path. |

## Constraints

- The PharmaPendium search service, TERMite, and the model provider are external;
  their availability and credentials are given, not controlled here.
- The controlled-vocabulary tables and the per-field gold set are provided under
  `inputs/`; the per-step gold set is provided under `docs/`.
- Only the **Safety** service is in realised scope; PK and RTB are designed-for.
- Result counts drift as the underlying database updates, so count-based metrics
  are a tolerance-banded signal, not a hard gate.

## Non-Goals

- Not a general conversational assistant; it only emits machine queries.
- Does not summarise, rank, or post-process the records the query retrieves.
- Does not curate or author the controlled vocabularies or gold sets.
- Does not implement PK/RTB service configs or the DSPy-optimised prompts in the
  current realised scope.

## Acceptance Criteria

- **REQ-001/002/015:** `oppp run "<question>"` (offline doubles) prints a payload
  whose `query` has one top-level constraint and reports `ok=true` with no
  error-level issues for a clean Safety question.
- **REQ-003:** `oppp enhance "<q>"` with `--backend noop` returns the query
  unchanged with no annotations; the default pipeline uses `noop`.
- **REQ-004:** `oppp decompose "<q>"` emits `Component`s with `field`, `type`,
  `reason`; the `llm` backend performs no taxonomy lookup.
- **REQ-006/024:** `oppp field <closed-field> "<unknown term>"` returns no
  fabricated value (empty/flagged), and a known term resolves to a taxonomy label.
- **REQ-007/008:** `oppp lookup <taxonomy> <class> --expand` returns the class's
  members; a class subquery's `grounding.expanded_from` is set.
- **REQ-011:** A question with "X or Y" in one field yields an `OR` node of two
  expanded MATCHes; a cross-field question yields a top-level `AND`.
- **REQ-016/017/018:** `oppp run … --decomposer gazetteer --translator
  deterministic --aggregator deterministic --no-execute` completes with no network
  call; each of `enhance`/`decompose`/`field`/`aggregate` runs standalone.
- **REQ-019:** `oppp eval --no-execute` reports a `valid_rate`; with execution it
  reports `exact_count` / `within_<tol>` against `s`.
- **REQ-022:** Launching the UI and translating a question shows Stage-1/2/3
  outputs.
- **REQ-025/027:** Running the offline path with no `.env` present succeeds; `.env`
  is git-ignored and never staged.
