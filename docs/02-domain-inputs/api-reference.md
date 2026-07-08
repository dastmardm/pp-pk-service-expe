# PharmaPendium API reference

**Base URL:** `https://api-dev.ppnp.cm-elsevier.com`

The PharmaPendium API exposes pharmaceutical data extracted manually from FDA
and EMA approval documents and from published literature. Every service follows
the same three-endpoint pattern: a simple filter search (GET and POST), an
advanced structured-query search (POST only), and a taxonomy fuzzy-lookup (GET
and POST). All search responses are limited to **500 records per request**;
paginate using `limitation.firstRow` and `limitation.count`.

---

## Common request shapes

### Simple filter (GET)

Array parameters are passed as comma-separated values. Within a single value the
pipe character `|` replaces commas to avoid ambiguity.

### Simple filter (POST) — `<Service>APIFilter`

```json
{
  "drugs":          ["DrugA", "DrugB"],
  "drugsFuzzy":     ["Sunitinib*"],
  "drugsAndSynonyms": ["aspirin"],
  "facets":         ["drugs", "species"],
  "displayColumns": ["drug", "dose", "route"],
  "sortColumns":    [{ "column": "drug", "isAscending": true }],
  "limitation":     { "firstRow": 0, "count": 100 },
  "leaf":           false
}
```

Fields not used by a service are omitted from that service's filter schema.

### Advanced structured query (POST) — `ExtendedQueryFilter`

Shared by all services. Use this to express complex boolean logic.

```json
{
  "query": { ... },
  "entityFilters": [ ... ],
  "facets": [ ... ],
  "leafOnly": false,
  "mixtureExpansion": false,
  "limitation": { "firstRow": 0, "count": 100 }
}
```

#### `query` constraint types

| Type | Shape | Notes |
|------|-------|-------|
| `MATCH` | `{ "field": "…", "value": "…" \| ["…"], "fuzzy": bool, "boost": number }` | Exact or fuzzy token match. |
| `REGEX` | `{ "field": "…", "pattern": "…", "boost": number }` | Regular expression match. |
| `PROXIMITY` | `{ "field": "…", "value": "word1 word2", "distance": number, "boost": number }` | Words within `distance` positions. |
| `RANGE` | `{ "field": "…", "min": number, "max": number, "boost": number }` | Numeric range. |
| `DATE_RANGE` | `{ "field": "…", "min": "YYYY-MM-DD", "max": "YYYY-MM-DD", "boost": number }` | Date range. |
| `EMPTY` | `{ "field": "…", "boost": number }` | Field is absent or empty. |
| `AND` | `{ "AND": [ constraint, … ] }` | All children must match; two or more children required. |
| `OR` | `{ "OR": [ constraint, … ] }` | Any child must match; two or more children required. |
| `NOT` | `{ "NOT": constraint }` | Exactly one child; negates the constraint. |

### Taxonomy lookup — `FuzzyLookupFilter`

GET form accepts `query` (string, required) and `taxonomy` (enum, required) as
query parameters. POST body:

```json
{ "query": "sulfa*", "taxonomy": "Drugs" }
```

#### `taxonomy` enum values (PK service)

`Concomitants`, `ConcomitantSubstances`, `Drugs`, `PKParameters`,
`Routes`, `Sources`, `Species`

### Common response types

**`SortColumn`**

```json
{ "column": "drug", "isAscending": true }
```

**`Limitation`**

```json
{ "firstRow": 0, "count": 100 }
```

**`TreeCommonLookupEntity`** — returned by all `lookupFuzzy` endpoints

```json
{
  "results": [
    {
      "name": "Sunitinib",
      "code": "DRUG-12345",
      "isLeaf": true,
      "children": []
    }
  ]
}
```

**All `SearchResponse*` objects** follow this envelope:

```json
{
  "entities": [ { "...": "..." } ],
  "facets":   { "drugs": { "...": "..." } },
  "totalCount": 412
}
```

### HTTP status codes

| Code | Meaning |
|------|---------|
| 200 | Request succeeded; data returned. |
| 400 | Invalid parameters or malformed request body. |
| 401 | Unauthenticated. |
| 403 | Forbidden — insufficient permissions. |
| 404 | Resource not found. |
| 500 | Server error. |

---

## Pharmacokinetics (PK) Service

Manually extracted preclinical and clinical PK data from FDA and EMA packages.
Supports food-effect, drug-interaction, and comparative-exposure queries.

**Base path:** `/v1/pk`

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/pk/search` | Simple filter search. |
| POST | `/v1/pk/search` | Simple filter search (JSON body). |
| POST | `/v1/pk/search/advanced` | Structured-query search. |
| GET | `/v1/pk/lookupFuzzy` | Taxonomy lookup. |
| POST | `/v1/pk/lookupFuzzy` | Taxonomy lookup (JSON body). |

### `PKAPIFilter` fields

| Field | Type | Description |
|-------|------|-------------|
| `drugs` | `array<string>` | Exact drug taxonomy terms. |
| `drugsAndSynonyms` | `array<string>` | Exact drug matches with synonyms. |
| `drugsFuzzy` | `array<string>` | Wildcard drug names. |
| `species` | `array<string>` | Species taxonomy. |
| `routes` | `array<string>` | Routes of administration. |
| `documentSource` | `array<string>` | Source taxonomy terms. |
| `parameters` | `array<string>` | PK parameter names from the PK Parameters taxonomy. |
| `studyGroups` | `array<string>` | Study population descriptors (e.g. `hepatic impairment`). |
| `concomitants` | `array<string>` | Food-effect state for the study: `Fed` or `Fasted`. |
| `radioLabels` | `array<string>` | Radioactive labels used in the study. |
| `metabolitesEnantiomers` | `array<string>` | Metabolite or enantiomer designations. |
| `tissueSpecific` | `array<string>` | Tissue-specific parameter designations. |
| `parameterValues` | `array<object>` | Numeric value constraints for PK parameters. |
| `years` | `array<integer>` | Publication years. |
| `facets` | `array<string>` | Facet fields. |
| `displayColumns` | `array<string>` | Response fields to include. |
| `sortColumns` | `array<SortColumn>` | Sort order. |
| `limitation` | `Limitation` | Pagination. |
| `leaf` | `boolean` | End terms only. |

The pipeline targets this service exclusively in v0.1. Service invariants applied
by Stage 3 (unless the query already contains the field):

- `concomitants` defaults to `Fasted`-or-empty.
- `tissueSpecific` defaults to `Not tissue-specific`.
- `metabolitesEnantiomers` defaults to `Not metabolites/enantiomers`.

See [field-taxonomy.md](field-taxonomy.md) for the full PK field-to-bucket map.
