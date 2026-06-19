# Proposed architecture

## The idea in one diagram

```
                          ┌───────────────────────────────────────┐
   NL query  ───────────▶ │  STAGE 0 — ENHANCE  (optional)         │
 "ADRs of sunitinib       │  default: noop · opt-in: TERMite NER   │
  in human?"              │  → entities + preferred labels + types │
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
        ║ STAGE 2 — PER-FIELD TRANSLATION  (independent, parallel)       ║
        ║ each NL subquery  →  one machine subquery (a filter)          ║
        ║                                                               ║
        ║   CLOSED-VOCAB field → tool-call lookup against CSV           ║
        ║      "sunitinib" ──lookup drugs.csv──▶                        ║
        ║                    MATCH drugsFuzzy = ["Sunitinib*"]          ║
        ║      "human"     ──lookup species.csv──▶                      ║
        ║                    MATCH species = "Human"                    ║
        ║                                                               ║
        ║   OPEN field → LLM decides value directly                    ║
        ║      "hepatic impairment" ──▶ REGEX studyGroup = "(cirrho…"   ║
        ╚═══════════════════════════════════════════════════════════════╝
                       └──────────────────┼──────────────────┘
                                          ▼
        ╔═══════════════════════════════════════════════════════════════╗
        ║ STAGE 3 — AGGREGATION                                          ║
        ║ machine subqueries  →  one final machine query               ║
        ║   • combine into the boolean tree (AND across fields)         ║
        ║   • preserve per-field & cross-field OR/AND/NOT               ║
        ║   • route to entityFilters where required                     ║
        ║   • add facets / displayColumns                               ║
        ║   • apply service invariants (PK concomitants, etc.)          ║
        ╚═══════════════════════════════════════════════════════════════╝
                                          │
                                          ▼
                                  final machine query  ──▶  PharmaPendium API
```

## Why three stages

An **optional Stage 0 enhancer** (TERMite, `noop` by default) may normalize
entities before Stage 1; the three core stages below are the heart of the design.

| Stage | Responsibility | Why separate |
|-------|---------------|--------------|
| **1. Decomposition** | Split the NL query into one NL fragment per field; route each fragment to a field. | Isolates "what is the user asking about?" from "how do I express it?". Small, cheap, testable. |
| **2. Per-field translation** | Turn one NL fragment into one `(operator, field, value)` filter. Ground closed-vocab values on CSV; let the LLM decide open ones. | This is where grounding and hierarchy live. Each field gets a focused translator that can be tested, evaluated, and improved in isolation. Naturally parallel. |
| **3. Aggregation** | Assemble filters into the final boolean tree; apply boolean intent, entity-filter routing, facets, and service invariants. | Cross-field structure and service rules are a distinct concern from per-field value selection. |

This is the inverse of the legacy design, where one prompt does all three at once
(see [../01-current-system/legacy-architecture.md](../01-current-system/legacy-architecture.md)).

## Design principles

1. **Ground, don't generate.** If a field has a CSV, the value comes from the
   CSV. The model's job shrinks to *selecting* and *expanding*, not *inventing*.
2. **One field, one translator.** Every field has an isolated, testable unit.
   Closed-vocab fields share a generic CSV-lookup translator; a handful of fields
   (numeric, free-text-with-synonyms) get bespoke logic.
3. **Make boolean structure explicit.** Per-field booleans in Stage 2; cross-field
   booleans in Stage 3. Never implicit in prose.
4. **Hierarchy is a first-class operation.** Class→members, category→terms,
   parent→children expansion is a documented step, not a hope.
5. **Enhancement is optional.** TERMite is an **opt-in Stage 0 enhancer**
   (default `noop`). When enabled it contributes high-quality preferred labels and
   IDs that *hint* Stage 1 routing and Stage 2 grounding — a booster, not a
   required pre-step. The production Stage 1 decomposer is vocab-free and works
   without it.

## Relationship to the three services

The pipeline shape is identical for Safety, PK, and RTB. What differs is
configuration, not architecture:

- the **field set** (which fields exist),
- the **field→bucket map** (which are closed-vocab),
- the **facet allow-list**,
- the **service invariants** applied in Stage 3,
- the **output surface** (Safety/PK emit JSON; RTB emits a `where_clause` string).

A per-service config object should carry these; the stage code stays shared.

## Open questions

- **`targets` taxonomy.** Used by the gold set (Q21) and listed in
  [enums.csv](../../inputs/enums.csv), but no `targets.csv` is shipped in
  `inputs/`. Do we export one, or resolve targets via the back-end fuzzy-lookup
  endpoint at runtime?
- **MedDRA effect rollups.** The gold set repeatedly notes "MedDRA rules not yet
  implemented." Is the parent/child structure in [effects.csv](../../inputs/effects.csv)
  sufficient, or do we need the full MedDRA SOC→HLGT→HLT→PT hierarchy?
- **Drug-class detection vs target detection.** Q8/Q21 show "kinase" being
  mis-typed as a target. Does Stage 1 disambiguate class-vs-target, or does Stage
  2 try both lookups and let confidence decide?
- **Where does TERMite stop and CSV lookup start?** Both can resolve preferred
  labels. Proposed split is in
  [grounding-and-tool-calling.md](grounding-and-tool-calling.md); needs validation.
- **Decomposition granularity.** Is it strictly one subquery per field, or per
  *concept* (e.g. two distinct effects → two subqueries that Stage 3 OR-joins)?
  See [stage-1-decomposition.md](stage-1-decomposition.md).
