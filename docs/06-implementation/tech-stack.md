# Tech Stack & Implementation Conventions

The implementation lives in [src/oppp/](../../src/oppp/) as a Python package.
The core convention is stable across the package: every pipeline step has a
typed boundary, a registry-backed implementation choice, and an isolated command
or helper for debugging and evaluation.

## Stack

| Tool | Role in this project |
|------|----------------------|
| **Python 3.11+** | Implementation language. |
| **pyproject.toml / Hatchling** | Package metadata, extras, console script, build backend, and Ruff/Pytest configuration. |
| **Pydantic** | Typed stage contracts: expansion, enhancement annotations, decomposition components, subqueries, machine query, aggregation plan, and judge verdicts. |
| **Typer** | CLI entry points for full runs, isolated stages, lookup, DAG rendering, services, and evaluation. |
| **RapidFuzz** | Exact-adjacent and fuzzy lookup over closed-set taxonomy names. |
| **python-dotenv** | Lazy `.env` loading when LLM or TERMite-backed paths need credentials. |
| **urllib.request** | Standard-library HTTP execution for `countTotal` calls; no extra HTTP dependency in the core. |
| **LangChain / langchain-openai** | Optional structured-output LLM client through Portkey/OpenAI-compatible settings. |
| **LangGraph** | Optional graph wrapper around the same pipeline stages, available through `build_langgraph()`. |
| **SciBite TERMite toolkit** | Optional Stage 0 NER enhancer that supplies entity labels, types, and public synonyms. |
| **Streamlit** | Optional browser UI for stage-by-stage debugging. |
| **matplotlib** | Optional DAG PNG rendering for `oppp dag`. |
| **openpyxl** | Optional XLSX report export from `oppp eval --output`. |
| **Pytest / Ruff** | Test and lint tooling. |

## Pluggability

Each swappable part uses a small `Protocol` plus the shared
[Registry](../../src/oppp/registry.py):

| Surface | Registry | Implementations |
|---------|----------|-----------------|
| Stage -1 expander | `expander_registry` | `llm`, `noop` |
| Stage 0 enhancer | `enhancer_registry` | `termite`, `noop` |
| Stage 1 decomposer | `decomposer_registry` | `llm`, `gazetteer` |
| Stage 2 translator | `translator_registry` | `tool`, `deterministic` |
| Stage 2 normalizer | `normalizer_registry` | `fuzzy`, `noop` |
| Stage 3 aggregator | `aggregator_registry` | `llm`, `deterministic` |
| Service config | `service_registry` | `safety`, `pk`, `rtb` |

The full pipeline resolves these names in
[pipeline.py](../../src/oppp/pipeline.py). The CLI exposes the same choices as
flags, and the Streamlit UI reads names from the registries.

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
[eval/harness.py](../../src/oppp/eval/harness.py) scores `countTotal` proximity.

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
| LLM-as-judge | `JudgeVerdict` |

The final request body is always represented by `MachineQuery` and validated by
Stage 3. Closed-set values proposed by the LLM are re-grounded against the CSV
before they can be emitted.

## Prompt Optimization

The package includes typed boundaries that are suitable for prompt optimization,
but there are no DSPy modules under `src/oppp/` in v0.1. Prompt optimization can
reuse the same registries and Pydantic contracts without changing the stage
interfaces.

## Package Layout

| Path | Purpose |
|------|---------|
| [src/oppp/models.py](../../src/oppp/models.py) | Pydantic contracts shared by all stages. |
| [src/oppp/pipeline.py](../../src/oppp/pipeline.py) | Sequential runner and optional LangGraph builder. |
| [src/oppp/stages/](../../src/oppp/stages/) | Expansion, enhancement, decomposition, translation, and aggregation stages. |
| [src/oppp/taxonomy/](../../src/oppp/taxonomy/) | CSV-backed closed-set indexes and hierarchy helpers. |
| [src/oppp/normalize/](../../src/oppp/normalize/) | Misspelling normalizer strategies. |
| [src/oppp/services/](../../src/oppp/services/) | Safety, PK, and RTB field maps, invariants, and RTB serializer. |
| [src/oppp/eval/](../../src/oppp/eval/) | Count harness, per-step comparators, judge, and gold diff helpers. |
| [src/oppp/ui/app.py](../../src/oppp/ui/app.py) | Streamlit debug UI. |
| [src/oppp/cli.py](../../src/oppp/cli.py) | Typer CLI. |
