# Build status (v0.1)

The redesign is implemented as the `oppp` package under [src/oppp/](../../src/oppp/).
The deterministic core runs offline; the LLM/orchestration/UI layers are wired
behind lazy imports and optional extras.

## What's implemented

| Area | Module | Notes |
|------|--------|-------|
| Pydantic contracts | [models.py](../../src/oppp/models.py) | `EnhancedQuery`, `Component` (`type` filter/question + `reason`), `MachineSubquery`, `MachineQuery`, grounding, validation. |
| Pluggable registry | [registry.py](../../src/oppp/registry.py) | Every step resolved by name from config. |
| Taxonomy grounding | [taxonomy/index.py](../../src/oppp/taxonomy/index.py) | CSV load, exact + fuzzy (RapidFuzz) lookup, singularization, class labels, candidate windows, MedDRA family expansion, gazetteer membership. |
| Misspelling normalizer | [normalize/](../../src/oppp/normalize/) | `noop` + `fuzzy`; CLI defaults to `fuzzy`, while `run_pipeline()` defaults to `noop`. Conservative on open-set fields. |
| Stage -1 — expand | [stages/expand.py](../../src/oppp/stages/expand.py) | `llm` (default in CLI/library) + `noop`; rewrites for clarity and abbreviation expansion, preserving the original query. |
| Stage 0 — enhance | [stages/enhance.py](../../src/oppp/stages/enhance.py) | `termite` + `noop`; `oppp run` defaults to `termite`, while `get_enhancer()`/`run_pipeline()` default to `noop`. SciBite NER is lazy and records preferred labels plus public synonyms. |
| Stage 1 — decompose | [stages/decompose.py](../../src/oppp/stages/decompose.py) | `llm` (LangChain structured output, lazy; **vocab-free**) + `gazetteer` (offline double; exact **+ fuzzy** taxonomy detection). |
| Stage 2 — translate | [stages/translate.py](../../src/oppp/stages/translate.py) | closed-set grounding + class/effect expansion, enum, boolean, year→RANGE, LLM term selection, LLM synonym/closed-window fallback, and direct open-field `MATCH`/`REGEX` translation. |
| Stage 3 — aggregate | [stages/aggregate.py](../../src/oppp/stages/aggregate.py) | dropped-filter handling, API constraint budget collapse, boolean tree, entityFilters routing, facets/displayColumns, validation, service invariants, optional zero-count open-filter probe. |
| Service config | [services/](../../src/oppp/services/) | Safety, PK, and RTB field maps, buckets, facet allow-lists, TERMite type maps, invariants, and RTB `where_clause` serializer. |
| Pipeline | [pipeline.py](../../src/oppp/pipeline.py) | sequential runner + optional LangGraph graph (same signature). |
| Execution | [execute.py](../../src/oppp/execute.py) | POST machine query to the PP API and read `data.countTotal`; full rows are not fetched. |
| Evaluation | [eval/](../../src/oppp/eval/) | count-based harness, per-step comparators, gold-vs-agent filter diff, typed LLM judge, CSV/XLSX report export. |
| CLI | [cli.py](../../src/oppp/cli.py) | `run`, `enhance`, `decompose`, `field`, `aggregate`, `lookup`, `services`, `dag`, `eval`. |
| UI | [ui/app.py](../../src/oppp/ui/app.py) | Streamlit stage-by-stage inspector with service/enhancer/decomposer/translator/aggregator/normalizer selectors, gold-set picker, Stage 0-3 panels, payload display, and optional count execution. |
| Tests | [tests/](../../tests/) | taxonomy, pipeline, eval (offline). |

## How to run

```bash
# environment (uv preferred; pip shown as fallback)
uv venv && uv pip install -e '.[dev]'        # or: python -m venv .venv && .venv/bin/pip install -e '.[dev]'

# full pipeline on one question
oppp run "What are the ADRs of Sunitinib in human" --normalizer fuzzy

# isolate a single stage (the design's per-step isolation)
oppp enhance "ADRs of Columvi in human" --backend termite   # Stage 0 (optional TERMite)
oppp decompose "NOAEL for sunitinib in rats"                 # Stage 1
oppp field drugs "suntinib" --normalizer fuzzy               # Stage 2 on one fragment
oppp aggregate "neutropenia or thrombocytopenia in human"    # Stage 3 (offline upstream)
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

Baseline with the offline `gazetteer` backend is intentionally modest. It handles
clean preferred-label cases and many taxonomy expansions, and diverges where a
case depends on live TERMite recognition, model-backed disambiguation, or
row-level runtime closed-set post-filtering.

## Entity detection — recall fix

Misspelled and synonym entities used to be dropped because detection was
exact-match only and the misspelling normalizer lives in Stage 2 (it can only
correct a fragment *already routed* to a field). Two fixes:

- **Fuzzy gazetteer detection** (offline, default on): a second pass over
  unclaimed single tokens fuzzy-matches the taxonomies (`fuzz.ratio`, cutoff 82)
  so e.g. `suntinib → Sunitinib`, `cabozantininb → Cabozantinib` are detected.
  Precision guards (single-token, length ≥ 6, substring rejection) keep ordinary
  words like "related"/"toxicity" from firing — see `_fuzzy_matches`.
- **TERMite Stage 0 enhancer** (`--enhancer termite`): SciBite NER resolves
  synonyms, brand names and variants to preferred labels (`homo sapiens → Human`,
  `Columvi → Glofitamab`) that no CSV gazetteer can, and prepends them as a hints
  block ahead of Stage 1. Needs the SciBite toolkit + `TERMITE_*` creds in `.env`.

Synonyms absent from the CSVs (e.g. `homo sapiens`) still require the `termite`
enhancer or the `llm` decomposer; the offline gazetteer only knows preferred labels.

## Current limitations

- **Row-level post-filtering is not wired.** Execution reads `countTotal` only,
  so runtime closed sets derived from fetched datapoints are represented in the
  design docs but not materialized by the v0.1 execution layer.
- **Open-set filters are guarded by probes.** `parameterComment`, `studyGroup`,
  `ages`, `dose`, and similar fields are emitted as direct `MATCH`/`REGEX`
  constraints. Live runs may drop a filter whose isolated count is confirmed `0`.
- **`targets` has no input closed set in `inputs/`.** The current Safety path
  routes it through `DrugsTargets` and uses a TERMite preferred label when
  available; entity-routed filters are not zero-count probed.
- **TERMite Stage 0 enhancer** is implemented but unverified live here (no
  creds/network in this environment); the gazetteer and llm paths are exercised.
- **DSPy optimization modules are not present in `src/oppp/`.** The pipeline uses
  Pydantic structured outputs and registries; prompt optimization remains a
  convention described in [tech-stack.md](tech-stack.md).
- LLM/TERMite backends require their extras + `.env` credentials.
