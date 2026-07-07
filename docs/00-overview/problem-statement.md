# Problem statement

## The general problem

> **Convert a natural-language query into a machine query.**

A user asks something like:

> *"What is the AUC of sunitinib in human after oral administration?"*

and we must produce a structured request that the PharmaPendium search API can
execute.

## What a "machine query" actually is

A machine query is **nothing more than a bundle of filters**. Each filter has
exactly three things:

| Part | Example | Notes |
|------|---------|-------|
| **operator** | `MATCH`, `OR`, `AND`, `NOT`, `REGEX`, `RANGE`, `DATE_RANGE`, `EMPTY`, `PROXIMITY` | how to compare |
| **field name** | `species`, `parameter`, `route`, `documentYear` | which column |
| **value** | `"Human"`, `["Rat","Mouse"]`, `2020` | what to match |

These filters are then composed into a nested boolean tree (the API's `query`
object), optionally alongside `facets`, `displayColumns`, `entityFilters`, etc.
The full target format is described in
[../02-domain-inputs/machine-query-schema.md](../02-domain-inputs/machine-query-schema.md).

So the core task reduces to: **for each relevant field, decide the operator and
the value(s), then combine them.**

## Two fundamentally different kinds of field

The redesign hinges on one observation: not all fields are the same.

1. **Closed-set fields** — fields whose complete set of legal values is known
   before query execution, either from CSV taxonomies (`drugs`, `species`,
   `route`, `sources`, `documentYear`) or from inline enums/booleans (`sex`,
   `concomitants`, `tissueSpecific`, `metabolitesEnantiomers`, `isPreclinical`).
   These values are selected by grounding against the set, and hierarchy in the
   CSVs can be used for class or rollup expansion.

2. **Open-set fields** — fields whose value space is not known before query
   execution (`parameter`, `parameterDisplay`, `studyGroup`, `age`, `dose`,
   `duration`). These filters are deferred until the closed-set query fetches
   datapoints. The unique fetched values for the field become a runtime closed
   set, and the same translator selects a valid subset for post-filtering.

See [../02-domain-inputs/field-taxonomy.md](../02-domain-inputs/field-taxonomy.md)
for the full classification.

## The new shape (one line)

> NL query -> **many single-field NL subqueries** -> **closed-set translations**
> for fields with known values -> **aggregate and fetch datapoints** -> **runtime
> closed-set translations** for deferred open-set fields -> **post-filter**.

The implemented v0.1 package includes Stage -1 query expansion before
decomposition and currently executes API calls for `countTotal`; full row fetch
and runtime closed-set post-filtering remain represented as the row-level design
path.

The full pipeline is in
[../03-proposed-design/architecture.md](../03-proposed-design/architecture.md).
