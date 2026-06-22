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
   CSV and use it. Highest precision. The annotation must **correspond to this
   component's fragment**, not merely share the field type — otherwise a multi-value
   field (`rats or mice`, `neutropenia or thrombocytopenia`) would bind every value
   to the *first* same-typed annotation, silently duplicating one and dropping the
   rest. Correspondence uses two signals: **textual overlap** of surface/label with
   the fragment, OR **no grounding conflict** — the annotation still binds when the
   surfaces differ (e.g. fragment `No Observed Adverse Effect Level` vs label
   `NOAEL`, an abbreviation TERMite normalised) *unless* the fragment itself strongly
   self-grounds (exact/high-fuzzy) to a **different** vocab entry. That conflict is
   exactly the multi-value case (`Rat` self-grounds to `Rat` while the lone
   annotation is `Mouse`), so the annotation is rejected and the fragment grounds
   itself. When no annotation corresponds, fall through to fragment-based grounding.
2. **Exact name match** (case-insensitive) in the CSV.
3. **Fuzzy / synonym / wildcard** match; rank by closeness and, where present, by
   the corpus `count` column (more frequent → more likely intended). This is also
   where misspellings are reconciled — the pluggable normalizer feeds candidates
   here (see [misspelling-strategy.md](misspelling-strategy.md)).
4. **LLM map → re-ground** *(when exact + fuzzy return an empty candidate pool)* —
   the fragment is a synonym, scientific name, brand name, or abbreviation the
   string matcher cannot reach (e.g. `homo sapiens` for `species`, whose preferred
   label is `Human`; `per os` → `Oral`; `Columvi` → `Glofitamab`;
   `IV administration` → `intravenous`). The LLM is asked for the canonical
   vocabulary term(s) the phrase refers to, and **each proposal is then looked up
   again against the CSV** (steps 2–3) so the emitted value is always a real
   taxonomy entry — never the model's raw string. This keeps **ground, don't
   generate** intact even when the model is doing the mapping. The mapping call is
   non-deterministic in practice even at temperature 0 (e.g. `IV administration`
   resolves only ~half the calls), so it is **retried and unioned over a few
   attempts** — a single empty response must not silently drop the constraint to
   confidence 0. Runs only on the production (LLM-enabled) lookup path; the offline
   deterministic double skips it.
5. **No match** → the constraint is **dropped** (marked `dropped`, confidence 0)
   rather than inventing a value. Reached only when even the LLM's proposal fails to
   ground across attempts (or offline, when no LLM is available). Emitting the raw
   out-of-vocabulary phrase as a hard `MATCH` would silently **zero the whole query**
   (an `AND` with a value that exists in no record), so Stage 3 excludes a dropped
   constraint from the boolean tree, entity routing, and the budget alike, recording
   a warning so the gap is visible. The query then returns the valid superset, not 0.
   This is **ground, don't generate** taken to its conclusion: a closed-vocab field
   never carries a value the vocabulary doesn't contain — not even as a last resort.

### Entity-routed open fields (e.g. `targets`)

`targets` has no taxonomy CSV (it is an *open* field routed through the
`DrugsTargets` entity filter), but the back-end still matches it against the
enhancer's **preferred label**, not a free phrase: the filter accepts `Kinases`
(the TERMite label) and returns nothing for the raw `inhibitors of kinases`. So
for an entity-routed open field, when a TERMite annotation of the matching type is
present, Stage 2 emits its label — the same "use the enhancer's preferred label"
principle as step 1 above, applied where there is no CSV to verify against. With no
annotation, the fragment passes through unchanged.

For a **plain free-text field** (e.g. `parameterComment`) there is no vocabulary at
all — the value is searched as a substring of the record's comment text. The
decomposer copies the user's surface words, so the fragment can carry the query's
relational glue (`...NOAEL related to maternal toxicity` → fragment `related to
maternal toxicity`). The API matches the *substantive* phrase, so Stage 2 strips a
leading relational connective (`related to`, `associated with`, `due to`, `for`,
`of`, `in`, …) before emitting (`related to maternal toxicity` → `maternal
toxicity`). This is general over open free-text fields, not tied to any one comment.

#### Server-side zero-count probe (open-set safety net)

A closed-vocab field is validated against its CSV *before* it is ever emitted, so a
bad value is caught locally. An open-set field has no such check — a mis-routed or
glue-laden phrase can carry a value that exists in **no record** and silently zeroes
the whole `AND`, and we cannot know that offline. So at Stage 3 (live paths only) we
**ask the API**: each open-set filter is probed **in isolation** with one cheap
server-side `countTotal` (`drop_empty_open_filters`, never fetching rows), and a
filter whose count is confirmed **0** is dropped — it matches nothing in the corpus,
so it cannot legitimately constrain anything. Design choices: probe the filter
**alone** (not ANDed with the rest), so only a genuinely-invalid value is dropped,
never a valid value that is merely empty in combination; on any probe error/timeout
**keep** the filter (fail open). Entity-routed fields (`targets`/`indications` via
`entityFilters`) are skipped — the API rejects an `entityFilters`-only query, so they
can't be probed alone and fall through to keep. This is the open-field analogue of the
CSV check: ground or drop, never let an in-no-record value zero the query.

## Hierarchy expansion (the rollup engine)

The hierarchical CSVs (`name,id,parent_id,parent_name`) let us answer the gold
set's class/rollup questions correctly:

- **Down (class → label, not inlined members):** a class term emits the **class
  label** as a single value. The API resolves the label server-side to its whole
  subtree (verified: `species="Rodent"` and `species=[14 members]` both return the
  same count; `drugsFuzzy="Kinase inhibitors"` resolves the antineoplastic class).
  We do **not** inline every child: a large class (monoclonal antibodies has 100+
  members) busts the API's ~49-value-per-`MATCH`-list cap (HTTP 400), and inlining
  is redundant since the parent already matches its subtree. The expanded children
  are kept in the `grounding` record for provenance only. A class is recognised by
  being a `parent_name` (incl. via singular forms, `Monkeys`→`Monkey`), **or** — for
  a colloquial group with no own node — by its (singularised) word appearing as a
  standalone term in ≥2 entries that **all share one parent**, which is then the
  class (`Monkeys` → `Primate`, the gold answer for Q23 monkeys; 14→27 records). A
  specific leaf (`Mouse`, `Rat`) is never widened — the single-parent guard and an
  exact-leaf check keep ambiguous/specific terms out.
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

The lookups are simple in-memory operations over small/medium tables. A first
implementation can load each CSV into a pandas/dict index at startup; exact and
prefix matching cover most cases, with a fuzzy matcher (e.g. token-set ratio) and
optional embedding search for hard synonym cases. No external service is required
beyond the existing TERMite and LLM clients
([utils/client/](../../utils/client/), [utils/termite/](../../utils/termite/)).
