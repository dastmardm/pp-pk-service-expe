# Stage 3 - Aggregation, fetch, and post-filtering

**Input:** valid input closed-set machine subqueries from Stage 2A, deferred
open-set filter components, and question components from Stage 1.
**Output:** one closed-filter API query, fetched datapoints, and the datapoints
after any validated runtime closed-set post-filters.

This stage is deterministic assembly plus API execution. The hard per-field
value selection stays in Stage 2; Stage 3 decides how valid filters are combined,
where they are routed, and when the API is called.

The v0.1 implementation builds and validates the machine query and can execute it
for `countTotal`. It does not fetch full datapoint rows, so runtime closed-set
post-filtering is documented below as the row-level design path. The implemented
open-set guard is `drop_empty_open_filters`: live runs may probe each open-set
filter in isolation and drop it only when the API confirms a zero count.

## Steps

### 1. Keep only valid input closed-set filters

Stage 2A marks a closed-set translation invalid when it returns `[]`/`None` or
when the selected candidates are not members of the field's closed set. Stage 3
does not place invalid filters in the API query. It records them as warnings so
the final result explains which user constraint could not be grounded.

In the row-level design, open-set filters are held aside at this point because
their closed set is not known until datapoints are fetched. In v0.1, open-set
filters have already been translated as `MATCH` or `REGEX` subqueries and may be
kept or removed by the zero-count probe before aggregation.

### 2. Group by boolean intent

- Valid filters combine under a top-level **`AND`** by default: every field
  constrains the result.
- Filters that share a Stage-1 `boolean_group` combine with that group's
  operator first, then join the rest. Examples from the gold set:
  - Q13 effects "neutropenia **or** thrombocytopenia" -> an `OR` node of two
    expanded `effects` `MATCH` filters, then AND-ed with `species=Human`.
  - Q14 effects "neutropenia **and** cytopenia" -> an `AND` of two expanded
    `effects` `MATCH` filters.
  - Q7 asks for both human and preclinical populations. The Safety retrieval
    rule represents that as an `OR` over `species=Human` and
    `isPreclinical=true`; downstream answer logic can compare the two cohorts.

### 3. Route to `entityFilters` where required

Some input closed-set fields must be expressed via a linked entity rather than
the top-level `query`. Stage 3 moves them:

- Safety: `indications` -> `DrugsIndications`.
- `species`, `route`, and `toxicityParameter` stay as direct top-level fields.
- PK has no configured entity routes in v0.1.

A per-service routing table drives this. Open-set fields that have no input
closed set are not routed into the first API query.

### 4. Apply service invariants

Rules that are not derived from the user's words but are always required by a
service are applied as deterministic post-processing:

- **PK - concomitants.** Always pin to Fasted-or-empty:
  `{"OR":[{"MATCH":{"field":"concomitants","value":"Fasted"}},{"EMPTY":{"field":"concomitants"}}]}`.
- **PK - tissueSpecific.** Default to `Not tissue-specific` unless the query
  already contains `tissueSpecific`.
- **PK - metabolitesEnantiomers.** Default to `Not metabolites/enantiomers`
  unless the query already contains `metabolitesEnantiomers`.
- **RTB - category.** Add `DAT.CATEG = "Pharmacokinetic"` when no category is
  present, because the RTB where-clause surface requires a non-empty category.

These live in per-service invariants and are unit-tested in isolation.

### 5. Attach output options

- **`facets`** - when the question asks "which", "what are the", "list of", or
  categories, add the relevant allow-listed facet(s). Safety allows `drugs`,
  `species`, `sources`, `effects`, `route`, `doseType`, and `documentYear`.
- **`displayColumns`** - when the user explicitly asks for specific output
  columns, add them from [fields.csv](../../inputs/fields.csv), e.g. "at which
  dose, regimen and route" -> `["drug","dose","doseType","route"]`.
- `sortColumns` and `leafOnly` exist on the `MachineQuery` model, but v0.1 does
  not derive them from user intent.

### 6. Validate the API query

Before execution, Stage 3 validates that:

- exactly one top-level constraint exists in `query`;
- all constraint types are upper-case and well-formed;
- facet fields are within the service allow-list;
- `OR`/`AND` have at least two children and `NOT` has exactly one.

A validation failure stops the API query from being treated as a successful
closed-filter pass.

### 7. Execute and build runtime closed sets

The validated closed-filter query is sent to the service API. The returned
datapoints are then scanned field-by-field for every deferred open-set filter.
Row fetching must continue through the API's pagination surface until the
requested row bound is reached, all available rows are collected, or an API error
is returned. Pagination state is execution-layer metadata; Stage 2 and Stage 3
consume the typed datapoints and do not infer pagination themselves.

The execution layer normalizes service-specific API responses into this typed row
result before any stage sees them:

```json
{
  "ok": true,
  "count_total": 123,
  "datapoints": [{ "...": "..." }],
  "status": 200,
  "error": null,
  "page_state": { "page": 1, "next": null }
}
```

- `datapoints` is a list of flat record dictionaries keyed by the API/display
  field names in the service configuration.
- `count_total` is copied from the same response count used by count-only
  execution when present.
- `page_state` is opaque execution metadata; downstream stages may log it but
  must not branch on raw API pagination keys.
- If row data is unavailable for a service or response, `ok=false`,
  `datapoints=[]`, and `error` explains that row fetching was unavailable. The
  count-only path may still be reported, but runtime post-filtering is skipped
  for that run.
- Tests and offline evaluation use a canonical mocked response whose rows are
  already normalized as `datapoints`; live service adapters may map whatever raw
  response key the API uses into this shape.

```
runtime_closed_set[field] =
  sorted(unique(non-empty datapoint[field] values))
```

Those runtime closed sets are passed back through the Stage 2 closed-set
translator. The translator receives the user's pool for the open-set field and may
return only a subset of the fetched values.

### 8. Apply post-filters

For each valid runtime closed-set translation, Stage 3 keeps only datapoints
whose field value is in the selected subset. Invalid runtime translations do not
filter the datapoints.

The final result therefore has two auditable filter layers:

- **API-layer filters:** all valid input closed-set filters in the machine query.
- **Post-filter layer:** all valid open-set filters grounded against fetched
  datapoint values.

## Output surface per service

- **Safety / PK** -> the JSON envelope plus fetched datapoints and post-filter
  metadata.
- **RTB / CrossFire** -> a `where_clause` string over the closed-set query plus
  fetched rows and post-filter metadata. The same filter set has a different
  serializer.

## Example assembly

Stage 2A produced (for Q13):

```text
A: MATCH species = "Human"
B: MATCH effects = [neutropenia terms...]      boolean_group: g1/OR
C: MATCH effects = [thrombocytopenia terms...] boolean_group: g1/OR
questions: dose, doseType, route   (type: question -> displayColumns)
```

Stage 3 assembles and executes:

```json
{
  "query": {
    "AND": [
      { "MATCH": { "field": "species", "value": "Human" } },
      { "OR": [
        { "MATCH": { "field": "effects", "value": ["Neutropenia", "Granulocytopenia"] } },
        { "MATCH": { "field": "effects", "value": ["Thrombocytopenia", "Immune thrombocytopenia"] } }
      ]}
    ]
  },
  "displayColumns": ["drug", "dose", "doseType", "route"]
}
```

If the same question also had an open-set phrase such as `parameterComment =
"maternal toxicity"`, that phrase would be deferred. After the query above
fetches datapoints, the unique `parameterComment` values in those datapoints
become the runtime closed set, and only then is the comment filter translated and
applied as a post-filter.
