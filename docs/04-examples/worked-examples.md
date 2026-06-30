# Worked examples (end-to-end)

Each trace runs an SME gold-set question through the core decomposition,
translation, and aggregation stages. Stage -1 expansion and Stage 0 enhancement
are omitted where they do not change the example. Values match
the expected per-field mappings in
[inputs/sme_expected_cases.csv](../../inputs/sme_expected_cases.csv). Effect/
species expansions are abbreviated with `…`.

Examples that mention runtime closed-set post-filtering show the row-level design
path. In v0.1, open-set fields are emitted as direct `MATCH`/`REGEX` constraints
and may be guarded by zero-count probes during live execution.

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

Shows input closed-set fields (toxicityParameter, drugs, species) next to a
runtime closed-set field (`parameterComment`).

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

**Stage 2A - input closed-set translation**

| field | bucket | machine subquery |
|-------|--------|------------------|
| toxicityParameter | input closed set | `MATCH toxicityParameter = "NOAEL"` (verified in toxicity_parameters.csv) |
| drugs | input closed set | `MATCH drugsFuzzy = ["Sunitinib*"]` |
| species | input closed set | `MATCH species = "Rat"` |
| parameterComment | runtime closed set | deferred until datapoints are fetched |

**Stage 3 - closed-filter query**

```json
{
  "query": {
    "AND": [
      { "MATCH": { "field": "drugsFuzzy", "value": ["Sunitinib*"] } },
      { "MATCH": { "field": "toxicityParameter", "value": "NOAEL" } },
      { "MATCH": { "field": "species", "value": "Rat" } }
    ]
  }
}
```

**Stage 2B - runtime closed-set post-filter**

After the API returns datapoints, collect the unique `parameterComment` values
from those datapoints and translate `"maternal toxicity"` against that runtime
closed set. If the translator selects `["Maternal toxicity"]`, Stage 3 keeps only
datapoints whose `parameterComment` value is `Maternal toxicity`. If it returns
`[]` or `None`, the comment filter is invalid and no post-filter is applied.

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

Shows runtime closed-set fields needing synonym selection plus **service
invariants**.

**Stage 2** highlights:

| field | bucket | machine subquery |
|-------|--------|------------------|
| drugs | input closed set | `MATCH drugsFuzzy = "Cabozantinib*"` |
| species | input closed set | `MATCH species = "Human"` |
| route | input closed set | `MATCH route = "Oral"` |
| parameter | runtime closed set | selected from fetched `parameter` values, e.g. `["Cmax"]` |
| studyGroup | runtime closed set | selected from fetched `studyGroup` values matching hepatic impairment synonyms |
| age | runtime closed set | selected from fetched `age` values, e.g. `["Adult"]` |

**Stage 3** injects the PK **invariants** automatically into the closed-filter
query:
`metabolitesEnantiomers = "Not metabolites/enantiomers"`, `tissueSpecific =
"Not tissue-specific"`, and the `concomitants` Fasted-or-empty OR block — none of
which the user said, but all of which the PK service always requires. After
fetching datapoints, the runtime closed-set translator selects the `parameter`,
`studyGroup`, and `age` post-filter values from the fetched rows.
