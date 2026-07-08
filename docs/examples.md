# Worked examples

These examples show how representative PK questions enter the count-gated
pipeline. Counts are branch decisions: `countTotal < 1000` triggers datapoint
fetch and local filtering; `countTotal >= 1000` triggers the next translation
layer.

## AUC of Sunitinib in human after oral administration

Question:

```text
What is the AUC of Sunitinib in human after oral administration?
```

Decomposition:

```json
[
  { "field": "drugs", "nl_fragment": "Sunitinib", "type": "filter", "source": "query" },
  { "field": "species", "nl_fragment": "human", "type": "filter", "source": "query" },
  { "field": "routes", "nl_fragment": "oral", "type": "filter", "source": "query" },
  { "field": "parameter", "nl_fragment": "AUC", "type": "filter", "source": "query" },
  { "field": "value", "nl_fragment": "what is AUC", "type": "question", "source": "query" }
]
```

TERMite enrichment attaches drug, species, route, and PK-parameter annotations to
the matching fragments. Small-closed/early translation grounds:

| Field | Translation |
|-------|-------------|
| `species` | `MATCH species = "Human"` |
| `routes` | `MATCH routes = "Oral"` |

Small-closed API query:

```json
{
  "query": {
    "AND": [
      { "field": "species", "value": "Human" },
      { "field": "routes", "value": "Oral" },
      { "OR": [
        { "field": "concomitants", "value": "Fasted" },
        { "field": "concomitants" }
      ]},
      { "field": "tissueSpecific", "value": "Not tissue-specific" },
      { "field": "metabolitesEnantiomers", "value": "Not metabolites/enantiomers" }
    ]
  },
  "displayColumns": ["drug", "parameter", "dose", "route"]
}
```

When this count is below `1000`, the translator fetches datapoints and applies
the pending `drugs = Sunitinib` and `parameter = AUC` filters locally. When this
count is at least `1000`, closed translation adds the `drugs` filter to the API
query and the next count gate decides whether `parameter = AUC` is applied on
rows or translated into the full API query.

## Cmax of Cabozantinib in adults with hepatic impairment

Question:

```text
Cmax of Cabozantinib in adults with hepatic impairment after oral administration
```

Decomposition:

```json
[
  { "field": "drugs", "nl_fragment": "Cabozantinib", "type": "filter", "source": "query" },
  { "field": "species", "nl_fragment": "adults", "type": "filter", "source": "query" },
  { "field": "routes", "nl_fragment": "oral administration", "type": "filter", "source": "query" },
  { "field": "parameter", "nl_fragment": "Cmax", "type": "filter", "source": "query" },
  { "field": "studyGroups", "nl_fragment": "hepatic impairment", "type": "filter", "source": "query" },
  { "field": "age", "nl_fragment": "adults", "type": "filter", "source": "query" }
]
```

Small-closed/early translation grounds `species` and `routes`. If that branch
remains at or above `1000`, closed translation grounds `drugs`. When the closed
branch also remains at or above `1000`, open-set fields are translated into the
API query:

| Field | Translation |
|-------|-------------|
| `parameter` | `MATCH parameter = "Cmax"` |
| `studyGroups` | `REGEX studyGroups` for hepatic-impairment synonyms |
| `age` | `REGEX age = "adult"` |

Full API query:

```json
{
  "query": {
    "AND": [
      { "field": "drugsFuzzy", "value": ["Cabozantinib*"] },
      { "field": "species", "value": "Human" },
      { "field": "routes", "value": "Oral" },
      { "field": "parameter", "value": "Cmax" },
      { "field": "studyGroups", "pattern": "(hepatic impairment|liver impairment|hepatic dysfunction)" },
      { "field": "age", "pattern": "adult" },
      { "OR": [
        { "field": "concomitants", "value": "Fasted" },
        { "field": "concomitants" }
      ]},
      { "field": "tissueSpecific", "value": "Not tissue-specific" },
      { "field": "metabolitesEnantiomers", "value": "Not metabolites/enantiomers" }
    ]
  },
  "displayColumns": ["drug", "parameter", "dose", "route"]
}
```

The evaluated count for this branch is the API `countTotal` from the full query.

## Half-life of Sunitinib in rats in fasted state

Question:

```text
What is the half-life of Sunitinib in rats after oral administration in fasted state?
```

Decomposition:

```json
[
  { "field": "drugs", "nl_fragment": "Sunitinib", "type": "filter", "source": "query" },
  { "field": "species", "nl_fragment": "rats", "type": "filter", "source": "query" },
  { "field": "routes", "nl_fragment": "oral", "type": "filter", "source": "query" },
  { "field": "concomitants", "nl_fragment": "fasted state", "type": "filter", "source": "query" },
  { "field": "parameter", "nl_fragment": "half-life", "type": "filter", "source": "query" },
  { "field": "value", "nl_fragment": "what is the half-life", "type": "question", "source": "query" }
]
```

The early query contains the small-closed `species` and `routes` filters. When
that count is at least `1000`, closed translation adds `drugs`. The
user-supplied `concomitants` filter keeps its enum/invariant bucket and replaces
the default Fasted-or-empty invariant for that field.

Closed API query:

```json
{
  "query": {
    "AND": [
      { "field": "drugsFuzzy", "value": ["Sunitinib*"] },
      { "field": "species", "value": "Rat" },
      { "field": "routes", "value": "Oral" },
      { "field": "concomitants", "value": "Fasted" },
      { "field": "tissueSpecific", "value": "Not tissue-specific" },
      { "field": "metabolitesEnantiomers", "value": "Not metabolites/enantiomers" }
    ]
  },
  "displayColumns": ["drug", "parameter", "dose", "route"]
}
```

When this count is below `1000`, datapoints are fetched and the pending
`parameter = half-life` filter is applied locally.
