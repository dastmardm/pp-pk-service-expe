# Stage 2 - Per-field translation

**Input:** filter components from Stage 1, each carrying one field and one NL
fragment.
**Output:** valid machine subqueries for input closed-set fields, plus validated
post-filters for fields that become closed sets only after datapoints are fetched.

This stage is where the closed-set/open-set distinction is enforced. A
translation is valid only when it chooses values from a known set. The set may be
known before the API call (`inputs/` CSVs and inline enums), or it may be derived
from fetched datapoints for an open-set field.

Question components do not become filters. They are carried forward so Stage 3
can choose facets or `displayColumns`.

## Two translation passes

```
Stage-1 filter components
        │
        ├─ Pass A: input closed-set fields
        │     closed_set = CSV / enum / boolean values
        │     pool = NL fragment + TERMite labels + synonyms
        │     translate_closed_set(pool, closed_set)
        │     valid subset -> machine subquery
        │     [] / None    -> invalid, excluded downstream
        │
        ├─ aggregate valid Pass-A subqueries
        │     -> API query
        │     -> fetched datapoints
        │
        └─ Pass B: open-set fields
              closed_set = unique values for that field in fetched datapoints
              pool = NL fragment + generated synonyms
              translate_closed_set(pool, closed_set)
              valid subset -> post-filter datapoints
              [] / None    -> invalid, no downstream narrowing
```

The same closed-set translator is used in both passes. The difference is only
where the closed set comes from.

## Closed-set translator

The translator is a tool over a closed set of entities. It starts with:

- `field`: the field being filtered;
- `pool`: one or more candidate phrasings for the user's intended value;
- `closed_set`: the legal entities for the field.

It always returns a **sublist of `closed_set`**. Returning `[]` or `None` means
translation failed. A failed translation is marked invalid and does not affect
the API query, entity filters, post-filtering, facets, or display columns.

Resolution order:

1. **Exact search.** Compare every pool item with the closed-set entities using
   case-insensitive exact matching. Keep every exact entity that matches the
   field intent.
2. **Fuzzy search.** If exact search returns nothing, compare every pool item
   with the closed set using fuzzy matching. Ranking may use string similarity,
   corpus `count`, and hierarchy signals.
3. **Pool enrichment.** If fuzzy search also returns nothing, call the LLM to add
   equivalent pool items: synonyms, abbreviations, brand names, scientific names,
   spelling variants, or likely class/member names. Then restart exact search and
   fuzzy search over the enriched pool.
4. **Closed-set LLM selection.** If the enriched pool still produces no match,
   pass the pool and the closed-set entities to the LLM and ask it to select the
   matching entities using the exact closed-set spellings. The LLM is selecting
   from the set, not inventing values.
5. **Invalid result.** If the selected list is still empty, the translation
   fails and is marked invalid.

The closed-set contract asserts every LLM candidate against `closed_set`. Values
that cannot be verified are dropped, so the final emitted value is always a valid
subset of the available entities.

In the v0.1 implementation, this membership assertion is enforced by
re-grounding every LLM proposal against the CSV (`exact` first, then `fuzzy`) and
dropping any proposal that cannot be verified. The synonym-mapping fallback makes
several attempts to recover from empty model responses; the closed-set window
selection path keeps only re-grounded rows.

## Input closed-set fields

For fields backed by [inputs/](../../inputs/) taxonomies, the closed set is the
CSV's preferred-label list. The generic algorithm handles typos, synonyms, and
hierarchy:

1. **Normalize.** Run the field normalizer over the NL
   fragment first (see [misspelling-strategy.md](misspelling-strategy.md)).
   Closed-set fields can safely normalize toward the nearest known entity because
   every correction is later validated against the closed set.
2. **Build the pool.** Start with the normalized fragment. Add matching Stage-0
   TERMite preferred labels and synonyms. Add LLM-generated
   synonyms only if exact and fuzzy search over the initial pool fail.
3. **Translate over the closed set.** Run the closed-set translator above.
4. **Expand hierarchy when the selected entity is a class or rollup.**
   - drug class -> class label, resolved server-side by the API;
   - exact species class -> class label, resolved server-side by the API;
   - colloquial species groups with no exact class label, such as "Monkeys",
     -> the matching member species;
   - effect category -> preferred terms via the effects hierarchy;
   - preclinical / non-clinical phrasing -> the `isPreclinical` boolean field.
5. **Choose the operator.** Default to `MATCH`. Use `NOT` for exclusions and
   `RANGE`/`DATE_RANGE` for `documentYear` thresholds. Preserve the Stage-1
   boolean group so Stage 3 can assemble `AND`/`OR` correctly.
6. **Apply field emission rules.** Drug filters typically emit to `drugsFuzzy`
   with a conservative trailing wildcard on a single leaf name, while strict
   fields emit their configured API field.

Output example:

```json
{ "MATCH": { "field": "species", "value": ["African green monkey", "Cynomolgus monkey", "Rhesus monkey"] } }
```

## Runtime closed-set fields

Open-set fields are deferred until the closed-set query has fetched datapoints.
At that point each open-set field gets a runtime closed set:

1. Collect the unique non-empty values for that field from the fetched datapoints.
2. Build a pool from the user's NL fragment and LLM-generated synonyms.
3. Run the same closed-set translator against the runtime entity list.
4. Keep only datapoints whose field value is in the returned subset.

This turns a field such as `parameterComment`, `studyGroup`, `dose`, `ages`, PK
`parameterDisplay`, or RTB `model` into a validated post-filter instead of a raw
LLM value in the first API query.

The v0.1 translator does not expose a generic
`translate(field, pool, runtime_closed_set)` entry point. Open fields are handled
by `_translate_open` before aggregation:

- `studyGroup` and `ages` emit `REGEX` constraints; `studyGroup` expands a small
  built-in synonym set for hepatic and renal impairment.
- Plain free-text fields such as `parameterComment` strip leading relational
  connective text before emitting `MATCH`.
- Entity-routed open fields such as `targets` emit the corresponding TERMite
  preferred label when TERMite recognized that surface, otherwise the user
  fragment remains in the pool until runtime grounding can validate it.
- Live runs can call `drop_empty_open_filters` before aggregation to remove an
  open-set filter whose isolated API count is confirmed as `0`.

Example:

```json
{
  "field": "parameterComment",
  "pool": ["maternal toxicity", "maternal toxic effect"],
  "runtime_closed_set": ["Maternal toxicity", "Paternal toxicity", "Embryo-fetal toxicity"],
  "selected": ["Maternal toxicity"]
}
```

## Per-field contract

Every field translator exposes the same selection result so Stage 3 and the
evaluator can treat input-closed and runtime-closed translations uniformly:

```text
translate(field, pool, closed_set, context) -> {
  field:    str,
  selected: [str],          # always a subset of closed_set
  valid:    bool,
  phase:    "input_closed" | "runtime_closed",
  boolean_group?: { id, op: "AND" | "OR" },
  grounding?: { matched_ids: [...], expanded_from: "class"|"term"|"runtime"|null, confidence: 0..1 },
  machine_subquery?: { operator, field, value },  # input-closed phase only
  notes?:   str
}
```

`selected` is always a member subset of the provided closed set. For the
input-closed phase, `machine_subquery` is derived from `selected` and the field's
emission rules. For the runtime-closed phase, `selected` is applied directly as a
datapoint post-filter. `valid=false` means the translation returned `[]` or
`None`, or every candidate failed membership validation.

## Failure handling

- **Input closed-set field fails translation** -> exclude the constraint from
  the API query and record the invalid translation. A hard `MATCH` on an
  out-of-set value is never emitted because it would silently zero the query.
- **Runtime closed-set field fails translation** -> keep the fetched datapoints
  from the closed-set query and do not apply that post-filter.
- **LLM selects out-of-set candidates** -> reject the candidates, retry with
  feedback that it must choose exact items from the closed set, and keep only
  verified members.
- **Ambiguous field reading** -> try the configured candidate fields and keep the
  highest-confidence valid closed-set translation, recording the alternatives.
