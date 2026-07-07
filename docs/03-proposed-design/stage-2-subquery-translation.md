# Stage 2 - Per-field translation

**Input:** filter components from Stage 1, each carrying one field and one NL
fragment, with Stage 0 TERMite annotations applied.
**Output:** valid machine subqueries for early-contributor and resolved large
closed-set fields, plus validated post-filters for open-set fields resolved
against fetched datapoints.

This stage is where the closed-set/open-set distinction is enforced. A
translation is valid only when it chooses values from a known set. The set may be
known before the first API call (`inputs/` CSVs and inline enums), derived from
the unique values present in early-contributor fetched datapoints, or observed in
the final fetched datapoints for open-set fields.

Question components do not become filters. They are carried forward so Stage 3
can choose facets or `displayColumns`.

## Three translation passes

The `EARLY_CONTRIBUTOR_THRESHOLD` (default 500) determines which fields are
translated first. A field is an early contributor when its input closed-set
vocabulary size is below this threshold.

```
Stage-1 filter components (with Stage-0 TERMite annotations)
        │
        ├─ Pass A: early-contributor closed-set fields
        │     criterion: vocabulary size < EARLY_CONTRIBUTOR_THRESHOLD
        │     closed_set = CSV / enum / boolean values
        │     pool = NL fragment + TERMite labels + synonyms
        │     translate_closed_set(pool, closed_set)
        │     valid subset -> machine subquery
        │     [] / None    -> invalid, excluded downstream
        │
        ├─ aggregate valid Pass-A subqueries (Stage 3A)
        │     -> first API query
        │     -> fetched datapoints
        │
        ├─ Pass B: runtime narrowing of large closed-set fields (iterative)
        │     for each large closed-set field (≥ threshold):
        │       runtime_closed_set = unique values for that field
        │                            in fetched datapoints
        │       if len(runtime_closed_set) < threshold:
        │         translate_closed_set(pool, runtime_closed_set)
        │         valid subset -> machine subquery (new contributor)
        │     repeat until no new contributors found in a round
        │
        ├─ aggregate all contributor subqueries (Stage 3B)
        │     -> final API query
        │     -> final fetched datapoints
        │
        └─ Pass C: open-set fields
              closed_set = unique values for that field in final fetched datapoints
              pool = NL fragment + generated synonyms
              translate_closed_set(pool, closed_set)
              valid subset -> post-filter datapoints
              [] / None    -> invalid, no downstream narrowing
```

The same closed-set translator is used in all three passes. The differences are
the source of the closed set and the point at which the pass runs.

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
5. **Membership assertion and retry.** Assert every LLM-selected candidate
   against `closed_set`. Reject out-of-set candidates, retry with explicit
   feedback that the model must choose exact items from the provided closed set,
   and keep only verified members.
6. **Invalid result.** If the selected list is still empty, the translation
   fails and is marked invalid.

The final emitted value is always a valid subset of the available entities.

In the v0.1 implementation, this membership assertion is enforced by
re-grounding every LLM proposal against the CSV (`exact` first, then `fuzzy`) and
dropping any proposal that cannot be verified. The synonym-mapping fallback makes
several attempts to recover from empty model responses; the closed-set window
selection path keeps only re-grounded rows.

## Early-contributor closed-set fields (Pass A)

For fields backed by [inputs/](../../inputs/) taxonomies whose vocabulary is below
`EARLY_CONTRIBUTOR_THRESHOLD`, the closed set is the CSV's preferred-label list.
The generic algorithm handles typos, synonyms, and hierarchy:

1. **Normalize.** Run the field normalizer over the NL
   fragment first (see [misspelling-strategy.md](misspelling-strategy.md)).
   Closed-set fields can safely normalize toward the nearest known entity because
   every correction is later validated against the closed set.
2. **Build the pool.** Start with the normalized fragment. Add matching Stage-0
   TERMite preferred labels and synonyms. Add LLM-generated synonyms only if
   exact and fuzzy search over the initial pool fail.
3. **Translate over the closed set.** Run the closed-set translator above.
4. **Expand hierarchy when the selected entity is a class or rollup.**
   - drug class -> class label, resolved server-side by the API;
   - exact species class -> class label, resolved server-side by the API;
   - colloquial species groups with no exact class label, such as "Monkeys",
     -> the matching member species.
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

## Runtime narrowing of large closed-set fields (Pass B)

Large closed-set fields (vocabulary ≥ `EARLY_CONTRIBUTOR_THRESHOLD`) are deferred
until the early-contributor API query has returned datapoints. The unique values
for each such field present in those datapoints form its runtime narrowed set:

1. Collect the unique non-empty values for that field from the early-contributor
   fetched datapoints.
2. If the count of unique values is below `EARLY_CONTRIBUTOR_THRESHOLD`, the field
   becomes a new contributor:
   - Build a pool from the NL fragment, TERMite preferred labels, and synonyms.
   - Run the closed-set translator against the narrowed value list.
   - A valid translation produces a machine subquery included in the final API
     query (Stage 3B).
3. Repeat steps 1–2 for the datapoints returned by each successive API query until
   no new fields cross the threshold in a round.
4. Fields that never cross the threshold after all rounds remain unresolved as
   contributors and are handled in Pass C.

## Open-set post-filters (Pass C)

Open-set fields and any large closed-set fields that could not be resolved as
contributors are deferred until the final API query (Stage 3B) has fetched
datapoints:

1. Collect the unique non-empty values for that field from the final fetched
   datapoints.
2. Build a pool from the user's NL fragment and LLM-generated synonyms.
3. Run the same closed-set translator against the runtime value list.
4. Keep only datapoints whose field value is in the returned subset.

This turns a field such as `parameter`, `parameterDisplay`, `studyGroup`, `age`,
`dose`, or `duration` into a validated post-filter instead of a raw LLM value
in the API query.

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
evaluator can treat all translation phases uniformly:

```text
translate(field, pool, closed_set, context) -> {
  field:    str,
  selected: [str],          # always a subset of closed_set
  valid:    bool,
  phase:    "early_contributor" | "runtime_narrowed" | "runtime_open",
  boolean_group?: { id, op: "AND" | "OR" },
  grounding?: { matched_ids: [...], expanded_from: "class"|"term"|"runtime"|null, confidence: 0..1 },
  machine_subquery?: { operator, field, value },  # early_contributor and runtime_narrowed phases only
  notes?:   str
}
```

`selected` is always a member subset of the provided closed set. For the
`early_contributor` and `runtime_narrowed` phases, `machine_subquery` is derived
from `selected` and the field's emission rules. For the `runtime_open` phase,
`selected` is applied directly as a datapoint post-filter. `valid=false` means the
translation returned `[]` or `None`, or every candidate failed membership
validation.

## Failure handling

- **Early-contributor field fails translation** -> exclude the constraint from the
  API query and record the invalid translation. A hard `MATCH` on an out-of-set
  value is never emitted because it would silently zero the query.
- **Runtime-narrowed field fails translation** -> the field is not added as a
  contributor; it may still be handled as a post-filter in Pass C.
- **Open-set field fails post-filter translation** -> keep the fetched datapoints
  from the final query and do not apply that post-filter.
- **LLM selects out-of-set candidates** -> reject the candidates, retry with
  feedback that it must choose exact items from the closed set, and keep only
  verified members.
- **Ambiguous field reading** -> try the configured candidate fields and keep the
  highest-confidence valid closed-set translation, recording the alternatives.
