# The machine-query format (target output)

This is what the pipeline must ultimately produce. It is the request body the
PharmaPendium PK search API (`/v1/pk/search/advanced`) accepts.

The API payload represents the filter layer sent to the search API. Closed-set
filters use values known from `inputs/` taxonomies, inline enums, or booleans.
Open-set filters appear in this payload as direct `MATCH` or `REGEX` constraints
and can be guarded in live runs by isolated zero-count probes.

## Top-level envelope

```json
{
  "query":          { ... },     // the boolean filter tree (required)
  "entityFilters":  [ ... ],     // filters via linked entities (optional)
  "sortColumns":    [ ... ],     // optional
  "displayColumns": [ ... ],     // optional; omit to return all fields
  "facets":         [ ... ],     // grouped counts (allow-listed per service)
  "leafOnly":       false,       // optional
  "mixtureExpansion": false,     // optional
  "limitation":     { ... }      // optional pagination
}
```

The request-side field/type catalogue is in
[inputs/query_criteria_fields.csv](../../inputs/query_criteria_fields.csv):

| field | type |
|-------|------|
| `drugs`, `drugsFuzzy`, `drugsAndSynonyms` | `array<string>` |
| `species`, `routes`, `documentSource` | `array<string>` |
| `documentYear` | `array<integer>` |
| `facets`, `displayColumns` | `array<string>` |
| `sortColumns` | `array<SortColumn>` |
| `limitation` | `Limitation` |
| `leafOnly` | `boolean` |

## The `query` tree: filters all the way down

The `query` is a tree with **exactly one top-level constraint**. Boolean nodes
use explicit `AND`/`OR`/`NOT` wrappers. Field-level leaves use the unwrapped API
shape; the selected operator is the typed machine-subquery metadata that produced
the leaf.

| Operator | Shape | Use for |
|----------|-------|---------|
| `MATCH` | `{"field": F, "value": V}` where `V` is a string or array | exact value(s) on a field |
| `OR` | `{"OR": [c1, c2, …]}` (≥2) | any of |
| `AND` | `{"AND": [c1, c2, …]}` (≥2) | all of |
| `NOT` | `{"NOT": c}` (single) | negation |
| `REGEX` | `{"field": F, "pattern": P}` | substring / free-text fields |
| `RANGE` | `{"field": F, "min": n, "max": n}` | numeric thresholds |
| `DATE_RANGE` | `{"field": F, "min": "YYYY-MM-DD", "max": …}` | dates |
| `EMPTY` | `{"field": F}` | field is empty/absent |
| `PROXIMITY` | (text proximity) | rarely used |

**Every Stage 2 machine subquery is an `(operator, field, value)` triple.** The
API query serializes the field leaf in the unwrapped shape while Stage 3 uses the
operator metadata to build `AND`/`OR`/`NOT` structure and validation.

### Example

> "AUC or Cmax of Sunitinib in human after oral administration"

```json
{
  "query": {
    "AND": [
      { "field": "drugsFuzzy", "value": ["Sunitinib*"] },
      { "field": "species",    "value": "Human" },
      { "field": "routes",     "value": "Oral" },
      { "OR": [
        { "field": "parameter", "value": "AUC" },
        { "field": "parameter", "value": "Cmax" }
      ]}
    ]
  }
}
```

Note the AND across fields (drug, species, route, and parameter intent). The
`parameter` request (AUC or Cmax) is an open-set field emitted as a direct API
constraint when the user asks for it as a retrieval filter.

## Entity filters

Some restrictions go through a linked entity rather than a direct field:

The PK service does not use `entityFilters`. All PK field filters are
emitted directly into the top-level `query`. Stage 3 is responsible for routing
a field's filter into `entityFilters` vs the top-level `query` when required by
the service configuration.

## Facets and display columns

- `facets`: allow-listed for PK (`drugs`, `species`, `sources`, `routes`,
  `documentYear`, `parameters`, `studyGroups`, `concomitants`, `tissueSpecific`,
  `metabolitesEnantiomers`). Used when the question asks for lists / "which" /
  categories.
- `displayColumns`: only when the user explicitly asks for specific output
  columns; otherwise omit. Uses response-item field names (see
  [inputs/fields.csv](../../inputs/fields.csv)).

## PK-specific invariants

PK always pins certain fields unless the user query already supplies them:
`concomitants` is `Fasted` or empty, `tissueSpecific` is `Not tissue-specific`,
and `metabolitesEnantiomers` is `Not metabolites/enantiomers`. These are applied
in [../03-proposed-design/stage-3-aggregation.md](../03-proposed-design/stage-3-aggregation.md).
