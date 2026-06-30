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
                          ┌───────────────────────────────────────┐
                          │  STAGE 0 — TERMite ENHANCE             │
                          │  required SciBite NER                  │
                          │  → entities + preferred labels + types │
                          └───────────────────────────────────────┘
                                          │
                                          ▼
        ╔═══════════════════════════════════════════════════════════════╗
        ║ STAGE 1 — DECOMPOSITION                                        ║
        ║ NL query  →  many single-field NL subqueries                  ║
        ║   • {field: drugs,   nl: "sunitinib"}                         ║
        ║   • {field: species, nl: "human"}                            ║
        ║   • {field: effects, nl: "ADRs" (output intent)}             ║
        ╚═══════════════════════════════════════════════════════════════╝
                                          │  (one item per field)
                       ┌──────────────────┼──────────────────┐
                       ▼                  ▼                  ▼
        ╔═══════════════════════════════════════════════════════════════╗
        ║ STAGE 2A — INPUT CLOSED-SET TRANSLATION                        ║
        ║ each closed-set filter  →  valid machine subquery             ║
        ║                                                               ║
        ║   CSV/enum field → exact → fuzzy → enriched pool → LLM select ║
        ║      "sunitinib" ──lookup drugs.csv──▶                        ║
        ║                    MATCH drugsFuzzy = ["Sunitinib*"]          ║
        ║      "human"     ──lookup species.csv──▶                      ║
        ║                    MATCH species = "Human"                    ║
        ║                                                               ║
        ║   open-set filters are deferred until datapoints are fetched  ║
        ╚═══════════════════════════════════════════════════════════════╝
                       └──────────────────┼──────────────────┘
                                          ▼
        ╔═══════════════════════════════════════════════════════════════╗
        ║ STAGE 3 — AGGREGATION + FETCH                                  ║
        ║ valid closed-set subqueries → API query → datapoints          ║
        ║   • combine into the boolean tree (AND across fields)         ║
        ║   • preserve per-field & cross-field OR/AND/NOT               ║
        ║   • route to entityFilters where required                     ║
        ║   • add facets / displayColumns                               ║
        ║   • apply service invariants (PK concomitants, etc.)          ║
        ╚═══════════════════════════════════════════════════════════════╝
                                          │
                                          ▼
        ╔═══════════════════════════════════════════════════════════════╗
        ║ STAGE 2B — RUNTIME CLOSED-SET POST-FILTERS                    ║
        ║ fetched datapoints provide unique values for open-set fields  ║
        ║   "maternal toxicity" → select from fetched comments          ║
        ║   valid subset → post-filter datapoints                       ║
        ╚═══════════════════════════════════════════════════════════════╝
```

## Why three stages

Stage -1 expansion may clarify abbreviations before entity recognition. Required
Stage 0 TERMite enhancement annotates entities before Stage 1. The three core
stages below are the heart of the design.

| Stage | Responsibility | Why separate |
|-------|---------------|--------------|
| **1. Decomposition** | Split the TERMite-enhanced NL query into one NL fragment per field; route each fragment to a field. | Isolates "what is the user asking about?" from "how do I express it?". Small, cheap, testable. |
| **2. Per-field translation** | Translate a field fragment against a known closed set. Input closed-set fields use CSV/enum/boolean values; open-set fields wait until fetched datapoints provide a runtime closed set. | This is where grounding and hierarchy live. Each field gets a focused translator that can be tested, evaluated, and improved in isolation. Naturally parallel. |
| **3. Aggregation + fetch** | Assemble valid input closed-set filters into the first API query; apply boolean intent, entity-filter routing, facets, service invariants, and fetch datapoints for runtime post-filtering. | Cross-field structure, service rules, and API execution are distinct from per-field value selection. |

In the v0.1 implementation, [execute.py](../../src/oppp/execute.py) reads
`countTotal` only; it does not fetch rows. Open-set filters are currently emitted
as direct `MATCH`/`REGEX` constraints, with a server-side zero-count probe
(`drop_empty_open_filters`) before aggregation in live runs. The runtime
closed-set row post-filter path above is the intended data-flow once row fetching
is available.

This is the inverse of the legacy design, where one prompt does all three at once
(see [../01-current-system/legacy-architecture.md](../01-current-system/legacy-architecture.md)).

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
   entity annotations and preferred labels. Neither stage may emit machine-query
   values on its own; TERMite labels seed later routing and translation only.

## Relationship to the three services

The pipeline shape is identical for Safety, PK, and RTB. What differs is
configuration, not architecture:

- the **field set** (which fields exist),
- the **field→bucket map** (input closed-set, runtime open-set, enum, boolean),
- the **facet allow-list**,
- the **service invariants** applied in Stage 3,
- the **output surface** (Safety/PK emit JSON; RTB emits a `where_clause` string).

A per-service config object carries these; the stage code stays shared.

## Settled field behavior

- `targets` is treated as an open-set entity-routed field unless a complete local
  target taxonomy is available in `inputs/`. The current translator emits a
  `DrugsTargets` entity filter and uses the TERMite preferred label when a
  corresponding target annotation exists.
- Effect rollups use the available [effects.csv](../../inputs/effects.csv)
  hierarchy. A grounded leaf may expand through its parent family according to
  the field's rollup rules.
- Drug-class and target-like phrases prefer a valid drug-class translation when
  the drug closed set contains that class. Otherwise they stay on the configured
  target/open-set path.
- TERMite labels seed the translation pool; CSVs and runtime closed sets remain
  the authority for what values may be emitted.
- Decomposition emits one component per concept, tagged with the same field and
  a shared boolean group when several concepts belong to one field.
