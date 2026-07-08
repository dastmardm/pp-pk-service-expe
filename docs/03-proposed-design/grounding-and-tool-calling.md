# Grounding & tool calling

This is the mechanism that turns "trust the LLM" into "verify against a closed
set". It applies to input closed-set fields described in
[../02-domain-inputs/field-taxonomy.md](../02-domain-inputs/field-taxonomy.md).

## The core move

The translator never accepts a raw generated value for a closed-set filter. For
input closed-set fields, each taxonomy CSV is exposed as a **lookup tool**. The
model may help build search phrases or select from candidates; the tool decides
*what legal values exist*.

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

The emitted value is therefore guaranteed to exist in the relevant closed set.

## One tool per input taxonomy

| Tool | Backing CSV | Returns |
|------|-------------|---------|
| `lookup_drugs` | [drugs.csv](../../inputs/drugs.csv) | matching drugs/classes + `parent_name` (class) |
| `lookup_species` | [species.csv](../../inputs/species.csv) | species + class, with class→members expansion |
| `lookup_route` | [route.csv](../../inputs/route.csv) | matching routes |
| `lookup_sources` | [sources.csv](../../inputs/sources.csv) | sources + FDA/EMA parent |

Inline enum and boolean fields (`sex`, `concomitants`, `tissueSpecific`,
`metabolitesEnantiomers`, `isPreclinical`, `documentYear`) do not need a lookup
tool because their complete value set is small enough to inline directly in the
translator prompt. Stage 2 selects from that inline closed set and validates
membership before emitting a value.

A uniform tool signature keeps Stage 2 simple:

```
lookup_<field>(
  query: str,            # the NL fragment / preferred label to resolve
  match: "exact"|"fuzzy" = "fuzzy",
  expand: "none"|"children"|"parent" = "none",
  limit: int = 25
) -> [ { name, id, parent_id, parent_name, count? } ]
```

Each returned candidate is recorded as a `GroundingHit` with the following
fields:

| Field | Meaning |
|-------|---------|
| `name` | The exact closed-set value that may be emitted. Required. |
| `id` | Closed-set row id when the source has one. Optional for runtime values. |
| `parent_id` | Parent row id for hierarchical input taxonomies. Optional. |
| `parent_name` | Parent label for hierarchical input taxonomies. Optional. |
| `score` | Confidence or match score on a 0-100 scale before conversion to the trace confidence. |
| `match` | Provenance: `exact`, `fuzzy`, `termite`, `class`, `expand`, `llm`, `runtime`, or `unmatched`. |
| `count` | Corpus count when present in the input CSV. Optional. |

The `grounding` block on a translated filter stores
`matched: GroundingHit[]`, optional `expanded_from` (`class`, `family`,
`runtime`, or `llm`), and a 0-1 `confidence`. Runtime closed-set hits use
`match="runtime"` and omit taxonomy ids unless fetched rows provide stable ids.

## Resolution order

The same order applies to every input closed set.

1. **Build the pool.** Start with the normalized Stage-1 fragment. For
   closed-set fields, add the Stage-0 TERMite preferred labels and synonyms that
   were annotated onto this fragment.
2. **Exact search.** Compare every pool item to every closed-set entity using
   case-insensitive exact matching. If exact matches are found, return those
   closed-set entities.
3. **Fuzzy search.** If exact search is empty, run fuzzy search from every pool
   item into the closed set. Rank by string similarity, corpus `count` where
   present, and hierarchy signals.
4. **Pool enrichment.** If fuzzy search is also empty, ask the LLM for more pool
   items: synonyms, abbreviations, brand names, scientific names, spelling
   variants, or likely class/member names. Restart exact search and fuzzy search
   with the enriched pool.
5. **Closed-set LLM selection.** If the enriched pool still returns no matches,
   pass the pool and the closed-set entities to the LLM and ask it to select the
   matching rows using exact closed-set spellings. This handles cases where the
   right row exists but string matching cannot bridge the wording.
6. **Membership assertion and retry.** Every LLM-selected candidate is checked
   against the closed set. Out-of-set candidates are rejected, and the LLM gets
   one retry with explicit feedback to choose exactly from the provided items.
   Candidates that still fail membership validation are dropped.
7. **Invalid translation.** If the selected list is `[]` or `None`, translation
   fails. Input closed-set failures are excluded from the API query.

The emitted closed-set value is therefore always a subset of the closed set. A
raw phrase that cannot be grounded is never emitted as a closed-set `MATCH`,
because it would silently zero an `AND` query.

### Open-set filter probes

Open-set fields (`parameter`, `parameterDisplay`, `studyGroup`, `age`, `dose`,
`duration`) have no complete input value list. The translator emits them as
direct `MATCH` or `REGEX` constraints. Live runs can probe each open-set filter
in isolation; a confirmed zero-count open filter is dropped with a warning, and
probe errors keep the filter.

## Hierarchy expansion (the rollup engine)

The hierarchical CSVs (`name,id,parent_id,parent_name`) let us answer the gold
set's class/rollup questions correctly:

- **Down (class → label or controlled members):** an exact class term emits the
  **class label** as a single value. The API resolves the label server-side to its
  whole subtree (verified: `species="Rodent"` and `species=[14 members]` both
  return the same count; `drugsFuzzy="Kinase inhibitors"` resolves the
  antineoplastic class). Large classes are not inlined because they would exceed
  the API's practical `MATCH`-list cap. For colloquial species groups with no
  exact class label, such as "Monkeys", lookup emits the matching member species
  rather than broadening to the full parent class. The expanded children are kept
  in the `grounding` record for provenance. A specific leaf (`Mouse`, `Rat`) is
  never widened.

Expansion is implemented once, over the generic `parent_id` structure, and reused
by every hierarchical lookup tool.

## Division of labour: TERMite vs CSV lookup

| Concern | Owner |
|---------|-------|
| Segment the full NL query into per-field fragments | Stage 1 |
| Recognise entities in the decomposed per-field fragments, give text/name + type | **TERMite** (Stage 0, after Stage 1) |
| Map entity type → field (refine Stage 1 routing via annotation reconciliation) | Stage 1 post-annotation pass |
| Confirm the label exists in the vocabulary; expand class/rollup; pick `id` | **CSV lookup tool** |
| Decide operator & boolean shape | Stage 2 |

TERMite is great at *finding* entities in focused text; operating on decomposed
fragments (rather than the raw query) reduces type ambiguity and produces
higher-confidence annotations. The CSVs remain authoritative about *what is
legal* and *how things nest*. Using both keeps entity recognition separate from
closed-set validation.

## Why not just put the CSV in the prompt?

`drugs.csv` is 5,227 rows and `species.csv` is 286 — too large to inline reliably,
and inlining still wouldn't enforce that the model picks a real value. Tool
calling keeps the prompt small, makes grounding *enforced* rather than
*encouraged*, and yields the auditable `grounding` block described in
[stage-2-subquery-translation.md](stage-2-subquery-translation.md).

## Implementation note

The implemented lookup layer is an in-memory CSV index in
[taxonomy/index.py](../../src/oppp/taxonomy/index.py). It loads each taxonomy with
the standard `csv` module, keeps lower-cased name and parent-child maps, and uses
RapidFuzz for fuzzy lookup. For large closed sets, the LLM closed-set fallback is
given a focused candidate window rather than every row; every LLM proposal is
re-grounded against the CSV before it can be emitted.

CSV and inline closed sets remain the authority for emitted closed-set values.
TERMite is required for Stage 0 entity annotations, while the LLM supplies
structured expansion and closed-set selection. Neither service may emit an
unverified closed-set value directly into the machine query.
