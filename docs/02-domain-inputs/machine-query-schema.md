# The machine-query format (target output)

This is what the pipeline must ultimately produce. It is the request body the
PharmaPendium search API (`/v1/safety/search/advanced`, `/v1/pk/search/advanced`,
…) accepts.

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
| `effects`, `species`, `routes`, `sources` | `array<string>` |
| `doseTypes`, `metaboliteTypes`, `toxicityParameters` | `array<string>` |
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

> "drugs causing neutropenia or thrombocytopenia in human"

```json
{
  "query": {
    "AND": [
      { "MATCH": { "field": "species", "value": "Human" } },
      { "OR": [
        { "MATCH": { "field": "effects", "value": ["Neutropenia", "Granulocytopenia", "..."] } },
        { "MATCH": { "field": "effects", "value": ["Thrombocytopenia", "Immune thrombocytopenia", "..."] } }
      ]}
    ]
  }
}
```

Note the two layers of boolean: an **AND across fields** (species ∧ effects) and
an **OR within the effects field** (neutropenia ∨ thrombocytopenia), each effect
already **expanded** to its taxonomy preferred terms.

## Entity filters

Some restrictions go through a linked entity rather than a direct field:

```json
"entityFilters": [
  { "DrugsIndications": { "MATCH": { "field": "indications", "value": "Breast cancer" } } }
]
```

Supported entity names differ by service (Safety: `Drugs`, `DrugsTargets`,
`DrugsIndications`, `Effects`, `Sources`, `Indications`; PK adds `Species`,
`Concomitants`, `PKParameters`). Stage 3 is responsible for routing a field's
filter into `entityFilters` vs the top-level `query` when required.

## Facets and display columns

- `facets`: allow-listed per service (Safety: `drugs, species, sources, effects,
  route, doseType, documentYear`). Used when the question asks for lists /
  "which" / categories.
- `displayColumns`: only when the user explicitly asks for specific output
  columns; otherwise omit. Uses response-item field names (see
  [inputs/fields.csv](../../inputs/fields.csv)).

## Service variations

The three services share this shape but differ in fields, facet allow-lists, and
invariants. The RTB/CrossFire service uses a different surface syntax
(`where_clause` strings like `DAT.VTYPE='AUC' AND DAT.BSPECIE='rat'`) but the
same underlying idea — a conjunction of `(operator, field, value)` filters. The
service-specific invariants (e.g. PK always pins `concomitants` to Fasted-or-
empty and defaults `tissueSpecific`) are applied in
[../03-proposed-design/stage-3-aggregation.md](../03-proposed-design/stage-3-aggregation.md).
