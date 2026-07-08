# Stage 1 — Decomposition

**Input:** the enhanced query from Stage 0, including TERMite annotations over
the expanded query.
**Output:** a list of single-field NL subqueries, each routed to a target field.
Stage 1 also records which Stage 0 annotations seed each component before Stage 2
translation begins.

## Goal

Turn one complex question into many tiny questions, each about exactly one field.
The model does the semantic routing job first: *"which parts of this sentence
are about which field?"*

## Output shape

A list of items like:

```json
[
  { "field": "drugs",     "nl_fragment": "sunitinib",    "type": "filter",   "reason": "The user restricts results to the drug sunitinib.",              "source": "termite:DRUG" },
  { "field": "species",   "nl_fragment": "human",        "type": "filter",   "reason": "The user restricts results to human studies.",                   "source": "termite:SPECIES" },
  { "field": "parameter", "nl_fragment": "AUC",          "type": "filter",   "reason": "The user restricts results to AUC PK records.",                  "source": "termite:PARAMETER" },
  { "field": "value",     "nl_fragment": "what is AUC",  "type": "question", "reason": "The user wants the AUC value reported from the retrieved records.", "source": "llm" }
]
```

- **field** — the target searchable field (from
  [../02-domain-inputs/field-taxonomy.md](../02-domain-inputs/field-taxonomy.md)).
- **nl_fragment** — the minimal natural-language span expressing this component.
- **type** — a literal, one of:
  - **`filter`** — this component **must be translated into a machine subquery**
    (Stage 2) and included in the machine query's filters. It constrains *which
    records are retrieved*.
  - **`question`** — this component is **not** a filter. It states a question to
    **answer after the data is retrieved** — i.e. post-retrieval analysis over
    the result set (and the signal Stage 3 uses to decide facets / display
    columns). It describes *what we want to learn from the records*, not how to
    narrow them. E.g. "at which dose…" or "what is the AUC" are `question`s,
    not filters.
- **reason** — a one-sentence natural-language justification for why this
  fragment maps to this field and this `type`. Keep it to a single sentence;
  it is the human-readable audit trail for the decomposition.
- **source** — provenance such as `llm`, `termite:<TYPE>`, or a reconciliation
  suffix. Useful for debugging and for deciding grounding confidence in Stage 2.
- **boolean hint** (optional) — when one field carries multiple concepts with
  explicit logic, e.g. `parameter` with "AUC **or** Cmax",
  record the intended operator so Stage 3 can honour it.

The boolean hint is a structured `boolean_group` object:

```json
{ "id": "parameter-1", "op": "OR" }
```

- `id` is an opaque group id shared by every component that belongs to the same
  logical group.
- `op` is either `AND` or `OR`.
- A group usually contains components from the same field, such as two `parameter`
  values. It may span fields only when the user's retrieval intent explicitly
  asks for alternatives across fields.
- A component with no `boolean_group` joins the rest of the query through the
  Stage-3 top-level `AND` operator. Field-level groups are flattened into that
  top-level `AND`; nested cross-field boolean intent is not represented.
- Negation is not encoded in Stage 1 unless the user explicitly excludes a value;
  Stage 3 represents that with a single-child `NOT` node.

> **Note on `type` vs filtering.** Only `type: "filter"` components flow into
> Stage 2 translation and the machine query. `type: "question"` components are
> carried forward untouched as the post-retrieval task(s) — they tell the answer
> layer what to compute from the results, and they hint Stage 3 toward the right
> `facets` / `displayColumns` (see
> [stage-3-aggregation.md](stage-3-aggregation.md)).

## How routing is seeded

1. **Stage 0 TERMite annotations.** TERMite runs over the expanded query before
   decomposition and returns recognized text, preferred labels, public synonyms,
   and entity types that map to PK fields: `DRUG->drugs`,
   `SPECIES->species`, `ROUTE->routes`, `PARAMETER->parameter`, `AGE->age`.
2. **LLM decomposer.** The decomposer is a **vocab-free** LLM step: it segments
   the query into single-field spans and routes each to a field using the field
   catalogue and the user's own words. It does **not** resolve, normalize, or
   consult any taxonomy — that is Stage 2's grounded job. It also assigns each
   component its `type` and writes its one-sentence `reason`. Components carry
   `source: llm` unless a Stage 0 annotation supports the same component. The
   prompt instructs it to emit a `drugs` filter only
   when a **specific drug or drug class is named** (Sunitinib, kinase inhibitors):
   the bare head noun "drugs" in a *"drugs treating/causing/for `<condition>`"*
   construction is the thing asked about, not a filter — the `<condition>` routes
   to `studyGroups` and "drugs" becomes a `question` (the reported
   output). Otherwise the carrier phrase fuzzy-grounds to a nonsense drug and
   zeroes the query.
3. **Annotation reconciliation (deterministic).** A small
   deterministic pass honours TERMite annotations and resolves routing ambiguities.
   It resolves routing ambiguities: when TERMite annotates a fragment with a type
   that conflicts with the decomposer's field assignment, the pass probes the
   relevant taxonomy and picks the narrower, more precise reading.

   It also promotes **retrieval-defining** entities: a recognized PK parameter
   (AUC, Cmax, t½, …) names the *kind of record* sought, so it must be a
   **filter**, not just a reported column. "What is the **AUC** of X in fed
   subjects" asks about AUC *and* restricts retrieval to AUC records, but the
   decomposer may emit only a `parameter` *question*. When TERMite recognizes such
   an entity, the pass promotes the same-field question to a filter on the preferred
   label (the field is still reported via Stage-3 facets/displayColumns). Plain
   questions like "at which dose" are untouched.

   Both rules live in `reconcile_with_annotations` and run after decomposition.

## Granularity: per concept, tagged by field

Stage 1 decomposes to **concepts** and tags each concept with its target field.
When several concepts belong to the same field, they share a `boolean_group` so
Stage 2 can translate each concept independently and Stage 3 can recombine them
with the intended operator.

For example, "AUC or Cmax" becomes two `parameter` components with one shared
`OR` group. "AUC and Cmax" becomes two `parameter` components with one shared
`AND` group. This preserves per-concept grounding while still reporting the field
as a single logical filter in evaluation.

## What Stage 1 must NOT do

- It must not pick taxonomy values (that's Stage 2's grounded job).
- It must not build the boolean tree (that's Stage 3).
- It must not drop information it can't classify — unroutable spans should be
  surfaced (logged / flagged), not silently discarded.

## Worked example

> "What is the AUC of sunitinib in rats after oral administration in fasted subjects?"

```json
[
  { "field": "parameter", "nl_fragment": "AUC",               "type": "filter",   "reason": "The user restricts results to AUC records.",                           "source": "termite:PARAMETER" },
  { "field": "drugs",     "nl_fragment": "sunitinib",         "type": "filter",   "reason": "The user restricts results to the drug sunitinib.",                    "source": "termite:DRUG" },
  { "field": "species",   "nl_fragment": "rats",              "type": "filter",   "reason": "The user restricts results to rat studies.",                           "source": "termite:SPECIES" },
  { "field": "routes",    "nl_fragment": "oral",              "type": "filter",   "reason": "The user restricts results to oral administration.",                   "source": "termite:ROUTE" },
  { "field": "concomitants", "nl_fragment": "fasted",         "type": "filter",   "reason": "The user restricts results to fasted-state records.",                  "source": "llm" },
  { "field": "value",     "nl_fragment": "what is the AUC",  "type": "question", "reason": "The user wants the AUC value reported from the retrieved records.",    "source": "llm" }
]
```

`parameter` is promoted to a **filter** by the annotation reconciliation pass
because AUC names the kind of PK record sought — it restricts retrieval, not just
the reported output. The `value` component is a `question` — after retrieval we
report the AUC value(s); it is not a filter.
