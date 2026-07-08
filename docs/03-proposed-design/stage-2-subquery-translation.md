# Stage 2 - Per-field translation

**Input:** filter components from Stage 1, each carrying one field and one NL
fragment, with Stage 0 TERMite annotations applied.
**Output:** valid machine subqueries for closed-set and open-set fields.

This stage is where the closed-set/open-set distinction is enforced. A
closed-set translation is valid only when it chooses values from a known set. The
set is known before the API call (`inputs/` CSVs and inline enums). Open-set
translation emits direct API constraints because no local value set exists.

Question components do not become filters. They are carried forward so Stage 3
can choose facets or `displayColumns`.

## Translation passes

The `EARLY_CONTRIBUTOR_THRESHOLD` (default 500) determines which fields are
translated first. A field is an early contributor when its input closed-set
vocabulary size is below this threshold.

```
Stage-1 filter components (with Stage-0 TERMite annotations)
        │
      ├─ Pass A: closed-set fields
        │     criterion: vocabulary size < EARLY_CONTRIBUTOR_THRESHOLD
        │     closed_set = CSV / enum / boolean values
        │     pool = NL fragment + TERMite labels + synonyms
        │     translate_closed_set(pool, closed_set)
        │     valid subset -> machine subquery
        │     [] / None    -> invalid, excluded downstream
        │
        └─ Pass B: open-set fields
           no input closed_set
           emit direct MATCH or REGEX constraint
           live execution may run an isolated zero-count probe
```

The closed-set translator is used for fields with known values. Open-set fields
use a conservative direct-emission translator and optional probe guard.

## Closed-set translator

The translator is a tool over a closed set of entities. It starts with:

- `field`: the field being filtered;
- `pool`: one or more candidate phrasings for the user's intended value;
- `closed_set`: the legal entities for the field.

It always returns a **sublist of `closed_set`**. Returning `[]` or `None` means
translation failed. A failed translation is marked invalid and does not affect
   the API query, entity filters, facets, or display columns.

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

This membership assertion is enforced by re-grounding every LLM proposal against
the CSV (`exact` first, then `fuzzy`) and dropping any proposal that cannot be
verified. The LLM receives one retry with explicit membership feedback.

## Closed-set fields (Pass A)

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
{ "field": "species", "value": ["African green monkey", "Cynomolgus monkey", "Rhesus monkey"] }
```

## Open-set fields (Pass B)

Open fields are handled by `_translate_open` before aggregation:

- `studyGroups` and `age` emit `REGEX` constraints; `studyGroups` expands a small
  built-in synonym set for hepatic and renal impairment.
- Plain free-text fields such as `parameter` and `parameterDisplay` emit `MATCH`
  constraints.
- Live runs can call `drop_empty_open_filters` before aggregation to remove an
  open-set filter whose isolated API count is confirmed as `0`.

The open-set translator records the emitted constraint and any probe warning in
the grounding trace.

## Per-field contract

Every field translator exposes a common envelope plus phase-specific fields so
Stage 3 can treat closed-set and open-set translations uniformly without
pretending open-set values came from a closed set:

```text
translate(field, pool, closed_set, context) -> {
  field:    str,
  selected: [str] | null,   # closed-set only; always a subset of closed_set
  valid:    bool,
  phase:    "closed_set" | "open_set",
  boolean_group?: { id, op: "AND" | "OR" },
  grounding?: { matched_ids: [...], expanded_from: "class"|"term"|"runtime"|null, confidence: 0..1 },
  machine_subquery?: { operator, field, value },
  notes?:   str
}
```

For the `closed_set` phase, `selected` is a member subset of the provided closed
set and `machine_subquery` is derived from `selected` and the field's emission
rules. In the `open_set` phase, `selected` is null and `machine_subquery` is the
direct `MATCH` or `REGEX` constraint. `valid=false` means the translation
returned no usable machine subquery, or every closed-set candidate failed
membership validation.

## Failure handling

- **Closed-set field fails translation** -> exclude the constraint from the
  API query and record the invalid translation. A hard `MATCH` on an out-of-set
  value is never emitted because it would silently zero the query.
- **Open-set field fails translation** -> exclude the constraint from the API
   query and record the invalid translation. If a live zero-count probe confirms
   that an emitted open-set filter matches no records, drop that filter and record
   a warning.
- **LLM selects out-of-set candidates** -> reject the candidates, retry with
  feedback that it must choose exact items from the closed set, and keep only
  verified members.
- **Ambiguous field reading** -> try the configured candidate fields and keep the
  highest-confidence valid closed-set translation, recording the alternatives.
