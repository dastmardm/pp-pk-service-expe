# PharmaPendium NL→Machine-Query Redesign

This folder documents the redesign of the natural-language-to-machine-query
translation layer that currently lives in [utils/ppendium/](../utils/ppendium/).

The **goal of the redesign**: replace the single monolithic "one giant prompt
does everything" translator with a **decomposed, field-by-field pipeline** that
grounds closed-vocabulary fields against the taxonomy CSVs in
[inputs/](../inputs/) and only relies on free LLM judgement for fields whose
value space we cannot enumerate.

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
| 3 | [03-proposed-design/architecture.md](03-proposed-design/architecture.md) | The new 3-stage pipeline |
| 3 | [03-proposed-design/stage-1-decomposition.md](03-proposed-design/stage-1-decomposition.md) | NL query → per-field NL subqueries |
| 3 | [03-proposed-design/stage-2-subquery-translation.md](03-proposed-design/stage-2-subquery-translation.md) | NL subquery → machine subquery |
| 3 | [03-proposed-design/stage-3-aggregation.md](03-proposed-design/stage-3-aggregation.md) | Subqueries → final machine query |
| 3 | [03-proposed-design/grounding-and-tool-calling.md](03-proposed-design/grounding-and-tool-calling.md) | How CSV grounding + tool calling work |
| 3 | [03-proposed-design/misspelling-strategy.md](03-proposed-design/misspelling-strategy.md) | Pluggable handling of user misspellings (interface only) |
| 4 | [04-examples/worked-examples.md](04-examples/worked-examples.md) | End-to-end traces from the SME gold set |
| 5 | [05-evaluation/gold-set-and-metrics.md](05-evaluation/gold-set-and-metrics.md) | How we measure success |

## One-paragraph summary

A user asks a question in natural language. We **split** it into many small
single-field natural-language subqueries (one per searchable field). Each
subquery is **translated independently** into a machine subquery — a single
filter of the form `(operator, field, value)`. For fields whose legal values we
already have as CSV taxonomies (drugs, effects, species, route, …), the value is
**grounded by tool-calling against the CSV** instead of being invented by the
model; for fields we cannot enumerate (study group, dose comment, free-text
qualifiers, numeric thresholds), the model decides the value directly. Finally
we **aggregate** all machine subqueries into the single nested machine query the
PharmaPendium API expects.

> **Status:** design proposal. This captures the intended architecture and the
> reasoning behind it; it is not yet implemented.
