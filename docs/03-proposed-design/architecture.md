# Proposed architecture

## The idea in one diagram

```
                          ┌───────────────────────────────────────┐
   NL query  ───────────▶ │  STAGE -1 — EXPAND                    │
 "ADRs of sunitinib       │  LLM expansion                         │
  in human?"              │  → clearer query, same entities        │
                          └───────────────────────────────────────┘
                                          │
                                          ▼
        ╔═══════════════════════════════════════════════════════════════╗
        ║ STAGE 1 — DECOMPOSITION                                        ║
        ║ NL query  →  many single-field NL subqueries                  ║
        ║   • {field: drugs,   nl: "sunitinib"}                         ║
        ║   • {field: species, nl: "human"}                            ║
        ║   • {field: parameter, nl: "AUC" (output intent)}            ║
        ╚═══════════════════════════════════════════════════════════════╝
                                          │
                                          ▼
                          ┌───────────────────────────────────────┐
                          │  STAGE 0 — TERMite ENHANCE             │
                          │  required SciBite NER over decomposed  │
                          │  fragments                             │
                          │  → entities + preferred labels + types │
                          └───────────────────────────────────────┘
                                          │
                                          ▼
        ╔═══════════════════════════════════════════════════════════════╗
        ║ STAGE 2A — EARLY-CONTRIBUTOR TRANSLATION                       ║
        ║ closed-set fields with < EARLY_CONTRIBUTOR_THRESHOLD items    ║
        ║ are resolved first (default threshold: 500 items)             ║
        ║                                                               ║
        ║   CSV/enum field → exact → fuzzy → enriched pool → LLM select ║
        ║      "sunitinib" ──lookup drugs.csv──▶                        ║
        ║                    MATCH drugsFuzzy = ["Sunitinib*"]          ║
        ║      "human"     ──lookup species.csv──▶                      ║
        ║                    MATCH species = "Human"                    ║
        ║                                                               ║
        ║   large closed-set fields (≥ threshold) and open-set fields   ║
        ║   are deferred until early-contributor datapoints are fetched  ║
        ╚═══════════════════════════════════════════════════════════════╝
                                          │
                                          ▼
        ╔═══════════════════════════════════════════════════════════════╗
        ║ STAGE 3A — EARLY-CONTRIBUTOR AGGREGATION + FETCH              ║
        ║ early-contributor subqueries → first API query → datapoints   ║
        ║   • combine into the boolean tree (AND across fields)         ║
        ║   • preserve per-field & cross-field OR/AND/NOT               ║
        ║   • route to entityFilters where required                     ║
        ║   • add facets / displayColumns                               ║
        ║   • apply service invariants (PK concomitants, etc.)          ║
        ╚═══════════════════════════════════════════════════════════════╝
                                          │
                                          ▼
        ╔═══════════════════════════════════════════════════════════════╗
        ║ STAGE 2B — RUNTIME NARROWING OF LARGE CLOSED-SET FIELDS       ║
        ║ fetched datapoints provide a narrowed value list for each     ║
        ║ large closed-set field (≥ threshold items)                    ║
        ║   • collect unique values per field from fetched datapoints   ║
        ║   • any field whose unique count is now < threshold becomes   ║
        ║     a new contributor and is translated against that list     ║
        ║   • repeat iteratively until no new fields cross the          ║
        ║     threshold in a round                                      ║
        ║   • remaining large-closed-set and open-set fields are        ║
        ║     post-filtered against the fetched datapoints              ║
        ╚═══════════════════════════════════════════════════════════════╝
                                          │
                                          ▼
        ╔═══════════════════════════════════════════════════════════════╗
        ║ STAGE 3B — FINAL AGGREGATION + FETCH                          ║
        ║ all resolved contributor subqueries → final API query         ║
        ║ (same assembly rules as Stage 3A, now with all resolved       ║
        ║  contributor filters included)                                ║
        ╚═══════════════════════════════════════════════════════════════╝
                                          │
                                          ▼
        ╔═══════════════════════════════════════════════════════════════╗
        ║ STAGE 2C — OPEN-SET POST-FILTERS                              ║
        ║ fetched datapoints provide unique values for open-set fields  ║
        ║   "maternal toxicity" → select from fetched comments          ║
        ║   valid subset → post-filter datapoints                       ║
        ╚═══════════════════════════════════════════════════════════════╝
```

## Why these stages

Stage -1 expansion clarifies abbreviations before decomposition. Stage 1 decomposes the query into single-field fragments; Stage 0 TERMite then annotates those fragments so entity recognition operates on focused spans rather than the full raw query. The remaining stages drive the grounding and fetch loop.

| Stage | Responsibility | Why separate |
|-------|---------------|--------------|
| **1. Decomposition** | Split the expanded NL query into one NL fragment per field; route each fragment to a field. | Isolates "what is the user asking about?" from "how do I express it?". Small, cheap, testable. |
| **0. TERMite enhancement** | Run NER over the decomposed per-field fragments; annotate entities, preferred labels, and entity types. | Targeting focused fragments reduces ambiguity; annotations seed Stage 2 translation with high-confidence preferred labels. |
| **2A. Early-contributor translation** | Translate closed-set fields whose vocabulary is below `EARLY_CONTRIBUTOR_THRESHOLD` (default 500 items). | Small-vocabulary fields produce fast, accurate matches and narrow the result space before larger fields are evaluated. |
| **3A. Early-contributor fetch** | Assemble early-contributor subqueries into the first API query and fetch datapoints. | Provides a real result sample whose unique field values drive iterative narrowing of large-vocabulary fields. |
| **2B. Runtime narrowing** | For each large closed-set field (≥ threshold), collect unique values from the fetched datapoints and translate against that narrowed list. Any field whose runtime unique count falls below the threshold becomes a new contributor; repeat until convergence. | Reduces the effective vocabulary for expensive fields without upfront exhaustive closed-set search. |
| **3B. Final fetch** | Assemble all resolved contributor subqueries into the final API query and fetch datapoints. | Retrieves the definitive result set incorporating every resolved field. |
| **2C. Open-set post-filters** | For every deferred open-set field, collect unique values from the final fetched datapoints, translate against that runtime closed set, and post-filter rows. | Open-set fields have no complete value list before fetch; runtime grounding ensures every post-filter value is observed in the data. |

In the v0.1 implementation, [execute.py](../../src/oppp/execute.py) reads
`countTotal` only; it does not fetch rows. Open-set filters are currently emitted
as direct `MATCH`/`REGEX` constraints, with a server-side zero-count probe
(`drop_empty_open_filters`) before aggregation in live runs. The early-contributor
and runtime-narrowing paths above are the intended data-flow once row fetching
is available.

This is the inverse of the legacy design, where one prompt did all three at once.

## Design principles

1. **Ground, don't generate.** Every filter value comes from a closed set: an
   input CSV/enum/boolean set before the first API call, or the unique values in
   fetched datapoints for open-set post-filtering.
2. **One field, one translator.** Every field has an isolated, testable unit.
   The same closed-set translator handles exact search, fuzzy search, LLM pool
   enrichment, and LLM selection from a known entity set.
3. **Make boolean structure explicit.** Per-field booleans in Stage 2; cross-field
   booleans in Stage 3. Never implicit in prose.
4. **Hierarchy is a first-class operation.** Class→members, category→terms,
   parent→children expansion is a documented step, not a hope.
5. **Expansion and enhancement are separate.** Stage -1 rewrites only for
   readability and abbreviation expansion. Stage 0 always contributes TERMite
   entity annotations and preferred labels over the decomposed per-field fragments.
   Neither stage may emit machine-query values on its own; TERMite labels seed
   later routing and translation only.

## Service configuration

The pipeline targets the PK service on the PharmaPendium API. The service
configuration object defines:

- the **field set** (which fields exist),
- the **field→bucket map** (early-contributor closed-set, large closed-set, runtime open-set, enum, boolean),
- the **facet allow-list**,
- the **service invariants** applied in Stage 3 (`concomitants`, `tissueSpecific`, `metabolitesEnantiomers` defaults).

The stage code is independent of the configuration object.

## Settled field behavior

- Drug-class phrases prefer a valid drug-class translation when the drug closed
  set contains that class.
- Species classes use the available [species.csv](../../inputs/species.csv)
  hierarchy: an exact class label resolves server-side; colloquial groups without
  an exact class label (e.g. "Monkeys") expand to their member species.
- TERMite labels seed the translation pool; CSVs and runtime closed sets remain
  the authority for what values may be emitted.
- Decomposition emits one component per concept, tagged with the same field and
  a shared boolean group when several concepts belong to one field.
