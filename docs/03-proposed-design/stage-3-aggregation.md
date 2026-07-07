# Stage 3 - Aggregation, fetch, and post-filtering

**Input (Stage 3A):** valid early-contributor machine subqueries from Stage 2A,
deferred large-closed-set and open-set filter components, and question components
from Stage 1.
**Input (Stage 3B):** all contributor machine subqueries (early contributors plus
any runtime-narrowed fields resolved in Stage 2B).
**Output:** the final API query, fetched datapoints, and the datapoints after all
validated runtime post-filters from Stage 2C.

This stage is deterministic assembly plus API execution. The hard per-field value
selection stays in Stage 2; Stage 3 decides how valid filters are combined, where
they are routed, and when each API call is made.

The pipeline makes at most two API calls per query: Stage 3A fetches datapoints
using only the early-contributor fields; Stage 3B fetches the final datapoints
using all resolved contributor fields. Open-set post-filtering (Stage 2C) runs
against the Stage 3B result without an additional API call.

The v0.1 implementation builds and validates the machine query and can execute it
for `countTotal`. It does not fetch full datapoint rows, so the runtime-narrowing
and post-filtering paths are documented below as the intended data-flow once row
fetching is available. The implemented open-set guard is `drop_empty_open_filters`:
live runs may probe each open-set filter in isolation and drop it only when the
API confirms a zero count.

## Steps

### 1. Keep only valid contributor filters

Stage 2A marks an early-contributor translation invalid when it returns `[]`/`None`
or when the selected candidates are not members of the field's closed set. Stage 3
does not place invalid filters in the API query. It records them as warnings so
the final result explains which user constraint could not be grounded.

Large-closed-set filters and open-set filters are held aside at this point because
their closed set is not known until early-contributor datapoints are fetched.
Stage 2B resolves large-closed-set fields iteratively; any field that still cannot
be resolved after all rounds is deferred to Stage 2C post-filtering.

### 2. Group by boolean intent

- Valid filters combine under a top-level **`AND`** by default: every field
  constrains the result.
- Filters that share a Stage-1 `boolean_group` combine with that group's
  operator first, then join the rest. Examples:
  - "AUC **or** Cmax" -> an `OR` node of two `parameter` `MATCH` filters,
    then AND-ed with the drug and species filters.
  - "AUC **and** Cmax" -> an `AND` of two `parameter` `MATCH` filters.

### 3. Route to `entityFilters` where required

All PK fields are emitted directly into the top-level `query`. The PK service
has no `entityFilters` routes in v0.1. Open-set fields that have no contributor
translation are not placed in the API query.

### 4. Apply service invariants

Rules that are not derived from the user's words but are always required by a
service are applied as deterministic post-processing:

- **concomitants.** Always pin to Fasted-or-empty:
  `{"OR":[{"MATCH":{"field":"concomitants","value":"Fasted"}},{"EMPTY":{"field":"concomitants"}}]}`.
- **tissueSpecific.** Default to `Not tissue-specific` unless the query
  already contains `tissueSpecific`.
- **metabolitesEnantiomers.** Default to `Not metabolites/enantiomers`
  unless the query already contains `metabolitesEnantiomers`.

These live in per-service invariants and are unit-tested in isolation.

### 5. Attach output options

- **`facets`** - when the question asks "which", "what are the", "list of", or
  categories, add the relevant allow-listed facet(s). PK allows `drugs`,
  `species`, `sources`, `route`, `documentYear`, `parameters`, `studyGroup`,
  `concomitants`, `tissueSpecific`, and `metabolitesEnantiomers`.
- **`displayColumns`** - when the user explicitly asks for specific output
  columns, add them from [fields.csv](../../inputs/fields.csv), e.g. "at which
  dose, regimen and route" -> `["drug","dose","route"]`.
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

### 7. Stage 3A — Execute early-contributor query and derive runtime narrowed sets

The validated early-contributor query is sent to the service API. Row fetching
must continue through the API's pagination surface until the requested row bound
is reached, all available rows are collected, or an API error is returned.
Pagination state is execution-layer metadata; Stage 2 and Stage 3 consume the
typed datapoints and do not infer pagination themselves.

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
  count-only path may still be reported, but runtime narrowing and post-filtering
  are skipped for that run.
- Tests and offline evaluation use a canonical mocked response whose rows are
  already normalized as `datapoints`; live service adapters may map whatever raw
  response key the API uses into this shape.

The fetched datapoints are passed to Stage 2B. For each large closed-set field,
Stage 2B collects unique values, checks whether the count is below
`EARLY_CONTRIBUTOR_THRESHOLD`, and translates new contributors against that
narrowed set. When Stage 2B produces new contributor subqueries, steps 1–7 repeat
with the updated contributor set until no new contributors are found.

### 8. Stage 3B — Execute final query

Once Stage 2B convergence is reached, a final API query is assembled from all
resolved contributor subqueries (early contributors plus any runtime-narrowed
fields). The same assembly rules from steps 1–6 apply. The final query is sent to
the service API and its datapoints are collected.

```
runtime_closed_set[field] =
  sorted(unique(non-empty datapoint[field] values))
```

Those runtime closed sets (from the Stage 3B datapoints) are passed to Stage 2C
for open-set post-filtering.

### 9. Apply open-set post-filters (Stage 2C)

For each valid Stage 2C post-filter translation, Stage 3 keeps only datapoints
whose field value is in the selected subset. Invalid runtime translations do not
filter the datapoints.

The final result has three auditable filter layers:

- **Early-contributor API filters:** all valid early-contributor closed-set
  filters in the Stage 3A machine query.
- **Runtime-narrowed API filters:** all large closed-set fields resolved through
  Stage 2B, included in the Stage 3B machine query.
- **Post-filter layer:** all valid open-set filters from Stage 2C, grounded
  against Stage 3B fetched datapoint values.

## Output surface

The PK service produces the JSON envelope plus fetched datapoints and post-filter
metadata.


## Example assembly

> "What is the AUC of sunitinib in human subjects after oral administration?"

`species` (286 items) and `route` (204 items) are early contributors (below the
500-item threshold). `drugs` (5,227 items) is a large closed-set field and is
deferred.

```text
A: MATCH species = "Human"         (early contributor)
B: MATCH route   = "Oral"          (early contributor)
questions: dose, parameter         (type: question -> displayColumns)
deferred:  drugs                   (large closed-set, ≥ threshold)
```

Stage 3A assembles and executes the early-contributor query, plus the PK service
invariants (`concomitants`, `tissueSpecific`, `metabolitesEnantiomers` defaults):

```json
{
  "query": {
    "AND": [
      { "MATCH": { "field": "species", "value": "Human" } },
      { "MATCH": { "field": "route",   "value": "Oral" } }
    ]
  },
  "displayColumns": ["drug", "dose", "parameter"]
}
```

Stage 2B scans the returned datapoints and collects unique `drugs` values. If
that list is below `EARLY_CONTRIBUTOR_THRESHOLD`, it is translated against the
narrowed drug set and the result becomes a new contributor subquery. Stage 3B
assembles the final query combining all contributor filters. If the `drugs`
unique count still exceeds the threshold, `drugs` is excluded from the API query
(it is a closed-set field, not an open-set field, so it is not post-filtered).

If the question also had an open-set phrase such as `studyGroup = "hepatic
impairment"`, that phrase is deferred until Stage 3B has fetched datapoints. The
unique `studyGroup` values in those datapoints become the runtime closed set;
Stage 2C translates it and applies the matching subset as a post-filter over the
final datapoints.
