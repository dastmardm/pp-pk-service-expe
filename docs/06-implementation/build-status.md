# Build status (v0.1)

The redesign is implemented as the `oppp` package under [src/oppp/](../../src/oppp/).
The fixed production path runs LLM expansion, required TERMite enhancement, LLM
decomposition, grounded translation, and LLM aggregation. LLM, TERMite,
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
| Stage 2 — translate | [stages/translate.py](../../src/oppp/stages/translate.py) | closed-set grounding + class/effect expansion, enum, boolean, year→RANGE, LLM term selection, LLM synonym/closed-window fallback, and direct open-field `MATCH`/`REGEX` translation. |
| Stage 3 — aggregate | [stages/aggregate.py](../../src/oppp/stages/aggregate.py) | dropped-filter handling, API constraint budget collapse, boolean tree, entityFilters routing, facets/displayColumns, validation, service invariants, and zero-count open-filter probing. |
| Service config | [services/](../../src/oppp/services/) | PK field map, buckets, facet allow-list, TERMite type map, and service invariants. |
| Pipeline | [pipeline.py](../../src/oppp/pipeline.py) | sequential runner + LangGraph graph over the same fixed stages. |
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
the expected `s`. Reported: `valid_rate`, `executed_rate`, `exact_count`,
`within_<tol>`.

The evaluation harness keeps each stage's typed output so failures can be traced
to TERMite recognition, decomposition, closed-set translation, aggregation, API
execution, or row-level runtime closed-set post-filtering.

## Entity detection — recall fix

Misspelled and synonym entities used to be dropped because detection was
exact-match only and the misspelling normalizer lives in Stage 2 (it can only
correct a fragment *already routed* to a field). Two fixes:

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

## Current limitations

- **Row-level post-filtering is not wired.** Execution reads `countTotal` only,
  so runtime closed sets derived from fetched datapoints are represented in the
  design docs but not materialized by the v0.1 execution layer.
- **Open-set filters are guarded by probes.** `parameterComment`, `studyGroup`,
  `ages`, `dose`, and similar fields are emitted as direct `MATCH`/`REGEX`
  constraints. Live runs may drop a filter whose isolated count is confirmed `0`.
- **`parameter` and `parameterDisplay` have no input closed set in `inputs/`.** These open-set fields are translated as direct `MATCH` constraints in v0.1 and may be guarded by zero-count probing.
- **DSPy optimization modules are not present in `src/oppp/`.** The pipeline uses
  Pydantic structured outputs and fixed stage contracts; prompt optimization remains a
  convention described in [tech-stack.md](tech-stack.md).
- LLM and TERMite integrations require their extras + `.env` credentials.
