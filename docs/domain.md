# Domain contract

The translator targets the PharmaPendium pharmacokinetics service at
`/v1/pk/search/advanced`. It produces a machine-query payload, optionally executes
that payload, reads `data.countTotal`, and fetches datapoints when a count-gated
branch returns fewer than `1000` rows.

## Advanced query payload

The top-level payload is:

```json
{
  "query": { "...": "boolean filter tree" },
  "entityFilters": [],
  "facets": [],
  "sortColumns": [],
  "displayColumns": [],
  "leafOnly": false,
  "mixtureExpansion": false,
  "limitation": { "firstRow": 0, "count": 100 }
}
```

`query` has exactly one top-level constraint. Boolean nodes use explicit
`AND`/`OR`/`NOT` wrappers. Field-level leaves use the unwrapped API shape.

| Operator | API leaf or node shape | Use |
|----------|------------------------|-----|
| `MATCH` | `{"field": F, "value": V}` | Exact value or value list. |
| `REGEX` | `{"field": F, "pattern": P}` | Free-text or substring match. |
| `RANGE` | `{"field": F, "min": n, "max": n}` | Numeric thresholds. |
| `DATE_RANGE` | `{"field": F, "min": "YYYY-MM-DD", "max": "YYYY-MM-DD"}` | Date thresholds. |
| `EMPTY` | `{"field": F}` | Field is empty or absent. |
| `AND` | `{"AND": [c1, c2]}` | All child constraints. |
| `OR` | `{"OR": [c1, c2]}` | Any child constraint. |
| `NOT` | `{"NOT": c}` | Negation. |

Example:

```json
{
  "query": {
    "AND": [
      { "field": "drugsFuzzy", "value": ["Sunitinib*"] },
      { "field": "species", "value": "Human" },
      { "field": "routes", "value": "Oral" },
      { "OR": [
        { "field": "parameter", "value": "AUC" },
        { "field": "parameter", "value": "Cmax" }
      ]}
    ]
  }
}
```

Translation still records the typed machine-subquery operator internally.
Aggregation uses that metadata to validate and assemble the API tree.

## PK request fields

CSV-backed closed fields are classified by the number of items in the current
input catalog. Fewer than `1000` items makes the field small closed, also called
early. `1000` or more items keeps the field in the closed bucket. Non-CSV buckets
keep their own names.

| Field | Bucket | Backing source | Value-set size | Emission |
|-------|--------|----------------|----------------|----------|
| `drugs` | closed | `inputs/drugs.csv` | 5,226 items | Emits `drugsFuzzy`; singleton values remain arrays such as `["Sunitinib*"]`. |
| `species` | small closed / early | `inputs/species.csv` | 285 items | Emits taxonomy labels or supported class labels. |
| `routes` | small closed / early | `inputs/route.csv` | 203 items | Emits route labels such as `Oral`. |
| `documentSource` | small closed / early | `inputs/sources.csv` | 55 items | Emits source labels. |
| `documentYear` | small closed / early | `inputs/document_year.csv` | 117 items | Emits year/range constraints. |
| `sex` | enum | `Male`, `Female`, `Both` | 3 values | Emits enum value. |
| `isPreclinical` | boolean | `true`, `false` | 2 values | Emits boolean value. |
| `concomitants` | enum/invariant | `Fed`, `Fasted` | 2 values | User value wins; otherwise PK adds Fasted-or-empty. |
| `tissueSpecific` | enum/invariant | `Tissue-specific`, `Not tissue-specific` | 2 values | User value wins; otherwise PK adds `Not tissue-specific`. |
| `metabolitesEnantiomers` | enum/invariant | `Not metabolites/enantiomers`, `Metabolite`, `Enantiomer` | 3 values | User value wins; otherwise PK adds `Not metabolites/enantiomers`. |
| `parameter` | open | No complete local value set | Not bounded | Row-side filter below the row gate; emits direct `MATCH` or `REGEX` in the full API branch. PK parameter mentions such as AUC and Cmax are retrieval filters. |
| `parameterDisplay` | open | No complete local value set | Not bounded | Row-side filter below the row gate; emits direct `MATCH` or `REGEX` in the full API branch. |
| `studyGroups` | open | No complete local value set | Not bounded | Row-side filter below the row gate; emits direct `REGEX` in the full API branch, including built-in impairment synonyms. |
| `age` | open | No complete local value set | Not bounded | Row-side filter below the row gate; emits direct `REGEX` in the full API branch. |
| `dose` | open | No complete local value set | Not bounded | Row-side filter below the row gate; emits direct `MATCH` or `REGEX` in the full API branch. |
| `duration` | open | No complete local value set | Not bounded | Row-side filter below the row gate; emits direct `MATCH` or `REGEX` in the full API branch. |

The PharmaPendium API also exposes fields that the translator does not emit.
`drugsAndSynonyms`, `radioLabels`, and `parameterValues` are API-only for this
translator.

## Facets and display columns

PK allows facets for `drugs`, `species`, `sources`, `routes`, `documentYear`,
`parameters`, `studyGroups`, `concomitants`, `tissueSpecific`, and
`metabolitesEnantiomers`. `displayColumns` use response-item field names such as
`drug`, `dose`, `route`, and `parameter`.

Fields requested only as outputs become facets or display columns. They are not
filters unless the user also uses them to restrict retrieval.

## Input files

| File | Purpose |
|------|---------|
| `inputs/drugs.csv` | Drug and drug-class taxonomy for `drugs` and `drugsFuzzy`. |
| `inputs/species.csv` | Species taxonomy and class hierarchy. |
| `inputs/route.csv` | Route labels and usage counts for `routes`. |
| `inputs/sources.csv` | Document source taxonomy. |
| `inputs/document_year.csv` | Year/range labels for `documentYear`. |
| `inputs/fields.csv` | Response/display field catalog. |
| `inputs/query_criteria_fields.csv` | Request-side criteria and types. |
| `inputs/enums.csv` | API enum cross-checks, including fuzzy lookup taxonomy values. |
| `docs/PPPK.xlsx` | SME PK evaluation workbook; automated evaluation uses only the `PK_Query` sheet. |

CSV-backed closed fields emit preferred labels from the `name` column. The
`id`, `parent_id`, and `parent_name` columns provide stable keys and hierarchy
relationships where present.

## Response contract

Each API count branch reads the count envelope:

```json
{
  "data": {
    "countTotal": 412
  }
}
```

When the active branch has `countTotal < 1000`, the translator paginates the same
query and reads datapoints from `data.datapoints` or `data.rows`:

```json
{
  "data": {
    "countTotal": 412,
    "datapoints": [
      { "drug": "Sunitinib", "parameter": "AUC", "route": "Oral" }
    ],
    "pageState": { "...": "..." }
  }
}
```

Fetched datapoints are dictionaries keyed by PharmaPendium response fields. The
row-filtering contract uses those field values to apply pending closed, enum,
boolean, invariant, and open filters. The final count is
`final_filtered_count` for a row branch and `countTotal` for the full API branch.
