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
  "leafOnly":       false
}
```

The request-side field/type catalogue is in
[inputs/query_criteria_fields.csv](../../inputs/query_criteria_fields.csv):

| field | type |
|-------|------|
| `drugs`, `drugsFuzzy`, `drugsAndSynonyms` | `array<string>` |
| `species`, `routes`, `documentSource` | `array<string>` |
| `years` | `array<integer>` |
| `facets`, `displayColumns` | `array<string>` |
| `sortColumns` | `array<SortColumn>` |
| `limitation` | `Limitation` |
| `leaf` | `boolean` |

## The `query` tree: filters all the way down

The `query` is a tree with **exactly one top-level constraint**. Every node is
one of these constraint types (the "operators"):

| Operator | Shape | Use for |
|----------|-------|---------|
| `MATCH` | `{"MATCH": {"field": F, "value": V}}` where `V` is a string or array | exact value(s) on a field |
| `OR` | `{"OR": [c1, c2, …]}` (≥2) | any of |
| `AND` | `{"AND": [c1, c2, …]}` (≥2) | all of |
| `NOT` | `{"NOT": c}` (single) | negation |
| `REGEX` | `{"REGEX": {"field": F, "pattern": P}}` | substring / free-text fields |
| `RANGE` | `{"RANGE": {"field": F, "min": n, "max": n}}` | numeric thresholds |
| `DATE_RANGE` | `{"DATE_RANGE": {"field": F, "min": "YYYY-MM-DD", "max": …}}` | dates |
| `EMPTY` | `{"EMPTY": {"field": F}}` | field is empty/absent |
| `PROXIMITY` | (text proximity) | rarely used |

**Every leaf is an `(operator, field, value)` triple.** That is the unit Stage 2
produces. The interior `AND`/`OR`/`NOT` nodes are the structure Stage 3 builds.

### Example

> "AUC or Cmax of Sunitinib in human after oral administration"

```json
{
  "query": {
    "AND": [
      { "MATCH": { "field": "drugsFuzzy", "value": ["Sunitinib*"] } },
      { "MATCH": { "field": "species",    "value": "Human" } },
      { "MATCH": { "field": "routes",     "value": "Oral" } }
    ]
  }
}
```

Note the AND across fields (drug ∧ species ∧ route). The `parameter` request
(AUC or Cmax) is an open-set field emitted as a direct API constraint when the
user asks for it as a filter.

## Entity filters

Some restrictions go through a linked entity rather than a direct field:

The PK service does not use `entityFilters`. All PK field filters are
emitted directly into the top-level `query`. Stage 3 is responsible for routing
a field's filter into `entityFilters` vs the top-level `query` when required by
the service configuration.

## Facets and display columns

- `facets`: allow-listed for PK (`drugs`, `species`, `sources`, `route`,
  `documentYear`, `parameters`, `studyGroup`, `concomitants`, `tissueSpecific`,
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
