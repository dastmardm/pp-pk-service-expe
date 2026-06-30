# Pain points (why we redesign)

These are not hypothetical. Every failure below is documented in the
`mapping_comment` column of the SME gold set
([inputs/sme_expected_cases.csv](../../inputs/sme_expected_cases.csv)), where
subject-matter experts recorded where the current "PP AI" translator went wrong.

## 1. No grounding → wrong or invented values

The model emits field values from its own head with no check against the
taxonomy CSVs.

- **Drug class not matched to the taxonomy node.** Q24 "ADRs of ADC…": the model
  used `ADC` but the PharmaPendium drug hierarchy node is
  `Antibody-Drug Conjugate (ADC)`. Q23 used `monoclonal antibody` instead of the
  hierarchy term `Monoclonal antibodies`.
- **Class mistaken for a different field.** Q8 "inhibitors of kinases" and Q21
  "CDk4 inhibitors": *kinase* was annotated as a **target** when the user meant a
  **drug class**. Q21 also shows a label mismatch — `Cyclin-dependent kinase 4`
  vs the real PP target term `Cyclin-dependent kinase 4 (CDK4)`.
- **Brand names.** Q25 "Columvi" had to resolve to `Glofitamab`.

A CSV-grounded lookup (with hierarchy and synonyms) fixes all of these, because
the value is *selected from* the taxonomy rather than *generated*.

## 2. Hierarchy / rollups are mishandled

The taxonomy CSVs are hierarchical (`parent_id`, `parent_name`), but a flat
prompt can't reliably reason over them.

- **Species classes.** Q6 "rats or mice" was answered with `Rodent`, which is
  *broader* than rat+mouse. Q23 "Monkeys" should expand to all monkey species
  (African green monkey, Cynomolgus monkey, Rhesus monkey, …). Q7/Q16
  "preclinical / non-clinical species" needs the curated preclinical species
  set.
- **Effects (MedDRA rollups).** Repeatedly flagged "MedDRA rules are not yet
  implemented." "Neutropenia" must expand to all its preferred terms
  (Agranulocytosis, Febrile neutropenia, Granulocytopenia, …); "liver disorders"
  → the `Hepatic and hepatobiliary disorders NEC` subtree; "cardiac disorders"
  → the SOC-level rollup.

Expansion is a **per-field, taxonomy-aware** operation. It belongs next to the
CSV, not buried in one prose prompt.

## 3. One prompt, every rule → unmaintainable & untestable

[prompts.py](../../utils/ppendium/prompts.py) is ~1600 lines. A single Safety
prompt simultaneously governs drug-field selection, species logic, toxicity
parameters, routes, facets, display columns, unit handling, and JSON hygiene.

- You cannot change the species rule without risking the drug rule.
- You cannot unit-test "did we get `species` right?" in isolation.
- A regression in one field is invisible until the whole query is run.

## 4. Boolean intent across and within fields is fragile

The gold set distinguishes:

- **OR within a field** (Q13: neutropenia **or** thrombocytopenia),
- **AND within a field** (Q14: neutropenia **and** cytopenia),
- **Boolean across fields** (Q7: retrieve both Human and preclinical records,
  represented in the Safety query layer as Human **OR** `isPreclinical=true`).

A monolithic generator handles these inconsistently. Treating each field's
boolean shape explicitly in Stage 2, and the cross-field shape explicitly in
Stage 3, makes the logic auditable.

## 5. Fragile output parsing

The model returns free text and the code scrapes a JSON object out of it with
regex + brace matching (`extract_payload_req`, `_find_matching_brace`). Any
stray prose, trailing comma, or shorthand breaks the parse. Per-field tool
calling with typed/structured outputs removes most of this surface.

## Summary table

| # | Symptom | Root cause | Redesign answer |
|---|---------|------------|-----------------|
| 1 | Invented / mismatched values | No CSV grounding | Tool-calling lookup against taxonomy CSVs |
| 2 | Wrong breadth (too broad/narrow) | Hierarchy ignored | Per-field hierarchy expansion/rollup |
| 3 | Can't evolve or test safely | One giant prompt | One small translator per field |
| 4 | Boolean logic errors | Implicit in prose | Explicit per-field + aggregation stages |
| 5 | Parse failures | Free-text JSON scraping | Structured / tool-call outputs |
