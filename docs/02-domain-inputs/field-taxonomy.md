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
| `effects` | [effects.csv](../../inputs/effects.csv) | 12,724 | yes (MedDRA-style) | `MATCH` with expanded value list |
| `indications` | [indications.csv](../../inputs/indications.csv) | 3,152 | yes | `MATCH` via `entityFilters` where required |
| `species` | [species.csv](../../inputs/species.csv) | 286 | yes (class -> members, e.g. Rodent/Primate) | `MATCH` with class/leaf handling |
| `route` | [route.csv](../../inputs/route.csv) | 204 | flat (+ usage counts) | `MATCH` |
| `toxicityParameter` | [toxicity_parameters.csv](../../inputs/toxicity_parameters.csv) | 33 | yes | `MATCH` |
| `documentSource` / `sources` | [sources.csv](../../inputs/sources.csv) | 56 | yes (doc -> FDA/EMA parent) | `MATCH` |
| `doseType` | [dose_type.csv](../../inputs/dose_type.csv) | 7 | flat enum | `MATCH` |
| `documentYear` | [document_year.csv](../../inputs/document_year.csv) | 118 | flat years/ranges | `MATCH` / `RANGE` / `DATE_RANGE` |

### Inline closed sets

Small enums and booleans are also closed-set fields. They do not need a CSV
lookup, but translation still chooses from an explicit finite set.

| Field | Allowed values |
|-------|----------------|
| `sex` | `Male`, `Female`, `Both` |
| `isPreclinical` | `true`, `false` |
| `concomitants` (PK) | `Fed`, `Fasted` |
| `tissueSpecific` (PK) | `Tissue-specific`, `Not tissue-specific` |
| `metabolitesEnantiomers` (PK) | `Not metabolites/enantiomers`, `Metabolite`, `Enantiomer` |
| `category` (RTB) | `In vitro (efficacy)`, `In vivo (animal models)`, `Metabolism/transport`, `Pharmacokinetic`, `Toxicity/safety pharmacology` |

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
runtime closed-set post-filter path is not materialized in code. The implemented
open-set safety mechanism is the zero-count probe described above.

Typical open-set fields:

| Field | Why open before fetch | Runtime closed set |
|-------|-----------------------|--------------------|
| `parameterComment` | free-text qualifier, e.g. "maternal toxicity" | unique comments in the fetched datapoints |
| `studyGroup` | free text needing synonym handling, e.g. hepatic impairment | unique study-group strings in the fetched datapoints |
| `dose` | free numeric/unit text as stored in records | unique dose strings in the fetched datapoints |
| `ages` / `age` | free text or category-like record values | unique age strings in the fetched datapoints |
| `parameter`, `parameterDisplay`, `duration` (PK) | no local PK parameter/duration value set in `inputs/` | unique PK values in fetched datapoints |
| `targets` | no local `targets.csv` value set in `inputs/` | v0.1 emits a `DrugsTargets` entity filter, using a TERMite preferred label when available; row-level runtime sets apply when fetched linked values are available |
| `model`, `cellLine`, `tissue`, `regimen` (RTB) | free-text CrossFire columns | unique column values in fetched rows |

## Service field map

The service config is the source of truth for which filter fields exist and which
bucket each field uses.

| Service | Closed-set filters before API query | Open-set fields |
|---------|-------------------------------------|-------------------------------------------|
| Safety | `drugs`, `effects`, `species`, `route`, `toxicityParameter`, `documentSource`, `doseType`, `documentYear`, `indications`, `sex`, `isPreclinical` | `targets`, `parameterComment`, `studyGroup`, `ages`, `dose` |
| PK | `drugs`, `species`, `route`, `documentSource`, `documentYear`, `sex`, `concomitants`, `tissueSpecific`, `metabolitesEnantiomers`, `isPreclinical` | `parameter`, `parameterDisplay`, `studyGroup`, `age`, `dose`, `duration` |
| RTB | `drugs`, `species`, `route`, `category` | `parameter`, `model`, `cellLine`, `tissue`, `regimen` |

### Concrete service configuration

The generated technical spec must enumerate the concrete service mappings below
so implementation and evaluation do not have to rediscover them from code.

Safety emits JSON machine queries:

| Logical field | Bucket | Backing set | API field / route | Output metadata |
|---------------|--------|-------------|-------------------|-----------------|
| `drugs` | closed | `drugs.csv` | `drugsFuzzy` | facet `drugs`, display `drug` |
| `effects` | closed | `effects.csv` | `effects` | facet `effects`, display `effect` |
| `species` | closed | `species.csv` | `species` | facet `species`, display `specie` |
| `route` | closed | `route.csv` | `route` | facet/display `route` |
| `toxicityParameter` | closed | `toxicity_parameters.csv` | `toxicityParameter` | display `toxicityParameter` |
| `documentSource` | closed | `sources.csv` | `documentSource` | facet `sources`, display `source` |
| `doseType` | closed | `dose_type.csv` | `doseType` | facet/display `doseType` |
| `documentYear` | closed | `document_year.csv` | `documentYear` | facet/display `documentYear` |
| `indications` | closed | `indications.csv` | entity filter `DrugsIndications` | none |
| `targets` | open | fetched linked target values | entity filter `DrugsTargets` when available | none |
| `parameterComment` | open | fetched datapoint values | post-filter field `parameterComment` | display `parameterComment` |
| `studyGroup` | open | fetched datapoint values | post-filter field `studyGroup` | none |
| `ages` | open | fetched datapoint values | post-filter field `ages` | none |
| `dose` | open | fetched datapoint values | post-filter field `dose` | display `dose` |
| `sex` | enum | `Male`, `Female`, `Both` | `sex` | none |
| `isPreclinical` | boolean | `true`, `false` | `isPreclinical` | none |

PK emits JSON machine queries:

| Logical field | Bucket | Backing set | API field / route | Output metadata |
|---------------|--------|-------------|-------------------|-----------------|
| `drugs` | closed | `drugs.csv` | `drugsFuzzy` | facet `drugs`, display `drug` |
| `species` | closed | `species.csv` | `species` | facet `species`, display `specie` |
| `route` | closed | `route.csv` | `route` | facet/display `route` |
| `documentSource` | closed | `sources.csv` | `documentSource` | facet `sources`, display `source` |
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

RTB emits a CrossFire `where_clause` over `DAT.*` columns:

| Logical field | Bucket | Backing set | CrossFire column |
|---------------|--------|-------------|------------------|
| `drugs` | closed | `drugs.csv` | `DAT.MNAME` |
| `species` | closed | `species.csv` | `DAT.BSPECIE` |
| `route` | closed | `route.csv` | `DAT.MROUTE` |
| `category` | enum | category enum above | `DAT.CATEG` |
| `parameter` | open | fetched row values | `DAT.VTYPE` |
| `model` | open | fetched row values | `DAT.MODEL` |
| `cellLine` | open | fetched row values | `DAT.BCELL` |
| `tissue` | open | fetched row values | `MEASLOC.TISSUE` |
| `regimen` | open | fetched row values | `DAT.MREGIM` |

RTB always adds `DAT.CATEG = "Pharmacokinetic"` when no category is present.

## Decision rule

```
Does the field have a complete value set in inputs/ or an inline enum/boolean?
├─ yes -> CLOSED SET before query execution:
│        translate against that set and only emit a valid subset.
└─ no  -> OPEN SET before query execution:
         v0.1 translates directly and may apply zero-count probes;
         the row-level design defers the filter, fetches datapoints using
         closed-set filters, derives this field's unique fetched values,
         translates against that runtime closed set, then post-filters rows.
```

The complete response-side field list is in
[inputs/fields.csv](../../inputs/fields.csv); request-side criteria and their
types are in [inputs/query_criteria_fields.csv](../../inputs/query_criteria_fields.csv).
