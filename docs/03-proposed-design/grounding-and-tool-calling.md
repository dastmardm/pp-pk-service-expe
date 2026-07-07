# Grounding & tool calling

This is the mechanism that turns "trust the LLM" into "verify against a closed
set". It applies to input closed-set fields now, and to runtime closed sets once
row fetching supplies the fetched datapoint values described in
[../02-domain-inputs/field-taxonomy.md](../02-domain-inputs/field-taxonomy.md).

## The core move

The translator never accepts a raw generated value for a closed-set filter. For
input closed-set fields, each taxonomy CSV is exposed as a **lookup tool**. For
runtime closed-set fields, the unique values from fetched datapoints become the
lookup list. The model may help build search phrases or select from candidates;
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

The emitted value is therefore guaranteed to exist in the relevant closed set.

## One tool per input taxonomy

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

The same order applies to an input CSV and to a runtime list of fetched values.
The only difference is the source of the closed set.

1. **Build the pool.** Start with the normalized Stage-1 fragment. For input
   closed-set fields, add corresponding Stage-0 TERMite preferred labels and
   synonyms. For runtime closed-set fields, add LLM-generated synonyms only as
   pool items, not as accepted values.
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
   against the closed set. Out-of-set candidates are rejected, and the LLM is
   retried with explicit feedback to choose exactly from the provided items.
   Candidates that still fail membership validation are dropped.
7. **Invalid translation.** If the selected list is `[]` or `None`, translation
   fails. Input closed-set failures are excluded from the API query; runtime
   closed-set failures do not post-filter the fetched datapoints.

The emitted value is therefore always a subset of the closed set. A raw phrase
that cannot be grounded is never emitted as a hard `MATCH`, because it would
silently zero an `AND` query or remove every datapoint in post-filtering.

### Runtime closed sets for open-set fields

Open-set fields such as `parameterComment`, `studyGroup`, `dose`, `ages`, PK
`parameterDisplay`, and RTB `model` have no complete value list before the first
API call. The pipeline therefore defers them:

1. Translate and aggregate all valid input closed-set filters.
2. Execute the API query and fetch datapoints.
3. For each deferred open-set field, collect the unique values present in those
   datapoints.
4. Run the closed-set translator over that runtime list.
5. Keep only datapoints whose field value is in the returned subset.

Entity-routed open-set fields, such as `targets` when no local `targets.csv` is
available, follow the same rule when their values are present in the fetched
datapoints or linked result entities: the post-filter may only keep values from
the fetched runtime set.

The v0.1 code does not fetch rows. Its implemented guard for open-set fields is
server-side count probing: open fields are translated as direct `MATCH` or
`REGEX` constraints, and live runs may probe each one in isolation. A confirmed
zero-count open filter is dropped with a warning; probe errors keep the filter.
Entity-routed open fields such as `targets` are skipped by this probe because the
API rejects entity-filter-only requests.

## Hierarchy expansion (the rollup engine)

The hierarchical CSVs (`name,id,parent_id,parent_name`) let us answer the gold
set's class/rollup questions correctly:

- **Down (class → label or controlled members):** an exact class term emits the
  **class label** as a single value. The API resolves the label server-side to its
  whole subtree (verified: `species="Rodent"` and `species=[14 members]` both
  return the same count; `drugsFuzzy="Kinase inhibitors"` resolves the
  antineoplastic class). We do **not** inline large classes: monoclonal antibodies
  has 100+ members, which exceeds the API's practical `MATCH`-list cap. For
  colloquial species groups with no exact class label, such as "Monkeys", lookup
  emits the matching member species rather than broadening to the full parent
  class. The expanded children are kept in the `grounding` record for provenance.
  A specific leaf (`Mouse`, `Rat`) is never widened.
- **Up (term → category), additive + score-gated:** a leaf rolls up to its MedDRA
  family, but **(a)** the rollup is *additive* — the canonical/grounded term stays
  in the value set so the broad term is never lost (`Mutagenicity` survives rather
  than being replaced by its narrow NEC siblings), and **(b)** a rollup only fires on
  a *high-confidence anchor* (exact, or fuzzy ≥95). A weak fuzzy match (`positive
  Ames Test` ranks `Amniotic membrane rupture test positive` @86 on shared words)
  must not anchor a family — it would expand an unrelated set. Result/polarity words
  (`positive`, `negative`, `abnormal`, …) are stripped before grounding so an
  assay-result phrase keys on the assay name (`positive Ames Test` → `Ames Test` →
  the Ames assay family), since the vocabulary names the *assay/finding*, not its
  polarity.
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

The implemented lookup layer is an in-memory CSV index in
[taxonomy/index.py](../../src/oppp/taxonomy/index.py). It loads each taxonomy with
the standard `csv` module, keeps lower-cased name and parent-child maps, and uses
RapidFuzz for fuzzy lookup. For large closed sets, the LLM closed-set fallback is
given a focused candidate window rather than every row; every LLM proposal is
re-grounded against the CSV before it can be emitted.

CSV and runtime closed sets remain the authority for emitted values. TERMite is
required for Stage 0 entity annotations, while the LLM supplies structured
expansion and closed-set selection. Neither service may emit an unverified value
directly into the machine query.
