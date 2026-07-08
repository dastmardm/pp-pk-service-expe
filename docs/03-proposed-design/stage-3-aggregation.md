# Stage 3 - Aggregation and execution

**Input:** valid machine subqueries from Stage 2 and question components from
Stage 1.
**Output:** the final API query, validation result, optional open-set probe
warnings, and `countTotal` when execution is enabled.

This stage is deterministic assembly plus API execution. The hard per-field value
selection stays in Stage 2; Stage 3 decides how valid filters are combined, where
they are routed, and whether live execution probes open-set filters before the
final API call.

## Steps

### 1. Keep only valid contributor filters

Stage 2A marks an early-contributor translation invalid when it returns `[]`/`None`
or when the selected candidates are not members of the field's closed set. Stage 3
does not place invalid filters in the API query. It records them as warnings so
the final result explains which user constraint could not be grounded.

Open-set filters are valid direct API constraints when Stage 2 emits them.

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
has no `entityFilters` routes.

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
- `sortColumns` and `leafOnly` exist on the `MachineQuery` model. `sortColumns`
  carries API sort instructions when a caller supplies them, and `leafOnly`
  requests end-term results only. User-facing Stage 3 leaves `sortColumns` unset
  and leaves `leafOnly` at its default `false` value.

### 6. Validate the API query

Before execution, Stage 3 validates that:

- exactly one top-level constraint exists in `query`;
- all constraint types are upper-case and well-formed;
- facet fields are within the service allow-list;
- `OR`/`AND` have at least two children and `NOT` has exactly one.

A validation failure stops the API query from being treated as a successful
closed-filter pass.

### 7. Optionally probe open-set filters

When `probe_open_filters` is enabled for live execution, Stage 3 runs each
open-set filter in isolation before final aggregation. A confirmed zero-count
probe drops that filter and records a warning. Probe errors keep the filter.

### 8. Execute the final query

The validated query is sent to the service API for `countTotal`. The execution
result records the count, status, and any error details.

### 9. Record the auditable filter layers

The final result records the valid closed-set API filters, valid open-set API
filters, service invariants, output options, and any zero-count probe warnings.

## Output surface

The PK service produces the JSON envelope plus execution metadata.


## Example assembly

> "What is the AUC of sunitinib in human subjects after oral administration?"

`species`, `routes`, and `drugs` are closed-set fields.

```text
A: MATCH species    = "Human"
B: MATCH routes     = "Oral"
C: MATCH drugsFuzzy = ["Sunitinib*"]
questions: dose, parameter         (type: question -> displayColumns)
```

Stage 3 assembles and executes the query, plus the PK service invariants
(`concomitants`, `tissueSpecific`, `metabolitesEnantiomers` defaults):

```json
{
  "query": {
    "AND": [
      { "MATCH": { "field": "species", "value": "Human" } },
      { "MATCH": { "field": "routes",  "value": "Oral" } },
      { "MATCH": { "field": "drugsFuzzy", "value": ["Sunitinib*"] } }
    ]
  },
  "displayColumns": ["drug", "dose", "parameter"]
}
```

If the question also had an open-set phrase such as `studyGroup = "hepatic
impairment"`, Stage 2 emits a direct open-set constraint. When live execution
enables zero-count probes, Stage 3 probes that filter in isolation before the
final query and drops it only when the API confirms a zero count.
