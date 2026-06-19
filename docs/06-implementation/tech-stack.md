# Tech stack & implementation conventions

The tools and packages the redesign will be built with, and the two
non-negotiable conventions every component must follow:

> **Every step is (1) pluggable and (2) isolatable for evaluation.** You can swap
> any step's implementation, and you can run any single step on its own against a
> gold set without standing up the rest of the pipeline.
>
> **Prefer LLM calls with structured output wherever possible.** Every LLM step
> should return a typed, schema-validated object — never free text we parse after
> the fact. See [Structured output](#structured-output-preferred).

## The stack

| Tool | Role in this project |
|------|----------------------|
| **Python** | Implementation language. |
| **uv** | Environment + dependency + packaging manager (`uv venv`, `uv add`, `uv run`, `uv.lock`). Single source of truth for deps; no ad-hoc pip. |
| **Pydantic** | Typed contracts for every boundary — the decomposition component, the per-field machine subquery, and the final machine query are all Pydantic models. Validation replaces the legacy regex/brace JSON scraping. |
| **LangChain** | LLM client + tool-calling plumbing for the CSV lookup tools (wraps the existing [utils/client/](../../utils/client/) Portkey setup). |
| **LangGraph** | Orchestrates the pipeline as an explicit graph — the 3 core stages (decompose → translate → aggregate) behind the optional Stage 0 enhancer — with per-field fan-out/fan-in in Stage 2. Each node is a swappable unit; the graph is what makes step isolation natural. |
| **DSPy** | The translation steps are authored as **DSPy modules** (signatures + programs) so prompts are **optimizable** rather than hand-tuned strings. The SME gold set drives DSPy optimizers (e.g. few-shot / instruction search). See [Prompt optimization](#prompt-optimization-dspy). |
| **Typer** | CLI entry points: run the full pipeline, run a single stage/field, and run evaluations from the terminal. |
| **Streamlit** | Interactive UI for demoing and debugging — pick a gold-set question or type one, select each stage's backend (enhancer / decomposer / translator / aggregator / normalizer), and inspect every stage's intermediate output through to the final machine query. See [streamlit-ui.md](streamlit-ui.md). |
| **Ruff** | Linting + formatting. Enforced in CI / pre-commit. |
| **(existing) SciBite TERMite** | Kept as-is for NER ([utils/termite/](../../utils/termite/)). |

## Pluggability

Every step is defined by a **Pydantic-typed interface**, registered behind a
factory, and selected by config — not hard-wired. This already shows up in the
design:

- per-field **translators** in [stage-2-subquery-translation.md](../03-proposed-design/stage-2-subquery-translation.md);
- the **CSV lookup tools** in [grounding-and-tool-calling.md](../03-proposed-design/grounding-and-tool-calling.md);
- the **misspelling normalizers** in [misspelling-strategy.md](../03-proposed-design/misspelling-strategy.md);
- per-service **config** (fields, facet allow-lists, invariants, output serializer)
  from [architecture.md](../03-proposed-design/architecture.md).

Concretely: a step is a `Protocol`/ABC with a typed `run(input) -> output`
method; implementations register under a name; LangGraph nodes resolve the
implementation from config. Swapping a normalizer or a translator is a config
change, not a code edit.

## Isolation for evaluation

Because each step has typed inputs/outputs, each can be exercised **alone**:

| Step | Isolated input → output | Evaluated against |
|------|--------------------------|-------------------|
| Stage 0 — enhance *(optional)* | NL query → enhanced query + entity annotations | enhancer on/off behaviour |
| Stage 1 — decomposition | NL query → list of components (`field`, `type`, `reason`, …) | gold field-routing / type / boolean hints |
| Stage 2 — per-field translate | one component → one machine subquery | gold per-field values (P/R/F1) |
| Stage 2 — lookup/expansion | fragment → grounded labels/ids | gold hierarchy expansions |
| Stage 2 — normalizer | misspelled fragment → corrected | typo fixtures |
| Stage 3 — aggregation | subqueries → final machine query | schema validity + structure |

This is exactly the per-field/per-stage scoring in
[../05-evaluation/gold-set-and-metrics.md](../05-evaluation/gold-set-and-metrics.md).
Each LangGraph node is independently invokable; Typer exposes a
`--stage`/`--field` target so a single step can be benchmarked from the CLI, and
DSPy optimization targets one module at a time using these isolated harnesses.

## Structured output (preferred)

We **prefer LLM calls that return structured output** over free-text-then-parse,
wherever the model/provider supports it. Every LLM step in the pipeline emits a
typed object validated against its Pydantic model:

- **Stage 1 — decomposition** → a list of components
  (`field`, `type`, `reason`, `source`, …).
- **Stage 2 — open-field translation / disambiguation** → a typed machine
  subquery (`operator`, `field`, `value`).
- **CSV lookup tool calls** → typed arguments (LangChain tool-calling) rather
  than a stringified call.

Why this is the default:

- It **kills the legacy failure mode** — the regex + brace-matching JSON scraper
  in [extract_payload_req()](../../utils/ppendium/__init__.py) exists only because
  the model returned prose. Structured output removes that surface entirely.
- It composes with **Pydantic** validation and with **DSPy** typed signatures,
  so the schema is the contract end-to-end.
- It makes **isolation/eval** clean: each step's output is already a typed object
  to diff against the gold set.

Mechanism: provider-native structured/JSON output or tool-calling via LangChain
(`with_structured_output` / function-calling) bound to the step's Pydantic model;
DSPy signatures declare the same typed outputs.

**"If possible" caveat:** when a model or path can't guarantee structured output,
fall back to constrained generation + Pydantic validation with a bounded retry,
and surface a validation error rather than silently accepting malformed output.
The final machine query is **always** schema-validated in Stage 3 regardless of
how it was produced.

## Prompt optimization (DSPy)

The LLM-driven steps (Stage 1 decomposition, the open-field translators, any
LLM-based normalizer or disambiguator) are written as DSPy programs:

- a **signature** declares typed inputs/outputs (aligned with the Pydantic
  models), so the prompt is generated, not hand-written;
- the **SME gold set** ([inputs/sme_expected_cases.csv](../../inputs/sme_expected_cases.csv))
  provides train/dev examples and the metric;
- DSPy **optimizers** tune instructions/demonstrations per module, and because
  each module is isolated, we optimize one step without regressing the others.

This is the reason DSPy is in the stack: "we create the agent so it's compatible
for prompt optimization" — the architecture's per-step isolation is what makes
that optimization tractable.

## Suggested layout (sketch)

```
pyproject.toml          # uv-managed; deps + ruff config
uv.lock
src/oppp/
  models/               # pydantic contracts (component, subquery, machine query)
  pipeline/
    graph.py            # langgraph wiring of the stages
    stage0_enhance.py   # optional enhancer (termite default, noop opt-out)
    stage1_decompose.py # dspy module (vocab-free)
    stage2_translate/   # per-field translators (pluggable, registered)
    stage2_lookup/      # csv lookup tools + hierarchy expansion
    stage2_normalize/   # misspelling strategies (pluggable)
    stage3_aggregate.py # deterministic assembly + service invariants
  services/             # per-service config (safety, pk, rtb)
  eval/                 # isolated harnesses + metrics over the gold set
  cli.py                # typer entry points
  ui/app.py             # streamlit debug/demo UI
```

> **Status:** proposed stack and conventions. Layout is illustrative, not final.
