# PharmaPendium NL→Machine-Query Redesign

This folder documents the natural-language-to-machine-query translation layer
implemented in [src/oppp/](../src/oppp/) and the legacy prompt stack it replaces
under [utils/ppendium/](../utils/ppendium/). See [index.md](index.md) for the
complete documentation map.

The **goal of the redesign**: replace the single monolithic "one giant prompt
does everything" translator with a **decomposed, field-by-field pipeline** that
grounds input closed-set fields against the taxonomy CSVs in
[inputs/](../inputs/), then handles fields whose value space is not known until
runtime by translating against the unique values in fetched datapoints.

## Reading order

| # | Doc | What it covers |
|---|-----|----------------|
| 0 | [00-overview/problem-statement.md](00-overview/problem-statement.md) | The problem in one page |
| 0 | [00-overview/glossary.md](00-overview/glossary.md) | Shared vocabulary |
| 1 | [01-current-system/legacy-architecture.md](01-current-system/legacy-architecture.md) | How the legacy translator works today |
| 1 | [01-current-system/pain-points.md](01-current-system/pain-points.md) | Why it needs to change (evidence from the gold set) |
| 2 | [02-domain-inputs/machine-query-schema.md](02-domain-inputs/machine-query-schema.md) | The target machine-query format |
| 2 | [02-domain-inputs/field-taxonomy.md](02-domain-inputs/field-taxonomy.md) | The two sets of searchable fields |
| 2 | [02-domain-inputs/csv-catalog.md](02-domain-inputs/csv-catalog.md) | What each CSV in `inputs/` is for |
| 3 | [03-proposed-design/architecture.md](03-proposed-design/architecture.md) | The pipeline: 3 core stages + optional Stage 0 |
| 3 | [03-proposed-design/stage-1-decomposition.md](03-proposed-design/stage-1-decomposition.md) | NL query → per-field NL subqueries |
| 3 | [03-proposed-design/stage-2-subquery-translation.md](03-proposed-design/stage-2-subquery-translation.md) | NL subquery → machine subquery |
| 3 | [03-proposed-design/stage-3-aggregation.md](03-proposed-design/stage-3-aggregation.md) | Subqueries → final machine query |
| 3 | [03-proposed-design/grounding-and-tool-calling.md](03-proposed-design/grounding-and-tool-calling.md) | How CSV grounding + tool calling work |
| 3 | [03-proposed-design/misspelling-strategy.md](03-proposed-design/misspelling-strategy.md) | Pluggable handling of user misspellings (interface only) |
| 4 | [04-examples/worked-examples.md](04-examples/worked-examples.md) | End-to-end traces from the SME gold set |
| 5 | [05-evaluation/gold-set-and-metrics.md](05-evaluation/gold-set-and-metrics.md) | How we measure success — per-step gold set, metrics & LLM-as-judge |
| 6 | [06-implementation/tech-stack.md](06-implementation/tech-stack.md) | Tools/packages + pluggability & per-step isolation |
| 6 | [06-implementation/build-status.md](06-implementation/build-status.md) | What's built (the `oppp` package), how to run it, limitations |
| 6 | [06-implementation/operations.md](06-implementation/operations.md) | Install, run, configuration, credentials, and execution model |
| 6 | [06-implementation/streamlit-ui.md](06-implementation/streamlit-ui.md) | The Streamlit demo/debug UI: question picker, per-step selectors, stage outputs |

## Pipeline stages (pluggable + isolatable)

The pipeline is **three core stages** (decompose → translate → aggregate) preceded
by Stage -1 query expansion and an optional Stage 0 enhancer. Each step is
selectable by name through a registry and runnable on its own. CLI defaults use
the model-backed path; offline **doubles** let the test suite and per-stage
evaluation run without the LLM. The doubles skip LLM calls, not the API; add
`--no-execute` to skip the API too.

| Stage | Job | Backends (CLI default in **bold**) | Run alone |
|-------|-----|--------------------------------|-----------|
| -1 Expand | clarify the query and spell out abbreviations without changing meaning | **`llm`**, `noop` | full pipeline only |
| 0 Enhance *(optional)* | normalize entities in the raw query | **`termite`**, `noop` (offline) | `oppp enhance` |
| 1 Decompose | split into single-field components — **no vocab, no guessing** | **`llm`**, `gazetteer` (offline double) | `oppp decompose` |
| 2 Translate | translate fields against input or runtime closed sets | **`tool`** (LLM term-select), `deterministic` (offline double) | `oppp field` |
| 3 Aggregate | assemble and validate the API query; live runs may execute it for `countTotal` and probe open-set filters | **`llm`**, `deterministic` (offline double) | `oppp aggregate` |

`oppp run` defaults to `llm` expansion, `termite` enhancement, `llm`
decomposition, `tool` translation, `llm` aggregation, fuzzy normalization, and
API execution. The Python `run_pipeline()` defaults are more conservative for
library use: `enhancer=noop`, `normalizer=noop`, and no open-filter probes. For
an LLM-free run pin the doubles and disable the enhancer
(`--expander noop --enhancer noop --decomposer gazetteer --translator deterministic --aggregator deterministic`);
add `--no-execute` to also skip the API and stay fully offline.

![Agent component DAG](agent-dag.png)

> Regenerate this diagram with `oppp dag` (needs the `viz` extra:
> `pip install -e '.[viz]'`). Nodes are the agent's key components; solid edges
> are data flow, dashed edges are dependencies.

## Common CLI commands

The package installs an `oppp` console script (`oppp.cli:app`). All commands
accept `--help`. Run them from the repo root after `pip install -e .` (LLM
backends need the `llm` extra: `pip install -e '.[llm]'` + `.env` creds).

| Command | What it does |
|---------|--------------|
| `oppp run "<question>"` | Run the **full pipeline**, printing every stage (enhance → decomposition → subqueries + grounding → final machine query). |
| `oppp enhance "<question>"` | **Stage 0 only** — show the enhanced query + entity annotations. |
| `oppp decompose "<question>"` | **Stage 1 only** — show the per-field components as JSON. |
| `oppp field <field> "<fragment>"` | **Stage 2 only** — translate a single field fragment to a machine subquery. |
| `oppp aggregate "<question>"` | **Stage 3 only** — decompose+translate, then aggregate with the chosen backend. |
| `oppp lookup <taxonomy> "<term>"` | Inspect the **grounding layer** — look a term up in a taxonomy CSV. |
| `oppp services` | List configured services and their fields. |
| `oppp eval` | Evaluate against the SME gold set by expected result count. |

```bash
# Full pipeline (defaults match `oppp eval`: termite enhance + llm decompose +
# tool translate + llm aggregate + fuzzy normalize)
oppp run "adverse effects of sunitinib in humans"

# Fully offline run (no LLM), disabling the enhancer and pinning the doubles
oppp run "adverse effects of sunitinib in humans" \
  --enhancer noop --decomposer gazetteer --translator deterministic --aggregator deterministic

# Disable the TERMite enhancer (Stage 0 defaults to termite)
oppp run "<question>" --enhancer noop

# Print only the API payload JSON, or POST it to get countTotal
oppp run "<question>" --payload-only
oppp run "<question>" --execute

# Run a specific SME gold case and diff against the gold filters
oppp run --case 23

# Isolate a single stage
oppp enhance   "adverse effects of sunitinib in humans" --backend termite
oppp decompose "adverse effects of sunitinib in humans" --backend llm
oppp field     drugs "sunitnib" --normalizer fuzzy
oppp aggregate "abemaciclib liver disorders in rats or mice" --backend llm

# Grounding: look up a term, optionally expanding a class node
oppp lookup drugs "sunitinib"
oppp lookup effects "Neutropenia" --expand

# Evaluation against the gold set: offline doubles (no LLM) by default, but it
# *executes* each query against the API for counts. Add --no-execute for a fully
# offline, validity-only run.
oppp eval --tolerance 0.10 --show-cases
```

## One-paragraph summary

A user asks a question in natural language. Stage -1 may rewrite it into a
clearer form while preserving every entity and filter. An optional **enhancer**
(TERMite) annotates recognized entities up front. An LLM **decomposer** then
splits the question into single-field components using the user's own words; it
only segments, and does not resolve, normalize, or consult any vocabulary. Each
component is **translated independently** against a known closed set. For fields
whose legal values are available as CSV taxonomies or inline enums (drugs,
effects, species, route, dose type, sex, ...), the value is grounded before the
API call. Fields without an input value set (study group, comments, free-text
qualifiers, target values without a local taxonomy) are represented in the design
as runtime closed-set post-filters. In the current package, those open fields are
emitted as direct `MATCH`/`REGEX` constraints and, when execution is enabled, can
be guarded by isolated zero-count probes before final aggregation. Finally an LLM
**aggregator** reads the decomposition plus valid machine subqueries and assembles
the nested machine query the PharmaPendium API expects; the boolean structure is
rendered and validated deterministically.

> **Status:** implemented as the `oppp` package. Every stage is pluggable by name
> and isolatable; offline doubles (`gazetteer` / `deterministic`) keep the test
> suite hermetic and let evaluation run without the LLM (pass `--no-execute` to
> skip the API too). See
> [06-implementation/build-status.md](06-implementation/build-status.md).
