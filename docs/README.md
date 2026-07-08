# PharmaPendium PK translator docs

This documentation describes `oppp`, a Python package that translates
PharmaPendium pharmacokinetics questions into structured machine queries.

The package uses a fixed pipeline:

```text
NL question -> expansion -> decomposition -> TERMite enrichment
-> early closed-set translation -> aggregation/count
-> row fetch below 1000 rows, or staged closed/open-set translation
```

Closed-set fields are grounded against CSV taxonomies, enums, or booleans.
Open-set fields are kept as row-side filters when a closed-set count is below
`1000`; otherwise they are emitted as direct `MATCH` or `REGEX` constraints in
the final API query.

## Read first

| Doc | Purpose |
|-----|---------|
| [index.md](index.md) | Repository topology and complete documentation map. |
| [domain.md](domain.md) | PharmaPendium API payload, field taxonomy, CSV inputs, and PK invariants. |
| [pipeline.md](pipeline.md) | Fixed stage design, grounding, normalization, and aggregation behavior. |
| [examples.md](examples.md) | Representative end-to-end PK query traces. |
| [evaluation.md](evaluation.md) | Gold workbook and exact-count evaluation contract. |
| [implementation.md](implementation.md) | Package modules, commands, configuration, UI, and implementation conventions. |

## Common commands

Run from the repository root after installing the package and the extras needed
by the surface you use.

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'

oppp run "AUC of Sunitinib in human after oral administration"
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

## Diagram

The editable component diagram is [agent-dag.drawio](agent-dag.drawio). Solid
arrows show runtime flow; dashed arrows show supporting inputs.
