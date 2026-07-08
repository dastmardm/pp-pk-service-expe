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
the matching fragments. Early closed-set translation grounds:

| Field | Translation |
|-------|-------------|
| `drugs` | `MATCH drugsFuzzy = ["Sunitinib*"]` |
| `species` | `MATCH species = "Human"` |
| `routes` | `MATCH routes = "Oral"` |

Early API query:

```json
{
  "query": {
    "AND": [
      { "field": "drugsFuzzy", "value": ["Sunitinib*"] },
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
the pending `parameter = AUC` filter locally. The final count is the number of
datapoints remaining after that row filter.

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

Early closed-set translation grounds `drugs`, `species`, and `routes`. If that
branch remains at or above `1000`, the non-early closed-set branch runs. When the
closed-set branch also remains at or above `1000`, open-set fields are translated
into the API query:

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

The early query contains `drugs`, `species`, and `routes`. When that count is at
least `1000`, non-early closed-set translation adds the user-supplied
`concomitants = Fasted` filter. The user-supplied `concomitants` filter replaces
the default Fasted-or-empty invariant for that field.

Closed-set API query:

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
