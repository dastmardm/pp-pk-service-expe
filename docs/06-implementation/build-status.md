# Build status (v0.1)

The redesign is implemented as the `oppp` package under [src/oppp/](../../src/oppp/).
The deterministic core runs offline; the LLM/orchestration/UI layers are wired
behind lazy imports and optional extras.

## What's implemented

| Area | Module | Notes |
|------|--------|-------|
| Pydantic contracts | [models.py](../../src/oppp/models.py) | `Component` (`type` filter/question + `reason`), `MachineSubquery`, `MachineQuery`, grounding, validation. |
| Pluggable registry | [registry.py](../../src/oppp/registry.py) | Every step resolved by name from config. |
| Taxonomy grounding | [taxonomy/index.py](../../src/oppp/taxonomy/index.py) | CSV load, exact + fuzzy (rapidfuzz) lookup, class→members hierarchy expansion, gazetteer membership. |
| Misspelling normalizer | [normalize/](../../src/oppp/normalize/) | `noop` (default) + `fuzzy`; conservative on open fields. |
| Stage 1 — decompose | [stages/decompose.py](../../src/oppp/stages/decompose.py) | `gazetteer` (offline; exact **+ fuzzy** taxonomy detection), `termite` (SciBite NER, lazy), `llm` (LangChain structured output, lazy). |
| Stage 2 — translate | [stages/translate.py](../../src/oppp/stages/translate.py) | closed-vocab grounding + expansion, open→REGEX, enum, boolean, year→RANGE. |
| Stage 3 — aggregate | [stages/aggregate.py](../../src/oppp/stages/aggregate.py) | boolean tree, entityFilters routing, facets/displayColumns, validation, service invariants hook. |
| Service config | [services/safety.py](../../src/oppp/services/safety.py) | Safety field map, buckets, facet allow-list, TERMite type map. |
| Pipeline | [pipeline.py](../../src/oppp/pipeline.py) | sequential runner + optional LangGraph graph (same signature). |
| Execution | [execute.py](../../src/oppp/execute.py) | POST machine query to the PP API, read `countTotal`. |
| Evaluation | [eval/harness.py](../../src/oppp/eval/harness.py) | **count-based**: compares executed `countTotal` to gold `s`. |
| CLI | [cli.py](../../src/oppp/cli.py) | `run`, `decompose`, `field`, `lookup`, `services`, `eval`. |
| UI | [ui/app.py](../../src/oppp/ui/app.py) | Streamlit stage-by-stage inspector. |
| Tests | [tests/](../../tests/) | taxonomy, pipeline, eval (offline). |

## How to run

```bash
# environment (uv preferred; pip shown as fallback)
uv venv && uv pip install -e '.[dev]'        # or: python -m venv .venv && .venv/bin/pip install -e '.[dev]'

# full pipeline on one question
oppp run "What are the ADRs of Sunitinib in human" --normalizer fuzzy

# isolate a single stage (the design's per-step isolation)
oppp decompose "NOAEL for sunitinib in rats"
oppp field drugs "suntinib" --normalizer fuzzy      # Stage 2 on one fragment
oppp lookup species Rodent --expand                 # grounding layer

# evaluate against the gold set by expected count (column s)
oppp eval --show-cases                  # executes queries vs the API
oppp eval --no-execute                  # offline: validity only

# UI / tests / lint
streamlit run src/oppp/ui/app.py
pytest -q
ruff check src tests
```

## Evaluation metric

Per [docs/05](../05-evaluation/gold-set-and-metrics.md), the harness scores by
**result-count accuracy**: translate → execute → read `countTotal` → compare to
the expected `s`. Reported: `valid_rate`, `executed_rate`, `exact_count`,
`within_<tol>`.

Baseline with the offline `gazetteer` backend is intentionally modest — it nails
clean cases (e.g. Q1 Sunitinib/Human = 4300 exact, Q10 = 43 exact) and diverges
on the cases the docs flagged as open questions. Those drive the next steps.

## Entity detection (Stage 1) — recall fix

Misspelled and synonym entities used to be dropped because detection was
exact-match only and the misspelling normalizer lives in Stage 2 (it can only
correct a fragment *already routed* to a field). Two fixes:

- **Fuzzy gazetteer detection** (offline, default on): a second pass over
  unclaimed single tokens fuzzy-matches the taxonomies (`fuzz.ratio`, cutoff 82)
  so e.g. `suntinib → Sunitinib`, `cabozantininb → Cabozantinib` are detected.
  Precision guards (single-token, length ≥ 6, substring rejection) keep ordinary
  words like "related"/"toxicity" from firing — see `_fuzzy_matches`.
- **TERMite backend** (`--decomposer termite`): SciBite NER resolves synonyms,
  brand names and variants to preferred labels (`homo sapiens → Human`,
  `Columvi → Glofitamab`) that no CSV gazetteer can. Seeds entities, then falls
  back to the fuzzy gazetteer for gaps + patterns/questions. Needs the SciBite
  toolkit + `TERMITE_*` creds in `.env`.

Synonyms absent from the CSVs (e.g. `homo sapiens`) still require the `termite`
or `llm` backend; the offline gazetteer only knows preferred labels.

## Known limitations (next steps)

- **MedDRA effect rollups** and **drug-class / species-class** detection are not
  done offline (Q2/Q4/Q8/Q23…), causing under/over-counting — the documented
  open questions in [architecture.md](../03-proposed-design/architecture.md#open-questions).
- **`targets`** has no shipped CSV, so it is best-effort/open.
- **TERMite backend** is implemented but unverified live here (no creds/network
  in this environment); the gazetteer and llm paths are exercised.
- **DSPy** modules and the **PK/RTB** service configs are scaffolded by the
  architecture but not yet implemented (Safety only in v0.1).
- LLM/TERMite backends require their extras + `.env` credentials.
