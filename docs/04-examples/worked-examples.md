# Worked examples (end-to-end)

Each trace runs an SME gold-set question through the core decomposition,
translation, and aggregation stages. Stage -1 expansion and Stage 0 enhancement
are omitted where they do not change the example. Values match
the gold queries in [PPPK.xlsx](../PPPK.xlsx) (`PK_Query` sheet).
Species expansions are abbreviated with `…`.

Open-set fields are emitted as direct `MATCH`/`REGEX` constraints and may be
guarded by zero-count probes during live execution.

---

## Example A — "What is the AUC of Sunitinib in human after oral administration?"

Shows a basic PK query with closed-set filtering and an open-set PK parameter.

**Stage 1 — decomposition**

```json
[
  { "field": "drugs",       "nl_fragment": "Sunitinib", "type": "filter",   "reason": "The user restricts results to the drug sunitinib.",           "source": "termite:DRUG" },
  { "field": "species",     "nl_fragment": "human",     "type": "filter",   "reason": "The user restricts results to human studies.",                "source": "termite:SPECIES" },
  { "field": "routes",      "nl_fragment": "oral",      "type": "filter",   "reason": "The user restricts results to oral administration.",           "source": "termite:ROUTE" },
  { "field": "parameter",   "nl_fragment": "AUC",       "type": "filter",   "reason": "The user restricts results to AUC PK records.",               "source": "termite:PARAMETER" },
  { "field": "value",       "nl_fragment": "what is AUC", "type": "question", "reason": "The user wants the AUC value reported from the retrieved records.", "source": "llm" }
]
```

> The JSON shows the post-reconciliation state: `parameter` is a `filter` because
> AUC names the kind of PK record sought, not just a reported output column.

**Stage 2 — per-field translation**

| field | bucket | action | machine subquery |
|-------|--------|--------|------------------|
| drugs | early contributor | `lookup_drugs("Sunitinib")` → Sunitinib (+ salt Sunitinib Malate); use fuzzy | `MATCH drugsFuzzy = ["Sunitinib*"]` |
| species | early contributor | `lookup_species("human")` → Human | `MATCH species = "Human"` |
| route | early contributor | `lookup_route("oral")` → Oral | `MATCH routes = "Oral"` |
| parameter | open set | `MATCH parameter = "AUC"` with optional zero-count probe |

**Stage 3 — aggregation (with PK invariants)**

```json
{
  "query": {
    "AND": [
      { "MATCH": { "field": "drugsFuzzy", "value": ["Sunitinib*"] } },
      { "MATCH": { "field": "species",    "value": "Human" } },
      { "MATCH": { "field": "routes",     "value": "Oral" } },
      { "OR": [
        { "MATCH": { "field": "concomitants", "value": "Fasted" } },
        { "EMPTY": { "field": "concomitants" } }
      ]},
      { "MATCH": { "field": "tissueSpecific",         "value": "Not tissue-specific" } },
      { "MATCH": { "field": "metabolitesEnantiomers", "value": "Not metabolites/enantiomers" } }
    ]
  },
  "displayColumns": ["drug", "parameter", "dose", "route"]
}
```

Live execution can probe the `parameter` filter in isolation. A confirmed
zero-count probe drops the filter and records a warning; probe errors keep the
filter.

---

## Example B — "Cmax of Cabozantinib in adults with hepatic impairment after oral administration"

Shows open-set fields needing synonym handling plus **service invariants**.

**Stage 2** highlights:

| field | bucket | machine subquery |
|-------|--------|------------------|
| drugs | early contributor | `MATCH drugsFuzzy = "Cabozantinib*"` |
| species | early contributor | `MATCH species = "Human"` |
| route | early contributor | `MATCH routes = "Oral"` |
| parameter | open set | `MATCH parameter = "Cmax"` |
| studyGroup | open set | `REGEX studyGroup` matching hepatic impairment synonyms |
| age | open set | `REGEX age = "adult"` |

**Stage 3** injects the PK **invariants** automatically into the closed-filter
query:
`metabolitesEnantiomers = "Not metabolites/enantiomers"`, `tissueSpecific =
"Not tissue-specific"`, and the `concomitants` Fasted-or-empty OR block — none of
which the user said, but all of which the PK service always requires. Live
execution can probe the open-set `parameter`, `studyGroup`, and `age` filters in
isolation before final aggregation.

---

## Example C — "What is the half-life of Sunitinib in rats after oral administration in fasted state?"

Shows a PK question with explicit concomitant state that overrides the default
invariant.

**Stage 1**

```json
[
  { "field": "drugs",        "nl_fragment": "Sunitinib",   "type": "filter",   "reason": "The user restricts results to the drug sunitinib.",      "source": "termite:DRUG" },
  { "field": "species",      "nl_fragment": "rats",        "type": "filter",   "reason": "The user restricts results to rat studies.",             "source": "termite:SPECIES" },
  { "field": "routes",       "nl_fragment": "oral",        "type": "filter",   "reason": "The user restricts results to oral administration.",      "source": "termite:ROUTE" },
  { "field": "concomitants", "nl_fragment": "fasted state","type": "filter",   "reason": "The user specifies fasted concomitant conditions.",       "source": "llm" },
  { "field": "parameter",    "nl_fragment": "half-life",   "type": "filter",   "reason": "The user restricts results to half-life PK records.",     "source": "termite:PARAMETER" },
  { "field": "value",        "nl_fragment": "what is the half-life", "type": "question", "reason": "The user wants the t½ value reported.", "source": "llm" }
]
```

**Stage 2**

| field | bucket | machine subquery |
|-------|--------|------------------|
| drugs | early contributor | `MATCH drugsFuzzy = ["Sunitinib*"]` |
| species | early contributor | `MATCH species = "Rat"` |
| route | early contributor | `MATCH routes = "Oral"` |
| concomitants | early contributor | `MATCH concomitants = "Fasted"` (user stated; invariant not added again) |
| parameter | open set | `MATCH parameter = "half-life"` with optional zero-count probe |

**Stage 3**

Because the user explicitly specified `concomitants = Fasted`, the service
invariant does not add a second concomitants constraint.

```json
{
  "query": {
    "AND": [
      { "MATCH": { "field": "drugsFuzzy",              "value": ["Sunitinib*"] } },
      { "MATCH": { "field": "species",                 "value": "Rat" } },
      { "MATCH": { "field": "routes",                  "value": "Oral" } },
      { "MATCH": { "field": "concomitants",            "value": "Fasted" } },
      { "MATCH": { "field": "tissueSpecific",          "value": "Not tissue-specific" } },
      { "MATCH": { "field": "metabolitesEnantiomers",  "value": "Not metabolites/enantiomers" } }
    ]
  },
  "displayColumns": ["drug", "parameter", "dose", "route"]
}
```
