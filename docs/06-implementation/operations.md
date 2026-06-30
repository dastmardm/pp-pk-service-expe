# Operations

The `oppp` package is a local Python package with a Typer CLI, Streamlit UI,
required LLM/TERMite integrations for the pipeline, and an API count execution
path. Runtime settings load lazily when the fixed pipeline or execution path
needs them.

## Install

The package is defined in [pyproject.toml](../../pyproject.toml) and exposes the
`oppp` console script.

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

Install the extras required by the surfaces being used:

| Extra | Enables |
|-------|---------|
| `llm` | LangChain/OpenAI/Portkey-backed expander, decomposer, term selector, aggregator, and LangGraph wiring. |
| `ui` | Streamlit app at [ui/app.py](../../src/oppp/ui/app.py). |
| `viz` | `oppp dag` PNG rendering through matplotlib. |
| `report` | Excel output from `oppp eval --output report.xlsx` through openpyxl. |
| `dev` | Test/lint/report dependencies used by local development. |

## Run

Common commands:

```bash
oppp run "What are the ADRs of Sunitinib in human"
oppp run "<question>" --no-execute
oppp enhance "ADRs of Columvi in human"
oppp decompose "ADRs of Sunitinib in human"
oppp field drugs "suntinib"
oppp aggregate "neutropenia or thrombocytopenia in human"
oppp lookup species Rodent --expand
oppp services
oppp eval --show-cases
oppp dag
streamlit run src/oppp/ui/app.py
pytest -q
ruff check src tests
```

The CLI `run` command uses the fixed production path: LLM expansion, TERMite
enhancement, LLM decomposition, grounded tool translation, LLM aggregation,
fuzzy normalization, and API execution. Stage implementations are not selected
with stage flags. Use `--no-execute` when the API call should be skipped;
the pipeline stages still run in the same order.

The Python function [run_pipeline()](../../src/oppp/pipeline.py) uses the same
fixed stage implementations as the CLI. Library callers may control execution
behavior such as `probe_open_filters`, but not replace a pipeline stage with a
different method.

## Configuration

The configuration surface is defined in [config.py](../../src/oppp/config.py)
and mirrored by [.env.example](../../.env.example). `load_dotenv_if_present()`
loads `.env` when the LLM, TERMite, or API execution path asks for it.

| Variable | Purpose | Required for |
|----------|---------|--------------|
| `OPPP_INPUTS_DIR` | Overrides the default [inputs/](../../inputs/) directory used for taxonomies and gold sets. | Custom data location. |
| `PORTKEY_ENDPOINT` | Portkey/OpenAI-compatible base URL. | LLM expander, decomposer, aggregator, term selector, judge. |
| `PORTKEY_API_KEY` | API key for the Portkey/OpenAI-compatible endpoint. | Same as above. |
| `PORTKEY_PROVIDER` | Provider prefix used when building the LangChain model name. | Same as above. |
| `TOOL_MODEL` | Default model suffix used by `oppp.llm.get_chat_model()`. | Same as above. |
| `LLM_SEED` | Optional decoding seed; defaults to `7` when absent. | Reproducible LLM calls. |
| `TERMITE_HOME` | TERMite service URL. | Required Stage 0 enhancer. |
| `TERMITE_AUTH_URL` | TERMite OAuth token URL. | Required Stage 0 enhancer. |
| `TERMITE_CLIENT_NAME` | TERMite OAuth client name. | Required Stage 0 enhancer. |
| `TERMITE_CLIENT_SECRET` | TERMite OAuth client secret. | Required Stage 0 enhancer. |

## Execution Model

[execute.py](../../src/oppp/execute.py) posts a `MachineQuery` payload to the
configured service `search_url` and reads `data.countTotal`. It does not fetch
full result rows. The CLI uses this count for `oppp run --execute` and the
evaluation harness uses it for result-count accuracy.

When `probe_open_filters=true`, the pipeline asks the API for isolated counts of
open-set filters before final aggregation. If an open-set filter's isolated count
is confirmed as `0`, it is dropped and recorded as a warning. Probe failures keep
the filter, and entity-routed filters such as `DrugsTargets` are skipped because
the API rejects an entity-filter-only probe.
