# Proposed architecture

## The idea in one diagram

```
                          ┌───────────────────────────────────────┐
   NL query  ───────────▶ │  STAGE -1 — EXPAND                    │
 "AUC of sunitinib        │  LLM expansion                         │
  in human?"              │  → clearer query, same entities        │
                          └───────────────────────────────────────┘
                                          │
                                          ▼
                          ┌───────────────────────────────────────┐
                          │  STAGE 0 — TERMite ENHANCE             │
                          │  required SciBite NER over the         │
                          │  expanded query                        │
                          │  → entities + preferred labels + types │
                          └───────────────────────────────────────┘
                                          │
                                          ▼
        ╔═══════════════════════════════════════════════════════════════╗
        ║ STAGE 1 — DECOMPOSITION                                        ║
        ║ enhanced NL query  →  many single-field NL subqueries         ║
        ║   • {field: drugs,   nl: "sunitinib"}                         ║
        ║   • {field: species, nl: "human"}                            ║
        ║   • {field: parameter, nl: "AUC"}                            ║
        ╚═══════════════════════════════════════════════════════════════╝
                                          │
                                          ▼
        ╔═══════════════════════════════════════════════════════════════╗
        ║ STAGE 2 — PER-FIELD TRANSLATION                                ║
        ║ closed-set fields are grounded against CSV/enum/boolean sets; ║
        ║ open-set fields are emitted as direct constraints             ║
        ║                                                               ║
        ║   CSV/enum field → exact → fuzzy → enriched pool → LLM select ║
        ║      "sunitinib" ──lookup drugs.csv──▶                        ║
        ║                    MATCH drugsFuzzy = ["Sunitinib*"]          ║
        ║      "human"     ──lookup species.csv──▶                      ║
        ║                    MATCH species = "Human"                    ║
        ╚═══════════════════════════════════════════════════════════════╝
                                          │
                                          ▼
        ╔═══════════════════════════════════════════════════════════════╗
        ║ STAGE 3 — AGGREGATION + EXECUTION                              ║
        ║ valid subqueries → final API query → countTotal               ║
        ║   • combine into the boolean tree (AND across fields)         ║
        ║   • preserve per-field OR/AND/NOT                             ║
        ║   • route PK filters into the top-level query                 ║
        ║   • add facets / displayColumns                               ║
        ║   • apply service invariants (PK concomitants, etc.)          ║
        ║   • optionally probe open-set filters for confirmed zeroes    ║
        ╚═══════════════════════════════════════════════════════════════╝
```

## Why these stages

Stage -1 expansion clarifies abbreviations before entity recognition and
decomposition. Stage 0 TERMite annotates the expanded query with preferred labels
and entity types. Stage 1 uses those annotations while decomposing the query into
single-field fragments. The remaining stages translate, aggregate, validate, and
execute the count request.

| Stage | Responsibility | Why separate |
|-------|---------------|--------------|
| **0. TERMite enhancement** | Run NER over the expanded query; annotate entities, preferred labels, and entity types. | Gives Stage 1 and Stage 2 high-confidence entity hints without letting NER emit machine-query values directly. |
| **1. Decomposition** | Split the enhanced NL query into one NL fragment per field; route each fragment to a field. | Isolates "what is the user asking about?" from "how do I express it?". Small, cheap, testable. |
| **2. Translation** | Translate closed-set fields against CSV, enum, or boolean values; emit open-set fields as direct `MATCH` or `REGEX` constraints. | Grounded values are validated before aggregation, and open-set filters can be guarded by optional zero-count probes. |
| **3. Aggregation and execution** | Assemble valid subqueries into the final API query, apply service invariants, and execute for `countTotal` when requested. | The API payload is deterministic, typed, and auditable. |

[execute.py](../../src/oppp/execute.py) reads `countTotal` and does not fetch full
datapoint rows. Open-set filters are emitted as direct `MATCH`/`REGEX`
constraints, with an optional server-side zero-count probe before final
aggregation in live runs.

## Design principles

1. **Ground, don't generate.** Closed-set filter values come from an input
  CSV/enum/boolean set before the API call. Open-set filters keep their direct
  API constraint form and can be checked with isolated zero-count probes.
2. **One field, one translator.** Every field has an isolated, testable unit.
   The same closed-set translator handles exact search, fuzzy search, LLM pool
   enrichment, and LLM selection from a known entity set.
3. **Make boolean structure explicit.** Per-field booleans in Stage 2; cross-field
   booleans in Stage 3. Never implicit in prose.
4. **Hierarchy is a first-class operation.** Class→members, category→terms,
   parent→children expansion is a documented step, not a hope.
5. **Expansion and enhancement are separate.** Stage -1 rewrites only for
   readability and abbreviation expansion. Stage 0 always contributes TERMite
   entity annotations and preferred labels over the expanded query.
   Neither stage may emit machine-query values on its own; TERMite labels seed
   later routing and translation only.

## Service configuration

The pipeline targets the PK service on the PharmaPendium API. The service
configuration object defines:

- the **field set** (which fields exist),
- the **field→bucket map** (closed-set, open-set, enum, boolean),
- the **facet allow-list**,
- the **service invariants** applied in Stage 3 (`concomitants`, `tissueSpecific`, `metabolitesEnantiomers` defaults).

The stage code is independent of the configuration object.

## Settled field behavior

- Drug-class phrases prefer a valid drug-class translation when the drug closed
  set contains that class.
- Species classes use the available [species.csv](../../inputs/species.csv)
  hierarchy: an exact class label resolves server-side; colloquial groups without
  an exact class label (e.g. "Monkeys") expand to their member species.
- TERMite labels seed the translation pool; CSVs and inline closed sets remain
  the authority for what closed-set values may be emitted.
- Decomposition emits one component per concept, tagged with the same field and
  a shared boolean group when several concepts belong to one field.
