# Grounding & tool calling

This is the mechanism that turns "trust the LLM" into "verify against the CSV".
It applies to **closed-vocabulary fields** (Set A in
[../02-domain-inputs/field-taxonomy.md](../02-domain-inputs/field-taxonomy.md)).

## The core move

The legacy system lets the model write any string into a field value. The
redesign instead exposes each taxonomy CSV as a **lookup tool** and requires the
closed-vocab value to be the tool's output. The model chooses *what to look up*;
the tool decides *what legal values exist*.

```
LLM (Stage 2):  "I need a species value for the fragment 'monkeys'"
        │  tool call
        ▼
lookup_species(query="monkeys", expand="children")
        │  reads species.csv
        ▼
returns: [
  {name:"African green monkey", id:"dcylsezyXgH", parent_name:"Primate"},
  {name:"Cynomolgus monkey",    id:"...",         parent_name:"Primate"},
  ... all monkey species ...
]
        │
        ▼
LLM emits:  MATCH species = [those preferred labels]
```

The emitted value is therefore guaranteed to exist in the vocabulary.

## One tool per closed-vocab taxonomy

| Tool | Backing CSV | Returns |
|------|-------------|---------|
| `lookup_drugs` | [drugs.csv](../../inputs/drugs.csv) | matching drugs/classes + `parent_name` (class) |
| `lookup_effects` | [effects.csv](../../inputs/effects.csv) | matching effects + parent category, with rollup |
| `lookup_indications` | [indications.csv](../../inputs/indications.csv) | matching indications |
| `lookup_species` | [species.csv](../../inputs/species.csv) | species + class, with class→members expansion |
| `lookup_route` | [route.csv](../../inputs/route.csv) | matching routes |
| `lookup_sources` | [sources.csv](../../inputs/sources.csv) | sources + FDA/EMA parent |
| `lookup_toxicity_parameter` | [toxicity_parameters.csv](../../inputs/toxicity_parameters.csv) | parameters + category |
| `lookup_dose_type` | [dose_type.csv](../../inputs/dose_type.csv) | dose-type enum |

A uniform tool signature keeps Stage 2 simple:

```
lookup_<field>(
  query: str,            # the NL fragment / preferred label to resolve
  match: "exact"|"fuzzy" = "fuzzy",
  expand: "none"|"children"|"parent" = "none",
  limit: int = 25
) -> [ { name, id, parent_id, parent_name, count? } ]
```

## Resolution order (recall vs precision)

1. **TERMite preferred label** — if the fragment came from a TERMite annotation,
   its preferred label is usually already a taxonomy term; verify it exists in the
   CSV and use it. Highest precision.
2. **Exact name match** (case-insensitive) in the CSV.
3. **Fuzzy / synonym / wildcard** match; rank by closeness and, where present, by
   the corpus `count` column (more frequent → more likely intended). This is also
   where misspellings are reconciled — the pluggable normalizer feeds candidates
   here (see [misspelling-strategy.md](misspelling-strategy.md)).
4. **No match** → return empty; Stage 2 flags the constraint rather than inventing
   a value.

## Hierarchy expansion (the rollup engine)

The hierarchical CSVs (`name,id,parent_id,parent_name`) let us answer the gold
set's class/rollup questions correctly:

- **Down (class → members):** find the node whose `name` is the class, then select
  all rows whose `parent_id` chains to it. Drug classes (Q8, Q23, Q24), species
  classes (Q23 "Monkeys", Q6 rodents), effect categories.
- **Up (term → category):** follow `parent_id` to the SOC/category for MedDRA-style
  effect rollups.
- **Curated sets:** "preclinical / non-clinical species" (Q7, Q16) is a named set
  the back-end already defines; expose it as a special `expand="preclinical"` mode
  or a small curated list, since it doesn't correspond to a single taxonomy node.

Expansion is implemented once, over the generic `parent_id` structure, and reused
by every hierarchical lookup tool.

## Division of labour: TERMite vs CSV lookup

| Concern | Owner |
|---------|-------|
| Recognise entities in raw text, give preferred label + type | **TERMite** (unchanged) |
| Map entity type → field | Stage 1 |
| Confirm the label exists in the vocabulary; expand class/rollup; pick `id` | **CSV lookup tool** |
| Decide operator & boolean shape | Stage 2 |

TERMite is great at *finding* entities in messy text; the CSVs are authoritative
about *what is legal* and *how things nest*. Using both removes the legacy single
point of failure.

## Why not just put the CSV in the prompt?

`effects.csv` alone is 12,724 rows and `drugs.csv` is 5,227 — far too large to
inline, and inlining still wouldn't enforce that the model picks a real value.
Tool calling keeps the prompt small, makes grounding *enforced* rather than
*encouraged*, and yields the auditable `grounding` block described in
[stage-2-subquery-translation.md](stage-2-subquery-translation.md).

## Implementation note

The lookups are simple in-memory operations over small/medium tables. A first
implementation can load each CSV into a pandas/dict index at startup; exact and
prefix matching cover most cases, with a fuzzy matcher (e.g. token-set ratio) and
optional embedding search for hard synonym cases. No external service is required
beyond the existing TERMite and LLM clients
([utils/client/](../../utils/client/), [utils/termite/](../../utils/termite/)).
