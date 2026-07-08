# Build status

The translator is implemented as the `oppp` package under [src/oppp/](../../src/oppp/).
The fixed production path runs LLM expansion, required TERMite enhancement, LLM
decomposition, grounded closed-set tool translation, and LLM aggregation. LLM, TERMite,
orchestration, and UI dependencies are loaded lazily by the surfaces that need
them.

## What's implemented

| Area | Module | Notes |
|------|--------|-------|
| Pydantic contracts | [models.py](../../src/oppp/models.py) | `EnhancedQuery`, `Component` (`type` filter/question + `reason`), `MachineSubquery`, `MachineQuery`, grounding, validation. |
| Pipeline runner | [pipeline.py](../../src/oppp/pipeline.py) | Fixed stage order with typed intermediate artifacts. |
| Taxonomy grounding | [taxonomy/index.py](../../src/oppp/taxonomy/index.py) | CSV load, exact + fuzzy (RapidFuzz) lookup, singularization, class labels, candidate windows, hierarchy expansion, and taxonomy membership checks. |
| Misspelling normalizer | [normalize/](../../src/oppp/normalize/) | Fuzzy closed-set normalization plus conservative open-set cleanup. |
| Stage -1 — expand | [stages/expand.py](../../src/oppp/stages/expand.py) | LLM rewrite for clarity and abbreviation expansion, preserving the original query. |
| Stage 0 — enhance | [stages/enhance.py](../../src/oppp/stages/enhance.py) | Required SciBite TERMite NER records preferred labels plus public synonyms. |
| Stage 1 — decompose | [stages/decompose.py](../../src/oppp/stages/decompose.py) | LLM structured output, seeded by TERMite annotations and kept **vocab-free** for value selection. |
| Stage 2 — translate | [stages/translate.py](../../src/oppp/stages/translate.py) | closed-set grounding + class/hierarchy expansion, enum, boolean, year→RANGE, LLM term selection, LLM synonym/closed-window fallback, and direct open-field `MATCH`/`REGEX` translation. |
| Stage 3 — aggregate | [stages/aggregate.py](../../src/oppp/stages/aggregate.py) | dropped-filter handling, API constraint budget collapse, boolean tree, entityFilters routing, facets/displayColumns, validation, service invariants, and zero-count open-filter probing. |
| Service config | [services/](../../src/oppp/services/) | PK field map, buckets, facet allow-list, TERMite type map, and service invariants. |
| Execution | [execute.py](../../src/oppp/execute.py) | POST machine query to the PP API and read `data.countTotal`; full rows are not fetched. |
| Evaluation | [eval/](../../src/oppp/eval/) | count-based harness, per-step comparators, gold-vs-agent filter diff, typed LLM judge, CSV/XLSX report export. |
| CLI | [cli.py](../../src/oppp/cli.py) | `run`, `enhance`, `decompose`, `field`, `aggregate`, `lookup`, `services`, `dag`, `eval`. |
| UI | [ui/app.py](../../src/oppp/ui/app.py) | Streamlit stage-by-stage inspector with service selection, gold-set picker, Stage 0-3 panels, payload display, and count execution control. |
| Tests | [tests/](../../tests/) | taxonomy, pipeline, eval (offline). |

## How to run

```bash
# environment (uv preferred; pip shown as fallback)
uv venv && uv pip install -e '.[dev]'        # or: python -m venv .venv && .venv/bin/pip install -e '.[dev]'

# full pipeline on one question
oppp run "AUC of Sunitinib in human after oral administration"
oppp run "AUC of Sunitinib in human after oral administration" --payload-only

# isolate a single stage (the design's per-step isolation)
oppp enhance "AUC of Sunitinib in human after oral"          # Stage 0 TERMite
oppp decompose "AUC of sunitinib in human after oral"        # Stage 1
oppp field drugs "suntinib"                                  # Stage 2 on one fragment
oppp aggregate "AUC or Cmax of sunitinib in rat"             # Stage 3
oppp lookup species Rodent --expand                          # grounding layer

# evaluate against the gold set by expected count (column s)
oppp eval --show-cases                  # executes queries vs the API
oppp eval --no-execute                  # offline: validity only

# UI / tests / lint
streamlit run src/oppp/ui/app.py
pytest -q
ruff check src tests
```

See [operations.md](operations.md) for install extras, `.env` variables, and the
execution model.

## Evaluation metric

Per [docs/05](../05-evaluation/gold-set-and-metrics.md), the harness scores by
**result-count accuracy**: translate → execute → read `countTotal` → compare to
the `Expected Count` column in `PPPK.xlsx`. Reported: `valid_rate`, `executed_rate`, `exact_count`,
`within_<tol>`.

The evaluation harness keeps each stage's typed output so failures can be traced
to TERMite recognition, decomposition, closed-set translation, open-set direct
constraints, aggregation, or API execution.

The implementation includes these evaluation surfaces:

- **Gold dataset.** [PPPK.xlsx](../PPPK.xlsx) `PK_Query` sheet with 47 PK
  questions and expected counts, read by [eval/harness.py](../../src/oppp/eval/harness.py).
- **CLI harness.** `oppp eval` runs translate -> execute when requested -> compare
  `countTotal` to `Expected Count`, with CSV/XLSX report export.
- **Per-step comparators.** [eval/per_step.py](../../src/oppp/eval/per_step.py)
  scores TERMite labels, decomposition routing/type pairs, translated field names,
  and final machine-query structure.
- **Typed judge.** [eval/judge.py](../../src/oppp/eval/judge.py) exposes `LLMJudge`
  and `JudgeVerdict` for fragment, open-pattern, and structure tie-breaks. Tests
  inject a fake client so the judge contract stays hermetic.
- **PK-focused coverage.** The gold set targets PK questions on the
  PharmaPendium API; evaluation coverage is complemented by targeted service
  configuration tests.

## Entity detection — recall fix

Misspelled and synonym entities are handled before Stage 2 normalization by two
entity-detection paths:

- **Fuzzy taxonomy detection**: a second pass over unclaimed single tokens
  fuzzy-matches the taxonomies (`fuzz.ratio`, cutoff 82)
  so e.g. `suntinib → Sunitinib`, `cabozantininb → Cabozantinib` are detected.
  Precision guards (single-token, length ≥ 6, substring rejection) keep ordinary
  words like "related"/"toxicity" from firing — see `_fuzzy_matches`.
- **Required TERMite Stage 0 enhancer**: SciBite NER resolves synonyms, brand
  names and variants to preferred labels (`homo sapiens → Human`,
  `Columvi → Glofitamab`) and prepends them as a hints block ahead of Stage 1.
  It needs the SciBite toolkit + `TERMITE_*` creds in `.env`.

Synonyms absent from the CSVs (e.g. `homo sapiens`) are expected to come from
TERMite labels or the LLM decomposition/translation path, then be grounded before
they can affect the machine query.

## Limitations

- **Open-set filters are guarded by probes.** `parameter`, `parameterDisplay`, `studyGroup`,
  `age`, `dose`, `duration`, and similar fields are emitted as direct `MATCH`/`REGEX`
  constraints. Live runs may drop a filter whose isolated count is confirmed `0`.
- **`parameter` and `parameterDisplay` have no input closed set in `inputs/`.** These open-set fields are translated as direct `MATCH` constraints and may be guarded by zero-count probing.
- **DSPy optimization modules are not present in `src/oppp/`.** The pipeline uses
  Pydantic structured outputs and fixed stage contracts.
- LLM and TERMite integrations require their extras + `.env` credentials.
