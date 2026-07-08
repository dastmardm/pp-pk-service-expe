# Tech Stack & Implementation Conventions

The implementation lives in [src/oppp/](../../src/oppp/) as a Python package.
The core convention is stable across the package: every pipeline step has a
typed boundary, one fixed production implementation, and an isolated command or
helper for debugging and evaluation.

## Stack

| Tool | Role in this project |
|------|----------------------|
| **Python 3.11+** | Implementation language. |
| **pyproject.toml / Hatchling** | Package metadata, extras, console script, build backend, and Ruff/Pytest configuration. |
| **Pydantic** | Typed stage contracts: expansion, enhancement annotations, decomposition components, subqueries, machine query, and aggregation plan. |
| **Typer** | CLI entry points for full runs, isolated stages, lookup, DAG rendering, services, and evaluation. |
| **RapidFuzz** | Exact-adjacent and fuzzy lookup over closed-set taxonomy names. |
| **python-dotenv** | Lazy `.env` loading when LLM, TERMite, or API execution paths need credentials. |
| **urllib.request** | Standard-library HTTP execution for `countTotal` calls; no extra HTTP dependency in the core. |
| **LangChain / langchain-openai** | Structured-output LLM client through Portkey/OpenAI-compatible settings. |
| **LangGraph** | Graph wrapper around the same fixed pipeline stages, available through `build_langgraph()`. |
| **SciBite TERMite toolkit** | Required Stage 0 NER enhancer that supplies entity labels, types, and public synonyms. |
| **Streamlit** | Optional browser UI for stage-by-stage debugging. |
| **matplotlib** | Optional DAG PNG rendering for `oppp dag`. |
| **openpyxl** | Optional XLSX report export from `oppp eval --output`. |
| **Pytest / Ruff** | Test and lint tooling. |

## Fixed Stage Surfaces

Stage methods are fixed. The CLI, Python runner, and Streamlit UI expose the
same production path rather than a menu of interchangeable implementations:

| Surface | Code surface | Production method |
|---------|--------------|-------------------|
| Stage -1 expander | [stages/expand.py](../../src/oppp/stages/expand.py) | LLM query expansion |
| Stage 0 enhancer | [stages/enhance.py](../../src/oppp/stages/enhance.py) | TERMite NER |
| Stage 1 decomposer | [stages/decompose.py](../../src/oppp/stages/decompose.py) | LLM decomposition seeded by TERMite annotations |
| Stage 2 translator | [stages/translate.py](../../src/oppp/stages/translate.py) | grounded closed-set tool translation plus direct open-set translation |
| Stage 2 normalizer | [normalize/](../../src/oppp/normalize/) | fuzzy closed-set normalization plus conservative open-set cleanup |
| Stage 3 aggregator | [stages/aggregate.py](../../src/oppp/stages/aggregate.py) | LLM aggregation plan plus deterministic validation |
| Service config | [services/](../../src/oppp/services/) | PK field map, facets, and invariants |

The full pipeline executes these surfaces in [pipeline.py](../../src/oppp/pipeline.py).
Stage replacement methods and bypass shortcuts are not accepted.

## Isolation for Evaluation

Because each stage has typed inputs and outputs, each can be exercised alone:

| Step | Isolated input -> output | Code surface |
|------|--------------------------|--------------|
| Stage -1 expand | query -> `ExpandedQuery` | `oppp.stages.expand.expand()` |
| Stage 0 enhance | query -> `EnhancedQuery` | `oppp enhance` |
| Stage 1 decompose | query -> `Decomposition` | `oppp decompose` |
| Stage 2 translate | one `Component` -> `MachineSubquery` | `oppp field` |
| Taxonomy lookup | taxonomy + term -> `GroundingHit` list | `oppp lookup` |
| Stage 3 aggregate | decomposition + subqueries -> `MachineQuery` | `oppp aggregate` |
| End-to-end eval | gold question -> validity/count metrics | `oppp eval` |

The per-step comparators in [eval/per_step.py](../../src/oppp/eval/per_step.py)
score Stage 0 labels, Stage 1 routing/type pairs, Stage 2 emitted field names,
and Stage 3 machine-query structure. The count harness in
[eval/harness.py](../../src/oppp/eval/harness.py) scores exact `countTotal`
matches.
The gold query set is [`PPPK.xlsx`](../PPPK.xlsx) (`PK_Query` sheet).
The count harness and per-step comparators load it when scoring resolved field
values and end-to-end counts.

## Structured Output

LLM-backed stages use the central [llm.py](../../src/oppp/llm.py) factory, which
builds a LangChain chat model with temperature `0`, `top_p=0`, and a fixed seed
unless `LLM_SEED` overrides it. Structured-output calls are bound to Pydantic
models:

| Stage | Structured model |
|-------|------------------|
| Stage -1 expander | `QueryExpansion` |
| Stage 1 decomposer | `Decomposition` |
| Stage 2 term selector / LLM fallbacks | `TermSelection` |
| Stage 3 LLM aggregator | `AggregationPlan` |

The final request body is always represented by `MachineQuery` and validated by
Stage 3. Closed-set values proposed by the LLM are re-grounded against the CSV
before they can be emitted.

Evaluation criteria for these contracts must assert the contract shape itself —
for example the required fields on enhanced-query annotations, machine
subqueries, execution results, open-set probe warnings, and final machine queries
— not only end-to-end behavior. A missing field on a typed contract is a contract
regression even if one broad behavioral test still passes.

## Planning Coverage

Generated implementation plans must keep all MUST requirements assigned to WBS
tasks and evaluation criteria, including requirements that are mostly preservation
work. In particular:

- service configuration coverage remains included even when a feature primarily
  changes runtime filtering;
- lazy secret loading, `.env.example`, and `.gitignore` secret protection remain
  covered even when no credential behavior is being changed;
- dependency import isolation remains covered so importing the package does not
  eagerly load LLM, TERMite, UI, visualization, or report libraries before a
  surface needs them.

## Prompt Optimization

The package includes typed boundaries that are suitable for prompt optimization.
Prompt optimization can reuse the same Pydantic contracts without changing the
fixed stage interfaces.

## Package Layout

| Path | Purpose |
|------|---------|
| [src/oppp/models.py](../../src/oppp/models.py) | Pydantic contracts shared by all stages. |
| [src/oppp/pipeline.py](../../src/oppp/pipeline.py) | Sequential runner and LangGraph builder around the fixed stages. |
| [src/oppp/stages/](../../src/oppp/stages/) | Expansion, enhancement, decomposition, translation, and aggregation stages. |
| [src/oppp/taxonomy/](../../src/oppp/taxonomy/) | CSV-backed closed-set indexes and hierarchy helpers. |
| [src/oppp/normalize/](../../src/oppp/normalize/) | Misspelling normalizer strategies. |
| [src/oppp/services/](../../src/oppp/services/) | PK field map and service invariants. |
| [src/oppp/eval/](../../src/oppp/eval/) | Count harness, diagnostic per-step comparators, and gold diff helpers. |
| [src/oppp/ui/app.py](../../src/oppp/ui/app.py) | Streamlit debug UI. |
| [src/oppp/cli.py](../../src/oppp/cli.py) | Typer CLI. |
