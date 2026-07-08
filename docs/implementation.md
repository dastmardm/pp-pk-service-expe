# Implementation

The implementation lives in `src/oppp/` as a Python package with a Typer CLI,
Streamlit UI, lazy LLM/TERMite integrations, taxonomy lookup, count-gated API
execution, row filtering, and an evaluation harness.

## Package layout

| Path | Purpose |
|------|---------|
| `src/oppp/models.py` | Pydantic contracts for stage artifacts, machine queries, grounding, validation, execution results, row execution, and runtime filters. |
| `src/oppp/pipeline.py` | Sequential runner and LangGraph builder around the fixed operation order. |
| `src/oppp/stages/` | Expansion, decomposition, TERMite enrichment, staged translation, aggregation, and row filtering. |
| `src/oppp/taxonomy/` | CSV-backed closed-set indexes and hierarchy helpers. |
| `src/oppp/normalize/` | Field-aware normalizer strategies. |
| `src/oppp/services/` | Service field maps, facets, invariants, and TERMite type maps. |
| `src/oppp/eval/` | Count-gated harness, diagnostics, and report export. |
| `src/oppp/ui/app.py` | Streamlit stage inspector. |
| `src/oppp/cli.py` | Typer command surface. |

## Stack

| Tool | Role |
|------|------|
| Python 3.11+ | Implementation language. |
| Pydantic | Typed stage contracts and machine-query models. |
| Typer | CLI entry points. |
| RapidFuzz | Fuzzy lookup over taxonomy values. |
| python-dotenv | Lazy `.env` loading. |
| urllib.request | Standard-library HTTP count and datapoint execution. |
| LangChain / langchain-openai | Structured-output LLM client through Portkey/OpenAI-compatible settings. |
| LangGraph | Optional graph wrapper around the fixed stages. |
| SciBite TERMite toolkit | Entity enrichment for decomposed query fragments. |
| Streamlit | Optional browser UI. |
| matplotlib | Optional `oppp dag` PNG rendering. |
| openpyxl | Optional XLSX evaluation report export. |
| Pytest / Ruff | Test and lint tooling. |

## Install and run

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'

oppp run "AUC of Sunitinib in human after oral"
oppp run "<question>" --payload-only
oppp run "<question>" --no-execute
oppp run --case 1

oppp enhance "AUC of Sunitinib in human after oral"
oppp decompose "AUC of Sunitinib in human after oral"
oppp field drugs "suntinib"
oppp aggregate "AUC or Cmax of sunitinib in rat"
oppp lookup species Rodent --expand
oppp services
oppp eval --show-cases

streamlit run src/oppp/ui/app.py
pytest -q
ruff check src tests
```

Extras:

| Extra | Enables |
|-------|---------|
| `llm` | LangChain/OpenAI/Portkey-backed expander, decomposer, term selector, aggregator, and LangGraph wiring. |
| `ui` | Streamlit app. |
| `viz` | `oppp dag` PNG rendering. |
| `report` | XLSX report output from `oppp eval --output`. |
| `dev` | Local test, lint, and report dependencies. |

## Configuration

Settings load lazily when the relevant surface asks for LLM, TERMite, or API
execution.

| Variable | Purpose |
|----------|---------|
| `OPPP_INPUTS_DIR` | Overrides the default `inputs/` directory. |
| `PORTKEY_ENDPOINT` | Portkey/OpenAI-compatible base URL. |
| `PORTKEY_API_KEY` | API key for the Portkey/OpenAI-compatible endpoint. |
| `PORTKEY_PROVIDER` | Provider prefix used in the LangChain model name. |
| `TOOL_MODEL` | Default model suffix for `oppp.llm.get_chat_model()`. |
| `LLM_SEED` | Optional decoding seed; default is `7`. |
| `TERMITE_HOME` | TERMite service URL. |
| `TERMITE_AUTH_URL` | TERMite OAuth token URL. |
| `TERMITE_CLIENT_NAME` | TERMite OAuth client name. |
| `TERMITE_CLIENT_SECRET` | TERMite OAuth client secret. |

## Streamlit UI

The UI calls the same pipeline as `oppp run` and presents:

- service and execution controls;
- `PK_Query` question picker plus free-text query box;
- expanded query, decomposition components with field reasons, and field-scoped
  TERMite annotations;
- staged translations with `matched_ids`, `expanded_from`, and confidence;
- API payloads, validation status, count-gate branch, fetched datapoints, row
  filters, and final count.

The UI is a debugging surface; it does not add stage methods or bypasses.

## Implementation conventions

- Stage boundaries are typed and explicit.
- The operation order is fixed for the production path.
- Closed-set values proposed by an LLM are re-grounded against the CSV or inline
  set before they can be emitted.
- CSV-backed closed fields with fewer than `1000` values are small closed/early;
  CSV-backed closed fields with `1000` or more values remain closed.
- Open-set filters are row-side filters under the `1000` row gate and direct API
  constraints only when the closed branch remains at or above `1000`.
- LLM, TERMite, UI, visualization, and report dependencies are imported lazily.
