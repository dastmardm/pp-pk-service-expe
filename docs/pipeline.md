# Pipeline design

The translator uses one count-gated production path:

```text
NL question
-> query expansion
-> query decomposition
-> TERMite enrichment
-> small-closed/early translation
-> aggregation and API count
-> row gate or staged translation
```

The row gate threshold is `1000` rows. A branch with `countTotal < 1000`
fetches datapoints and applies every remaining filter on the fetched rows. A
branch with `countTotal >= 1000` keeps translating more filter classes into the
API query until the result is small enough to fetch or the full API query has
been executed.

## Step responsibilities

| Step | Responsibility |
|------|----------------|
| Query expansion | Rewrite the question for clarity and abbreviation expansion while preserving meaning. |
| Query decomposition | Split the expanded question into one component per field, classify each component as `filter` or `question`, and emit `field`, `nl_fragment`, `type`, `reason`, and field-level boolean hints. |
| TERMite enrichment | Apply TERMite to each decomposed component's `nl_fragment` using that component's `field` as the enrichment context. |
| Small-closed/early translation | Ground CSV-backed closed fields whose current value set has fewer than `1000` items and leave all other filters pending. |
| Early aggregation and count | Assemble the early API query, apply PK invariants, validate it, and read `data.countTotal`. |
| Small early result | When the early count is below `1000`, fetch datapoints for the early query and apply pending filters locally. |
| Closed translation | When the early count is `1000` or higher, ground CSV-backed closed fields whose current value set has `1000` or more items and aggregate a broader API query. |
| Small closed result | When the closed count is below `1000`, fetch datapoints and apply the remaining open-set filters locally. |
| Open-set translation | When the closed count is still `1000` or higher, translate open-set fields into API constraints, aggregate the full query, and execute the API count. |

Callers can run stage-level CLI surfaces for debugging, but production execution
uses this fixed operation order.

## Filter buckets

CSV-backed closed fields are split by current value-set size so the API query
grows only as much as needed. A closed field with fewer than `1000` values is a
small closed field, also called an early field. A closed field with `1000` or
more values remains a closed field. Other PK request buckets keep their own
names.

| Bucket | Fields | Behavior |
|--------|--------|----------|
| Small closed / early | `species`, `routes`, `documentSource`, `documentYear` | CSV-backed closed fields with fewer than `1000` values. Grounded first and used in the first API count. |
| Closed | `drugs` | CSV-backed closed fields with `1000` or more values. Grounded only when the early count is at least `1000`. |
| Enum | `sex` | Keeps its enum bucket and finite inline value set. |
| Boolean | `isPreclinical` | Keeps its boolean bucket and finite inline value set. |
| Enum/invariant | `concomitants`, `tissueSpecific`, `metabolitesEnantiomers` | Keeps its enum/invariant bucket. User value wins; otherwise PK defaults apply to every API query. |
| Open set | `parameter`, `parameterDisplay`, `studyGroups`, `age`, `dose`, `duration` | Kept as row-side filters when a row gate succeeds; translated into API constraints only when the closed count is at least `1000`. |

PK invariants are applied to every aggregated API query unless the user supplies
the same field. A user-supplied invariant field wins for that field.

## Decomposition

Decomposition is vocab-free for value selection. It routes text spans to fields
using the field catalog and user wording, but it does not choose taxonomy values.
Each component carries the selected `field`, the natural-language fragment for
that field, the component `type`, and a `reason` explaining why the fragment
belongs to that field. Components have:

```json
{
  "field": "parameter",
  "nl_fragment": "AUC",
  "type": "filter",
  "reason": "The user restricts results to AUC PK records.",
  "source": "query",
  "boolean_group": { "id": "parameter-1", "op": "OR" }
}
```

The `field` value is the field context for TERMite enrichment. TERMite is applied
to the component's `nl_fragment` in that field context, while `reason` is kept as
the audit trail for the field assignment.

Only `type: "filter"` components become retrieval filters. `type: "question"`
components describe what to report from retrieved records and guide facets or
display columns.

Recognized PK parameters such as AUC, Cmax, and half-life are retrieval filters.
When a parameter phrase is also requested as an answer, decomposition keeps the
filter and carries the reporting intent separately.

## TERMite enrichment

TERMite enrichment attaches annotations to the decomposed components. For each
component, TERMite receives the component `nl_fragment` and the selected `field`
from decomposition. The annotation trace preserves:

- source surface from the user question;
- preferred entity label;
- entity type;
- synonyms or alternative labels.

TERMite labels and synonyms contribute candidates for closed-set grounding and
open-set phrase cleanup. The decomposition `field` remains the authoritative
field for the component; TERMite enriches that field-scoped fragment.

## Translation and grounding

CSV-backed small closed and closed translation follow the same resolution order:

1. Normalize the fragment with the field-aware normalizer.
2. Build a pool from the fragment, TERMite preferred labels, and TERMite
   synonyms.
3. Try exact lookup against the closed set.
4. Try fuzzy lookup.
5. Ask the LLM for equivalent pool items and retry lookup.
6. Ask the LLM to select from a focused closed-set candidate list.
7. Re-ground every selected candidate and reject anything outside the closed set.

The grounding trace uses:

```text
grounding = {
  matched_ids: [...],
  expanded_from: "class" | "term" | "runtime" | null,
  confidence: 0..1
}
```

Hierarchy expansion is explicit. Exact species and drug class labels can be
emitted as class labels; colloquial species groups without an exact class label
expand to matching member species. Specific leaves are not widened.

Open-set fields have no complete local value set. They remain pending while a
small-closed or closed branch can fetch fewer than `1000` rows. When the closed
count is at least `1000`, open-set fields emit direct `MATCH` or `REGEX`
constraints and record open-set provenance.

## Normalization

Normalization runs inside translation before closed-set lookup or open-set API
constraint emission. Closed-set fields can normalize aggressively because every
correction is later validated against the closed set. Open-set fields use
conservative surface cleanup because no complete input value list exists.

| Strategy | Applies to | Purpose |
|----------|------------|---------|
| Conservative cleanup | Open sets | Strip connective text while preserving the user's phrase. |
| Fuzzy match | Closed sets | Resolve typos against CSV or inline values. |
| Phonetic match | Closed sets | Handle sound-alike typos over taxonomy names. |
| TERMite-first | Closed sets | Prefer TERMite labels when they match the field. |
| LLM pool enrichment | Closed sets | Generate equivalent search phrases, then ground them. |
| Hybrid | Closed sets | Combine shortlist generation, LLM disambiguation, and membership validation. |

## Aggregation and execution

Aggregation keeps valid filters, groups per-field boolean intent, and joins
unrelated fields with top-level `AND`. All PK filters are emitted directly in the
top-level `query`; PK does not use `entityFilters`.

The execution branch is:

```text
early_query = aggregate(small_closed_filters + invariants)
early_count = count(early_query)

when early_count < 1000:
  rows = fetch_datapoints(early_query)
  final_rows = apply(closed_filters + enum_boolean_invariant_filters + open_set_filters, rows)

when early_count >= 1000:
  closed_query = aggregate(small_closed_filters + closed_filters + enum_boolean_invariant_filters + invariants)
  closed_count = count(closed_query)

  when closed_count < 1000:
    rows = fetch_datapoints(closed_query)
    final_rows = apply(open_set_filters, rows)

  when closed_count >= 1000:
    full_query = aggregate(small_closed_filters + closed_filters + enum_boolean_invariant_filters + open_set_filters + invariants)
    final_count = count(full_query)
```

The final result records translated filters, pending filters, service invariants,
output options, validation issues, every API count branch that ran, row-fetch
status, runtime row filters, and either `final_filtered_count` or the final API
`countTotal`.
