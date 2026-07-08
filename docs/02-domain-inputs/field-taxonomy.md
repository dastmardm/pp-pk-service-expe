# Filterable fields and value sets

Every translator-emittable filter field belongs to exactly one bucket in the
service configuration. The bucket determines when the field can be translated
and where its legal values come from.

- **Closed-set fields** have a complete value set before query execution. The set
  comes from an `inputs/` taxonomy CSV, an inline enum, or a boolean domain. Stage
  2 may only emit values that are members of that set.
- **Open-set fields** do not have a complete value set in `inputs/`. These
  fields are translated directly to `MATCH` or `REGEX` constraints. Live runs can
  optionally drop a filter only when an isolated API count probe confirms that it
  matches no records.

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

## Open-set handling

Open-set fields have no complete local value set. The translator emits them as
direct API constraints and records their open-set provenance in the grounding
trace. When live execution enables zero-count probing, each open-set filter can
be executed in isolation; a confirmed zero-count filter is dropped with a
warning, and probe errors keep the filter.

Typical open-set fields:

| Field | Why open | API constraint style |
|-------|----------|----------------------|
| `parameter` | no local PK parameter value set in `inputs/` | direct `MATCH` or `REGEX` |
| `parameterDisplay` | no local value set in `inputs/` | direct `MATCH` or `REGEX` |
| `studyGroups` | free text needing synonym handling, e.g. hepatic impairment | direct `MATCH` or `REGEX` |
| `age` | free text or category-like record values | direct `MATCH` or `REGEX` |
| `dose` | free numeric/unit text as stored in records | direct `MATCH` or `REGEX` |
| `duration` | free text stored in records | direct `MATCH` or `REGEX` |

## Service field map

The service config is the source of truth for which filter fields exist and which
bucket each field uses.

| Service | Closed-set filters before API query | Open-set fields |
|---------|-------------------------------------|-------------------------------------------|
| PK | `drugs`, `species`, `routes`, `documentSource`, `documentYear`, `sex`, `concomitants`, `tissueSpecific`, `metabolitesEnantiomers`, `isPreclinical` | `parameter`, `parameterDisplay`, `studyGroups`, `age`, `dose`, `duration` |

### Concrete service configuration

PK emits JSON machine queries:

| Logical field | Bucket | Backing set | API field / route | Output metadata |
|---------------|--------|-------------|-------------------|-----------------|
| `drugs` | closed | `drugs.csv` | `drugsFuzzy` | facet `drugs`, display `drug` |
| `species` | closed | `species.csv` | `species` | facet `species`, display `specie` |
| `routes` | closed | `route.csv` | `routes` | facet `routes`, display `route` |
| `documentSource` | closed | `sources.csv` | `documentSource` (API field) | facet `sources`, display `source` |
| `documentYear` | closed | `document_year.csv` | `documentYear` | facet/display `documentYear` |
| `parameter` | open | none | direct API field `parameter` | facet `parameters` for output grouping, display `parameter` |
| `parameterDisplay` | open | none | direct API field `parameterDisplay` | none |
| `studyGroups` | open | none | direct API field `studyGroups` | facet `studyGroups` |
| `age` | open | none | direct API field `age` | none |
| `dose` | open | none | direct API field `dose` | display `dose` |
| `duration` | open | none | direct API field `duration` | none |
| `sex` | enum | `Male`, `Female`, `Both` | `sex` | none |
| `concomitants` | enum | `Fed`, `Fasted` | `concomitants` | facet `concomitants` |
| `tissueSpecific` | enum | `Tissue-specific`, `Not tissue-specific` | `tissueSpecific` | facet `tissueSpecific` |
| `metabolitesEnantiomers` | enum | `Not metabolites/enantiomers`, `Metabolite`, `Enantiomer` | `metabolitesEnantiomers` | facet `metabolitesEnantiomers` |
| `isPreclinical` | boolean | `true`, `false` | `isPreclinical` | none |

PK adds the following invariants unless the user query already supplies the
field: `concomitants` is `Fasted` or empty, `tissueSpecific` is
`Not tissue-specific`, and `metabolitesEnantiomers` is
`Not metabolites/enantiomers`. A user-supplied value for one of these fields
wins for that field, including non-fasted concomitant conditions; the default
constraint is not duplicated.

The PharmaPendium API also exposes request fields that this translator does not
emit. `drugsAndSynonyms`, `radioLabels`, and `parameterValues` are API-only for
the translator and are not assigned to a translation bucket.

## Decision rule

```
Does the field have a complete value set in inputs/ or an inline enum/boolean?
├─ yes -> CLOSED SET:
│        translate against that closed set;
│        use candidate windows for large vocabularies when needed;
│        include valid translations in the Stage 3 query.
└─ no  -> OPEN SET:
         translate directly to MATCH or REGEX;
         optionally apply zero-count probes during live execution.
```

The complete response-side field list is in
[inputs/fields.csv](../../inputs/fields.csv); request-side criteria and their
types are in [inputs/query_criteria_fields.csv](../../inputs/query_criteria_fields.csv).
