# Stage 3 — Aggregation

**Input:** all per-field machine subqueries from Stage 2.
**Output:** one final machine query in the
[target format](../02-domain-inputs/machine-query-schema.md), ready to POST.

This stage is deterministic assembly + a small amount of rule application. It
should be mostly code, not LLM — the hard semantic work already happened.

## Steps

### 1. Group by boolean intent

- Subqueries that are plain filters combine under a top-level **`AND`** (the
  default: every field constrains the result). This is the cross-field boolean.
- Subqueries that share a Stage-1 `boolean_group` combine with that group's
  operator first, then join the rest. Examples from the gold set:
  - Q13 effects "neutropenia **or** thrombocytopenia" → an `OR` node of two
    expanded `effects` MATCHes, then AND-ed with `species=Human`.
  - Q14 effects "neutropenia **and** cytopenia" → an `AND` of two expanded
    `effects` MATCHes.
  - Q7 species "Human **AND** at least one preclinical species" → an `OR` over
    `species=Human` and `isPreclinical=true` (cross-field boolean), per the
    Safety "Human plus preclinical" rule.

### 2. Route to `entityFilters` where required

Some fields must be expressed via a linked entity rather than the top-level
`query`. Stage 3 moves them:

- Safety: `indications` → `DrugsIndications`; `targets` → `DrugsTargets`.
- `species`, `route`, `toxicityParameter` stay as **direct** top-level fields
  (per the Safety prompt's explicit instruction).
- PK adds `Species`, `Concomitants`, `PKParameters` entities.

A per-service routing table drives this.

### 3. Apply service invariants

Rules that are not derivable from the user's words but are always required by a
service. Carried over from the legacy prompts, now applied as deterministic
post-processing:

- **PK — concomitants.** Always pin to Fasted-or-empty:
  `{"OR":[{"MATCH":{"field":"concomitants","value":"Fasted"}},{"EMPTY":{"field":"concomitants"}}]}`.
- **PK — tissueSpecific.** Default `Not tissue-specific`; set `Tissue-specific`
  + a `parameterDisplay` REGEX when a non-plasma location is named.
- **PK — metabolitesEnantiomers.** Default `Not metabolites/enantiomers`; set
  `Metabolite` for named-metabolite queries.
- **PK — duration / steady-state, clearance & Vd parameter defaults, unit
  normalization** — see the PK rules block in
  [prompts.py](../../utils/ppendium/prompts.py).
- **Safety — species "Human" gating.** Only add `species=Human` on unambiguous
  human terms (patient, subject, man/woman, child); "study" alone is not enough.

These should live in a per-service **invariants module**, unit-tested in
isolation.

### 4. Attach output options

- **`facets`** — when the question asks "which / what are the / list of /
  categories", add the relevant allow-listed facet(s). Allow-lists per service
  (Safety: `drugs, species, sources, effects, route, doseType, documentYear`).
  Fields whose Stage-1 `type` is `question` map to facets / display columns here.
- **`displayColumns`** — only when the user explicitly asks for specific output
  columns (e.g. "at which dose, regimen and route" → `["drug","dose","doseType",
  "route"]`). Otherwise omit. Names come from [fields.csv](../../inputs/fields.csv).
- **`sortColumns`**, **`leafOnly`** as needed.

### 5. Validate before returning

Because every piece is structured, Stage 3 can **validate** rather than hope:

- exactly one top-level constraint in `query`;
- all constraint types upper-case and well-formed;
- every `field` exists in [query_criteria_fields.csv](../../inputs/query_criteria_fields.csv)
  / [fields.csv](../../inputs/fields.csv);
- facet fields are within the service allow-list;
- closed-vocab values exist in their CSV (final grounding check);
- `OR`/`AND` have ≥2 children, `NOT` exactly 1.

A validation failure is a *bug we can catch here*, not a silent bad query — a
strict improvement over the legacy regex-scrape of free-text JSON.

## Output surface per service

- **Safety / PK** → the JSON envelope.
- **RTB / CrossFire** → a `where_clause` string (`DAT.VTYPE='AUC' AND
  DAT.BSPECIE='rat' AND …`) plus `instructions`. Same filter set, different
  serializer. Stage 3 picks the serializer from service config.

## Example assembly

Stage 2 produced (for Q13):

```
A: MATCH species = "Human"
B: MATCH effects = [neutropenia terms...]     boolean_group: g1/OR
C: MATCH effects = [thrombocytopenia terms...] boolean_group: g1/OR
questions: dose, doseType, route   (type: question → displayColumns)
```

Stage 3 assembles:

```json
{
  "query": {
    "AND": [
      { "MATCH": { "field": "species", "value": "Human" } },
      { "OR": [
        { "MATCH": { "field": "effects", "value": ["Neutropenia", "Granulocytopenia", "..."] } },
        { "MATCH": { "field": "effects", "value": ["Thrombocytopenia", "Immune thrombocytopenia", "..."] } }
      ]}
    ]
  },
  "displayColumns": ["drug", "dose", "doseType", "route"]
}
```
