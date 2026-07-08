# Pipeline design

The translator uses one count-gated production path:

```text
NL question
-> query expansion
-> query decomposition
-> TERMite enrichment
-> early closed-set translation
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
| Query decomposition | Split the expanded question into one component per field, classify each component as `filter` or `question`, and preserve field-level boolean hints. |
| TERMite enrichment | Enrich decomposed fragments with entity surfaces, preferred labels, synonyms, and entity types. |
| Early closed-set translation | Ground early closed-set filters against CSVs/enums/booleans and leave all other filters pending. |
| Early aggregation and count | Assemble the early API query, apply PK invariants, validate it, and read `data.countTotal`. |
| Small early result | When the early count is below `1000`, fetch datapoints for the early query and apply pending filters locally. |
| Non-early closed-set translation | When the early count is `1000` or higher, ground the remaining closed-set filters and aggregate a broader closed-set API query. |
| Small closed-set result | When the closed-set count is below `1000`, fetch datapoints and apply the remaining open-set filters locally. |
| Open-set translation | When the closed-set count is still `1000` or higher, translate open-set fields into API constraints, aggregate the full query, and execute the API count. |

Callers can run stage-level CLI surfaces for debugging, but production execution
uses this fixed operation order.

## Filter buckets

Closed-set fields are split into early and non-early translation buckets so the
API query grows only as much as needed.

| Bucket | Fields | Behavior |
|--------|--------|----------|
| Early closed set | `drugs`, `species`, `routes`, `documentSource`, `documentYear`, `isPreclinical` | Grounded first and used in the first API count. |
| Non-early closed set | `sex`, `concomitants`, `tissueSpecific`, `metabolitesEnantiomers` | User-supplied values are grounded only when the early count is at least `1000`; default PK invariants for these fields still apply to every API query. |
| Open set | `parameter`, `parameterDisplay`, `studyGroups`, `age`, `dose`, `duration` | Kept as row-side filters when a row gate succeeds; translated into API constraints only when both closed-set counts are at least `1000`. |

PK invariants are applied to every aggregated API query unless the user supplies
the same field. A user-supplied invariant field wins for that field.

## Decomposition

Decomposition is vocab-free for value selection. It routes text spans to fields
using the field catalog and user wording, but it does not choose taxonomy values.
Components have:

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

Only `type: "filter"` components become retrieval filters. `type: "question"`
components describe what to report from retrieved records and guide facets or
display columns.

Recognized PK parameters such as AUC, Cmax, and half-life are retrieval filters.
When a parameter phrase is also requested as an answer, decomposition keeps the
filter and carries the reporting intent separately.

## TERMite enrichment

TERMite enrichment attaches annotations to the decomposed components. The
annotation trace preserves:

- source surface from the user question;
- preferred entity label;
- entity type;
- synonyms or alternative labels.

TERMite labels and synonyms contribute candidates for closed-set grounding and
open-set phrase cleanup. They do not override the field selected by
decomposition.

## Translation and grounding

Closed-set translation follows the same resolution order for early and non-early
fields:

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
closed-set branch can fetch fewer than `1000` rows. When both closed-set counts
are at least `1000`, open-set fields emit direct `MATCH` or `REGEX` constraints
and record open-set provenance.

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
early_query = aggregate(early_closed_filters + invariants)
early_count = count(early_query)

when early_count < 1000:
  rows = fetch_datapoints(early_query)
  final_rows = apply(non_early_closed_filters + open_set_filters, rows)

when early_count >= 1000:
  closed_query = aggregate(early_closed_filters + non_early_closed_filters + invariants)
  closed_count = count(closed_query)

  when closed_count < 1000:
    rows = fetch_datapoints(closed_query)
    final_rows = apply(open_set_filters, rows)

  when closed_count >= 1000:
    full_query = aggregate(closed_filters + open_set_filters + invariants)
    final_count = count(full_query)
```

The final result records translated filters, pending filters, service invariants,
output options, validation issues, every API count branch that ran, row-fetch
status, runtime row filters, and either `final_filtered_count` or the final API
`countTotal`.
