# Worked examples (end-to-end)

Each trace runs an SME gold-set question through all three stages. Values match
the expected per-field mappings in
[inputs/sme_expected_cases.csv](../../inputs/sme_expected_cases.csv). Effect/
species expansions are abbreviated with `…`.

---

## Example A — Q1: "What are the ADRs of Sunitinib in human"

**Stage 1 — decomposition**

```json
[
  { "field": "drugs",   "nl_fragment": "Sunitinib", "type": "filter",   "reason": "The user restricts results to the drug sunitinib.", "source": "termite:DRUG" },
  { "field": "species", "nl_fragment": "human",     "type": "filter",   "reason": "The user restricts results to human studies.",     "source": "termite:SPECIES" },
  { "field": "effects", "nl_fragment": "ADRs",       "type": "question", "reason": "The user wants the adverse effects, answered over the retrieved records.", "source": "llm" }
]
```

**Stage 2 — per-field translation**

| field | bucket | action | machine subquery |
|-------|--------|--------|------------------|
| drugs | closed | `lookup_drugs("Sunitinib")` → Sunitinib (+ salt Sunitinib Malate); use fuzzy | `MATCH drugsFuzzy = ["Sunitinib*"]` |
| species | closed | `lookup_species("human")` → Human | `MATCH species = "Human"` |
| effects | question | no filter; the post-retrieval question, becomes a facet | *(facet: effects)* |

> SME note for Q1: "Sunitinib and Sunitinib Malate have to be selected" — the
> `Sunitinib*` fuzzy + drug-salt expansion captures both.

**Stage 3 — aggregation**

```json
{
  "query": {
    "AND": [
      { "MATCH": { "field": "drugsFuzzy", "value": ["Sunitinib*"] } },
      { "MATCH": { "field": "species", "value": "Human" } }
    ]
  },
  "facets": ["effects"]
}
```

---

## Example B — Q12: "What is the NOAEL for sunitinib in rats related to maternal toxicity"

Shows a **closed** field (toxicityParameter) next to an **open** field
(parameterComment).

**Stage 1**

```json
[
  { "field": "toxicityParameter", "nl_fragment": "NOAEL",             "type": "filter",   "reason": "The user restricts results to the NOAEL endpoint.",              "source": "termite:TOXICITY_PARAMETER" },
  { "field": "drugs",             "nl_fragment": "sunitinib",         "type": "filter",   "reason": "The user restricts results to the drug sunitinib.",              "source": "termite:DRUG" },
  { "field": "species",           "nl_fragment": "rats",              "type": "filter",   "reason": "The user restricts results to rat studies.",                     "source": "termite:SPECIES" },
  { "field": "parameterComment",  "nl_fragment": "maternal toxicity", "type": "filter",   "reason": "The user restricts results to the maternal-toxicity qualifier.", "source": "llm" },
  { "field": "value",             "nl_fragment": "what is the NOAEL", "type": "question", "reason": "The user wants the NOAEL value reported from the retrieved records.", "source": "llm" }
]
```

**Stage 2**

| field | bucket | machine subquery |
|-------|--------|------------------|
| toxicityParameter | closed | `MATCH toxicityParameter = "NOAEL"` (verified in toxicity_parameters.csv) |
| drugs | closed | `MATCH drugsFuzzy = ["Sunitinib*"]` |
| species | closed | `MATCH species = "Rat"` |
| parameterComment | **open** | `MATCH parameterComment = "Maternal toxicity"` (LLM decides; no CSV) |

**Stage 3**

```json
{
  "query": {
    "AND": [
      { "MATCH": { "field": "drugsFuzzy", "value": ["Sunitinib*"] } },
      { "MATCH": { "field": "toxicityParameter", "value": "NOAEL" } },
      { "MATCH": { "field": "species", "value": "Rat" } },
      { "MATCH": { "field": "parameterComment", "value": "Maternal toxicity" } }
    ]
  }
}
```

---

## Example C — Q23: "What are the monoclonal antibodies causing Nephritis in Monkeys?"

Shows **two hierarchy expansions** (drug class → class node; species class →
members) and an effect rollup.

**Stage 1**

```json
[
  { "field": "drugs",   "nl_fragment": "monoclonal antibodies", "type": "filter", "reason": "The user restricts results to the monoclonal-antibody drug class (a class, not a target).", "source": "llm" },
  { "field": "effects", "nl_fragment": "Nephritis",             "type": "filter", "reason": "The user restricts results to records reporting nephritis.",     "source": "termite:ADVERSE_EVENT" },
  { "field": "species", "nl_fragment": "Monkeys",               "type": "filter", "reason": "The user restricts results to monkey species (a class to expand to its members).", "source": "termite:SPECIES", "boolean_group": "expand-children" }
]
```

**Stage 2**

| field | action | machine subquery |
|-------|--------|------------------|
| drugs | `lookup_drugs("monoclonal antibodies", match=fuzzy)` → resolve to the class node `Monoclonal antibodies` (legacy bug: used `monoclonal antibody`) | `MATCH drugsFuzzy = ["Monoclonal antibodies"]` |
| species | `lookup_species("Monkeys", expand="children")` → all monkey species | `MATCH species = ["African green monkey","Cynomolgus monkey","Rhesus monkey", …]` |
| effects | `lookup_effects("Nephritis", expand="children")` → rollup | `MATCH effects = ["Nephritis","Lupus nephritis","Tubulointerstitial nephritis", …]` |

**Stage 3**

```json
{
  "query": {
    "AND": [
      { "MATCH": { "field": "drugsFuzzy", "value": ["Monoclonal antibodies"] } },
      { "MATCH": { "field": "effects",    "value": ["Nephritis", "Lupus nephritis", "Tubulointerstitial nephritis", "..."] } },
      { "MATCH": { "field": "species",    "value": ["African green monkey", "Cynomolgus monkey", "Rhesus monkey", "..."] } }
    ]
  },
  "facets": ["drugs"]
}
```

> This is exactly the case the legacy system got wrong (`mapping_comment`:
> "monoclonal antibody retrieved instead of monoclonal antibodies… species
> retrieval was monkey instead of all monkeys"). Grounded lookup + child
> expansion fixes both.

---

## Example D — Q13: "drugs causing neutropenia or thrombocytopenia in human, at which dose, dosing regimen and route?"

Shows **OR within a field** + **output fields → displayColumns**.

**Stage 1** (decompose to concepts, same field, shared OR group)

```json
[
  { "field": "effects", "nl_fragment": "neutropenia",      "type": "filter",   "reason": "The user restricts results to neutropenia (OR-joined with thrombocytopenia).",     "boolean_group": "g1/OR" },
  { "field": "effects", "nl_fragment": "thrombocytopenia", "type": "filter",   "reason": "The user restricts results to thrombocytopenia (OR-joined with neutropenia).",     "boolean_group": "g1/OR" },
  { "field": "species", "nl_fragment": "human",            "type": "filter",   "reason": "The user restricts results to human studies." },
  { "field": "dose",     "nl_fragment": "at which dose",   "type": "question", "reason": "The user wants the dose reported for each retrieved record." },
  { "field": "doseType", "nl_fragment": "dosing regimen",  "type": "question", "reason": "The user wants the dosing regimen reported for each retrieved record." },
  { "field": "route",    "nl_fragment": "route",           "type": "question", "reason": "The user wants the route reported for each retrieved record." }
]
```

**Stage 2** — each effect concept expanded independently against effects.csv;
species grounded to `Human`.

**Stage 3**

```json
{
  "query": {
    "AND": [
      { "MATCH": { "field": "species", "value": "Human" } },
      { "OR": [
        { "MATCH": { "field": "effects", "value": ["Neutropenia","Granulocytopenia","Febrile neutropenia","..."] } },
        { "MATCH": { "field": "effects", "value": ["Thrombocytopenia","Immune thrombocytopenia","..."] } }
      ]}
    ]
  },
  "displayColumns": ["drug", "dose", "doseType", "route"]
}
```

---

## Example E — PK: "Cmax of Cabozantinib in adults with hepatic impairment after oral administration"

Shows an **open** field needing synonym expansion + **service invariants**.

**Stage 2** highlights:

| field | bucket | machine subquery |
|-------|--------|------------------|
| drugs | closed | `MATCH drugsFuzzy = "Cabozantinib*"` |
| parameter | closed (PKParameters) | `MATCH parameter = "Cmax"` |
| species | closed | `MATCH species = "Human"` |
| route | closed | `MATCH route = "Oral"` |
| studyGroup | **open** | `REGEX studyGroup = ".*(cirrhosis|hepatic impairment|Child-Pugh B|Child-Pugh C|liver failure).*"` |
| ages | **open** | `REGEX age = "Adult"` |

**Stage 3** then injects the PK **invariants** automatically:
`metabolitesEnantiomers = "Not metabolites/enantiomers"`, `tissueSpecific =
"Not tissue-specific"`, and the `concomitants` Fasted-or-empty OR block — none of
which the user said, but all of which the PK service always requires.
