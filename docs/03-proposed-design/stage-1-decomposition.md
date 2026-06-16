# Stage 1 — Decomposition

**Input:** the NL query (+ TERMite annotations).
**Output:** a list of single-field NL subqueries, each routed to a target field.

## Goal

Turn one complex question into many tiny questions, each about exactly one field.
The legacy system never does this — it hands the whole question to one prompt.
Here we want the model to do only the easy semantic job first: *"which parts of
this sentence are about which field?"*

## Output shape

A list of items like:

```json
[
  { "field": "drugs",   "nl_fragment": "sunitinib", "type": "filter",   "reason": "The user restricts results to the drug sunitinib.",        "source": "termite:DRUG" },
  { "field": "species", "nl_fragment": "human",     "type": "filter",   "reason": "The user restricts results to human studies.",             "source": "termite:SPECIES" },
  { "field": "effects", "nl_fragment": "ADRs",      "type": "question", "reason": "The user wants to know which adverse effects occur, answered over the retrieved records.", "source": "llm" }
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
    narrow them. E.g. "at which dose…" or "what are the ADRs" are `question`s,
    not filters.
- **reason** — a one-sentence natural-language justification for why this
  fragment maps to this field and this `type`. Keep it to a single sentence;
  it is the human-readable audit trail for the decomposition.
- **source** — provenance: a TERMite annotation or the LLM. Useful for debugging
  and for deciding grounding confidence in Stage 2.
- **boolean hint** (optional) — when one field carries multiple concepts with
  explicit logic, e.g. `effects` with "neutropenia **or** thrombocytopenia",
  record the intended operator so Stage 3 can honour it.

> **Note on `type` vs filtering.** Only `type: "filter"` components flow into
> Stage 2 translation and the machine query. `type: "question"` components are
> carried forward untouched as the post-retrieval task(s) — they tell the answer
> layer what to compute from the results, and they hint Stage 3 toward the right
> `facets` / `displayColumns` (see
> [stage-3-aggregation.md](stage-3-aggregation.md)).

## How routing is seeded

1. **TERMite first.** Each annotation already carries a type that maps cleanly to
   a field: `DRUG→drugs`, `SPECIES→species`, `ROUTE→route`, `ADVERSE_EVENT→
   effects`, `TOXICITY_PARAMETER→toxicityParameter`, `INDICATION→indications`,
   `PARAMETER→parameter` (PK), `AGE→ages` (PK), `TARGET→targets`. These become
   high-confidence subqueries with `source: termite`.
2. **LLM fills the gaps.** Spans TERMite did not tag (free-text qualifiers,
   numeric thresholds, dosing regimen words, sex, and `question` intents like
   "at which dose") are routed by a small LLM step that knows the field
   catalogue. The same step assigns each component its `type` and writes its
   one-sentence `reason`.
3. **Disambiguation.** When a span could be two fields (the classic "kinase" =
   drug *class* vs *target*, Q8/Q21), Stage 1 records both candidates; Stage 2
   resolves by attempting the relevant CSV lookups and comparing confidence.

## Granularity: per field or per concept?

Two defensible options (open question — see
[architecture.md](architecture.md#open-questions)):

- **One subquery per field.** "neutropenia or thrombocytopenia" → a single
  `effects` subquery carrying both concepts + an `OR` hint.
- **One subquery per concept.** → two `effects` subqueries; Stage 3 OR-joins
  them.

The gold set supports *per concept* internally but reports *per field*: Q14
stores `(neutropenia terms) AND (thrombocytopenia terms)` in one `effects` cell.
Recommended: decompose to **concepts** but tag them with the same field + a
shared boolean group, so Stage 2 can expand each concept independently and Stage
3 can recombine with the right operator.

## What Stage 1 must NOT do

- It must not pick taxonomy values (that's Stage 2's grounded job).
- It must not build the boolean tree (that's Stage 3).
- It must not drop information it can't classify — unroutable spans should be
  surfaced (logged / flagged), not silently discarded.

## Worked example

> "What is the NOAEL for sunitinib in rats related to maternal toxicity" (Q12)

```json
[
  { "field": "toxicityParameter", "nl_fragment": "NOAEL",             "type": "filter",   "reason": "The user restricts results to the NOAEL toxicity endpoint.",         "source": "termite:TOXICITY_PARAMETER" },
  { "field": "drugs",             "nl_fragment": "sunitinib",         "type": "filter",   "reason": "The user restricts results to the drug sunitinib.",                 "source": "termite:DRUG" },
  { "field": "species",           "nl_fragment": "rats",              "type": "filter",   "reason": "The user restricts results to rat studies.",                        "source": "termite:SPECIES" },
  { "field": "parameterComment",  "nl_fragment": "maternal toxicity", "type": "filter",   "reason": "The user restricts results to the maternal-toxicity qualifier.",    "source": "llm" },
  { "field": "value",             "nl_fragment": "what is the NOAEL", "type": "question", "reason": "The user wants the NOAEL value reported from the retrieved records.", "source": "llm" }
]
```

Note `maternal toxicity` is routed to the **open** field `parameterComment` (not
`effects`), matching the SME mapping for Q12. The `value` component is a
`question` — after retrieval we report the NOAEL value(s); it is not a filter.
