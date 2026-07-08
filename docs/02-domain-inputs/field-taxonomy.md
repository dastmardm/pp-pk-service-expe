# Filterable fields and value sets

Every searchable filter field belongs to exactly one bucket in the service
configuration. The bucket determines when the field can be translated and where
its legal values come from.

- **Closed-set fields** have a complete value set before query execution. The set
  comes from an `inputs/` taxonomy CSV, an inline enum, or a boolean domain. Stage
  2 may only emit values that are members of that set.
- **Open-set fields** do not have a complete value set in `inputs/`. The row-level
  design defers them until fetched datapoints provide a runtime closed set for
  post-filtering. In v0.1, these fields are translated directly to `MATCH` or
  `REGEX` constraints and live runs may drop a filter only when an isolated API
  count probe confirms that it matches no records.

A **filterable field** is any field Stage 1 may emit as a `type=filter`
component. Fields requested only as outputs become facets or `displayColumns`;
they are not filters unless the user also uses them to restrict retrieval.

## Input closed sets

These fields have their full legal value set available before query execution.
For CSV-backed fields, the preferred labels in the `name` column are the values
that may be emitted to the API.

| Field | Backing set | Rows | Hierarchical? | Typical operator |
|-------|-------------|------|---------------|------------------|
| `drugs` / `drugsFuzzy` | [drugs.csv](../../inputs/drugs.csv) | 5,227 | yes (drug -> class via `parent_name`) | `MATCH` (+ trailing `*` for fuzzy drug leaves) |
| `species` | [species.csv](../../inputs/species.csv) | 286 | yes (class -> members, e.g. Rodent/Primate) | `MATCH` with class/leaf handling |
| `routes` | [route.csv](../../inputs/route.csv) | 204 | flat (+ usage counts) | `MATCH` |
| `documentSource` | [sources.csv](../../inputs/sources.csv) | 56 | yes (doc -> FDA/EMA parent) | `MATCH` |
| `documentYear` | [document_year.csv](../../inputs/document_year.csv) | 118 | flat years/ranges | `MATCH` / `RANGE` / `DATE_RANGE` |

### Inline closed sets

Small enums and booleans are also closed-set fields. They do not need a CSV
lookup, but translation still chooses from an explicit finite set.

| Field | Allowed values |
|-------|----------------|
| `sex` | `Male`, `Female`, `Both` |
| `isPreclinical` | `true`, `false` |
| `concomitants` | `Fed`, `Fasted` |
| `tissueSpecific` | `Tissue-specific`, `Not tissue-specific` |
| `metabolitesEnantiomers` | `Not metabolites/enantiomers`, `Metabolite`, `Enantiomer` |

The `FuzzyLookupFilter.taxonomy` values in [enums.csv](../../inputs/enums.csv)
are a useful cross-check for server-side fuzzy lookup support, but this document
uses the local `inputs/` value sets as the definition of what can be translated
before the first API call.

## Runtime closed sets

Open-set fields become closed only after the first query has returned
datapoints. For each open-set filter field, the pipeline collects the unique
non-empty values present in the fetched datapoints for that field. That unique
list becomes the field's runtime closed set:

```
open-set field fragment + fetched unique values
        -> closed-set translation
        -> valid subset of fetched values
        -> post-filter the datapoints
```

If translation over the runtime closed set returns `[]` or `None`, the open-set
filter is invalid and does not narrow the datapoints. The invalid translation is
recorded so the final answer can explain that the field could not be grounded.

The v0.1 execution layer reads `countTotal` and does not fetch rows, so the
runtime closed-set post-filter path is not materialized in code. The live guard
for open-set fields is the zero-count probe described above.

Typical open-set fields:

| Field | Why open before fetch | Runtime closed set |
|-------|-----------------------|--------------------|
| `parameter` | no local PK parameter value set in `inputs/` | unique PK parameter values in fetched datapoints |
| `parameterDisplay` | no local value set in `inputs/` | unique display values in fetched datapoints |
| `studyGroup` | free text needing synonym handling, e.g. hepatic impairment | unique study-group strings in the fetched datapoints |
| `age` | free text or category-like record values | unique age strings in the fetched datapoints |
| `dose` | free numeric/unit text as stored in records | unique dose strings in the fetched datapoints |
| `duration` | free text stored in records | unique duration strings in the fetched datapoints |

## Service field map

The service config is the source of truth for which filter fields exist and which
bucket each field uses.

| Service | Closed-set filters before API query | Open-set fields |
|---------|-------------------------------------|-------------------------------------------|
| PK | `drugs`, `species`, `routes`, `documentSource`, `documentYear`, `sex`, `concomitants`, `tissueSpecific`, `metabolitesEnantiomers`, `isPreclinical` | `parameter`, `parameterDisplay`, `studyGroup`, `age`, `dose`, `duration` |

### Concrete service configuration

PK emits JSON machine queries:

| Logical field | Bucket | Backing set | API field / route | Output metadata |
|---------------|--------|-------------|-------------------|-----------------|
| `drugs` | closed | `drugs.csv` | `drugsFuzzy` | facet `drugs`, display `drug` |
| `species` | closed | `species.csv` | `species` | facet `species`, display `specie` |
| `route` (logical) | closed | `route.csv` | `routes` (API filter field) | facet/display `route` |
| `documentSource` | closed | `sources.csv` | `documentSource` (API field) | facet `sources`, display `source` |
| `documentYear` | closed | `document_year.csv` | `documentYear` | facet/display `documentYear` |
| `parameter` | open | fetched PK values | post-filter field `parameter` | facet `parameters`, display `parameter` |
| `parameterDisplay` | open | fetched PK values | post-filter field `parameterDisplay` | none |
| `studyGroup` | open | fetched datapoint values | post-filter field `studyGroup` | facet `studyGroup` |
| `age` | open | fetched datapoint values | post-filter field `age` | none |
| `dose` | open | fetched datapoint values | post-filter field `dose` | display `dose` |
| `duration` | open | fetched datapoint values | post-filter field `duration` | none |
| `sex` | enum | `Male`, `Female`, `Both` | `sex` | none |
| `concomitants` | enum | `Fed`, `Fasted` | `concomitants` | facet `concomitants` |
| `tissueSpecific` | enum | `Tissue-specific`, `Not tissue-specific` | `tissueSpecific` | facet `tissueSpecific` |
| `metabolitesEnantiomers` | enum | `Not metabolites/enantiomers`, `Metabolite`, `Enantiomer` | `metabolitesEnantiomers` | facet `metabolitesEnantiomers` |
| `isPreclinical` | boolean | `true`, `false` | `isPreclinical` | none |

PK always adds the following invariants unless the user query already supplies
the field: `concomitants` is `Fasted` or empty, `tissueSpecific` is
`Not tissue-specific`, and `metabolitesEnantiomers` is
`Not metabolites/enantiomers`.

## Decision rule

```
Does the field have a complete value set in inputs/ or an inline enum/boolean?
├─ yes -> CLOSED SET:
│        Is the vocabulary size < EARLY_CONTRIBUTOR_THRESHOLD (default 500)?
│        ├─ yes -> EARLY CONTRIBUTOR (Pass A):
│        │        translate before the first API call; include in Stage 3A query.
│        └─ no  -> LARGE CLOSED SET (Pass B):
│                 defer until early-contributor datapoints are fetched;
│                 if the unique value count in those datapoints is < threshold,
│                 translate against the narrowed list and add as a new contributor;
│                 iterate until convergence; include resolved fields in Stage 3B query.
└─ no  -> OPEN SET (Pass C):
         defer until Stage 3B datapoints are fetched;
         derive the unique values from those datapoints as the runtime closed set;
         translate against that set and post-filter rows.
         v0.1 translates directly and may apply zero-count probes instead.
```

The complete response-side field list is in
[inputs/fields.csv](../../inputs/fields.csv); request-side criteria and their
types are in [inputs/query_criteria_fields.csv](../../inputs/query_criteria_fields.csv).
