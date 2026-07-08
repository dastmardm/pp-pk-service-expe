# Documentation index

## Repository topology

```text
pp-pk-service-expe/ - local package, inputs, tests, and docs for the `oppp` translator
├── src/oppp/ - Python package for NL-to-machine-query translation
│   ├── stages/ - expansion, decomposition, TERMite enrichment, staged translation, aggregation
│   ├── services/ - service configuration; PK is the documented target service
│   ├── taxonomy/ - CSV-backed lookup and hierarchy expansion
│   ├── normalize/ - field-aware misspelling and surface cleanup
│   ├── eval/ - count-gated harness, diagnostics, and report export
│   └── ui/ - Streamlit stage inspector
├── inputs/ - taxonomy CSVs, request/response field catalogs, and evaluation inputs
├── tests/ - offline tests for taxonomy, pipeline, and evaluation surfaces
├── utils/ - PharmaPendium and TERMite helper clients used by integration surfaces
└── docs/ - human-facing project documentation
```

## Subrepos

This repository has no pinned git submodules. All documented package, input, test,
and documentation assets live directly in this repository.

## Services and major components

| Component | Role |
|-----------|------|
| `oppp` package | Fixed-stage translator from PK natural-language questions to PharmaPendium machine queries. |
| PK service config | Field buckets, facet allow-list, TERMite type map, search URL, and service invariants. |
| Taxonomy layer | Loads CSV value sets and provides exact, fuzzy, and hierarchy-aware lookup. |
| Pipeline stages | Expansion, decomposition, TERMite enrichment, staged translation, aggregation, validation, row filtering, and execution orchestration. |
| Evaluation harness | Runs `PK_Query` cases and compares the final row count to `Expected Count`. |
| Streamlit UI | Browser inspector for stage outputs and final payloads. |

## Documentation files

| File | Covers |
|------|--------|
| [README.md](README.md) | Project overview, reading order, and common commands. |
| [domain.md](domain.md) | API payload shape, PK field taxonomy, CSV inputs, and service invariants. |
| [pipeline.md](pipeline.md) | Fixed pipeline, grounding, normalization, aggregation, and execution behavior. |
| [examples.md](examples.md) | Worked examples for representative PK questions. |
| [evaluation.md](evaluation.md) | `PK_Query` sheet and expected-row-count scoring. |
| [implementation.md](implementation.md) | Package layout, install/run/configuration, UI, and implementation conventions. |
| [agent-dag.drawio](agent-dag.drawio) | Editable Draw.io component diagram. |
| [PPPK.xlsx](PPPK.xlsx) | SME PK evaluation workbook; automated scoring uses only `PK_Query`. |
