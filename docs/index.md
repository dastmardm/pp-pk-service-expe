# Documentation index

This documentation describes the `oppp` natural-language-to-machine-query
translator for PharmaPendium: the problem it solves, the field/value contracts it
uses, the staged pipeline design, examples, evaluation, and implementation notes.

| Area | Doc | What it covers |
|------|-----|----------------|
| Start here | [README.md](README.md) | Project overview, reading order, pipeline stages, common CLI commands. |
| Overview | [00-overview/problem-statement.md](00-overview/problem-statement.md) | Why the monolithic legacy translator is being replaced. |
| Overview | [00-overview/glossary.md](00-overview/glossary.md) | Shared vocabulary for fields, grounding, services, and evaluation. |
| Domain inputs | [02-domain-inputs/csv-catalog.md](02-domain-inputs/csv-catalog.md) | CSV files under `inputs/` and how the code uses them. |
| Domain inputs | [02-domain-inputs/field-taxonomy.md](02-domain-inputs/field-taxonomy.md) | Filterable fields, closed sets, open sets, and service field maps. |
| Domain inputs | [02-domain-inputs/machine-query-schema.md](02-domain-inputs/machine-query-schema.md) | The machine-query JSON shape and PK-specific invariants. |
| Design | [03-proposed-design/architecture.md](03-proposed-design/architecture.md) | Pipeline architecture and service boundaries. |
| Design | [03-proposed-design/stage-1-decomposition.md](03-proposed-design/stage-1-decomposition.md) | Stage 1 component decomposition and annotation reconciliation. |
| Design | [03-proposed-design/stage-2-subquery-translation.md](03-proposed-design/stage-2-subquery-translation.md) | Stage 2 field translation and grounding behavior. |
| Design | [03-proposed-design/stage-3-aggregation.md](03-proposed-design/stage-3-aggregation.md) | Stage 3 boolean assembly, service invariants, execution, and post-filter design. |
| Design | [03-proposed-design/grounding-and-tool-calling.md](03-proposed-design/grounding-and-tool-calling.md) | Closed-set lookup, LLM fallback, hierarchy expansion, and TERMite division of labor. |
| Design | [03-proposed-design/misspelling-strategy.md](03-proposed-design/misspelling-strategy.md) | Normalizer behavior for closed-set and open-set fields. |
| Examples | [04-examples/worked-examples.md](04-examples/worked-examples.md) | End-to-end traces for representative SME cases. |
| Evaluation | [05-evaluation/gold-set-and-metrics.md](05-evaluation/gold-set-and-metrics.md) | Gold datasets, per-step comparators, LLM judge, and count metrics. |
| Implementation | [06-implementation/build-status.md](06-implementation/build-status.md) | Current package status, modules, commands, and limitations. |
| Implementation | [06-implementation/operations.md](06-implementation/operations.md) | How to install, run, configure, and execute the package. |
| Implementation | [06-implementation/streamlit-ui.md](06-implementation/streamlit-ui.md) | Streamlit debug UI behavior. |
| Implementation | [06-implementation/tech-stack.md](06-implementation/tech-stack.md) | Stack choices and implementation conventions. |
| Artifact | [agent-dag.drawio](agent-dag.drawio) | Editable Draw.io source for the agent component DAG. |
| Artifact | [agent-dag.png](agent-dag.png) | Rendered Draw.io component DAG used by the overview README. |
| Artifact | [PPPK.xlsx](PPPK.xlsx) | SME gold query set used by evaluation; includes PK queries with expected counts and parameter taxonomy. |
