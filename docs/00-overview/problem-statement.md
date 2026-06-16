# Problem statement

## The general problem

> **Convert a natural-language query into a machine query.**

A user asks something like:

> *"What are the drugs causing neutropenia or thrombocytopenia in human, at
> which dose, dosing regimen and route?"*

and we must produce a structured request that the PharmaPendium search API can
execute.

## What a "machine query" actually is

A machine query is **nothing more than a bundle of filters**. Each filter has
exactly three things:

| Part | Example | Notes |
|------|---------|-------|
| **operator** | `MATCH`, `OR`, `AND`, `NOT`, `REGEX`, `RANGE`, `DATE_RANGE`, `EMPTY` | how to compare |
| **field name** | `species`, `effects`, `route`, `documentYear` | which column |
| **value** | `"Human"`, `["Rat","Mouse"]`, `2020` | what to match |

These filters are then composed into a nested boolean tree (the API's `query`
object), optionally alongside `facets`, `displayColumns`, `entityFilters`, etc.
The full target format is described in
[../02-domain-inputs/machine-query-schema.md](../02-domain-inputs/machine-query-schema.md).

So the core task reduces to: **for each relevant field, decide the operator and
the value(s), then combine them.**

## Two fundamentally different kinds of field

The redesign hinges on one observation: not all fields are the same.

1. **Closed-vocabulary fields** — fields whose complete set of legal values we
   *already have on disk* as CSV taxonomies (`drugs`, `effects`, `indications`,
   `species`, `route`, `sources`, `toxicityParameter`, `doseType`,
   `documentYear`). For these we should not let the LLM hallucinate a value — we
   should **extract** the value by matching/grounding against the CSV (via tool
   calling), and we can exploit the hierarchy in those CSVs (e.g. expand a drug
   class to its members).

2. **Open fields** — fields whose value space we cannot enumerate (`studyGroup`,
   `parameterComment`, `parameterDisplay`, free-text `dose`, numeric value
   ranges, …). For these the LLM legitimately has to **decide** the value.

See [../02-domain-inputs/field-taxonomy.md](../02-domain-inputs/field-taxonomy.md)
for the full classification.

## What's wrong with how we do it today

Today a **single giant prompt** (per service: Safety, PK, RTB) asks one LLM call
to read the whole question and emit the entire machine query in one shot. That
approach:

- relies 100% on the LLM, with no grounding against the CSV taxonomies, so it
  invents field values that don't exist in the vocabulary;
- crams every rule for every field into one unmaintainable prompt;
- cannot be tested or improved field-by-field;
- mishandles hierarchy (drug classes, species classes, MedDRA effect rollups)
  because the model only sees a flat label, not the taxonomy.

The concrete failures are catalogued in
[../01-current-system/pain-points.md](../01-current-system/pain-points.md),
drawn directly from the SME gold set in
[inputs/sme_expected_cases.csv](../../inputs/sme_expected_cases.csv).

## The new shape (one line)

> NL query → **many single-field NL subqueries** → **one machine subquery per
> field** (grounded on CSV where possible) → **aggregate** into the final
> machine query.

The full pipeline is in
[../03-proposed-design/architecture.md](../03-proposed-design/architecture.md).
