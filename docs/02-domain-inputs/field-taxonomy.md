# The two sets of searchable fields

This is the central design distinction. Every searchable field falls into one of
two buckets, and the bucket determines **how Stage 2 produces its value**.

## Set A — Closed-vocabulary (CSV-backed) fields

The complete set of legal values exists on disk as a taxonomy CSV in
[inputs/](../../inputs/). For these fields we **must not** let the model invent a
value — we ground it against the CSV (see
[../03-proposed-design/grounding-and-tool-calling.md](../03-proposed-design/grounding-and-tool-calling.md))
and we can exploit the hierarchy for expansion.

| Field | Backing CSV | Rows | Hierarchical? | Typical operator |
|-------|-------------|------|---------------|------------------|
| `drugs` / `drugsFuzzy` | [drugs.csv](../../inputs/drugs.csv) | 5,227 | yes (drug → class via `parent_name`) | `MATCH` (+ trailing `*` for fuzzy) |
| `effects` | [effects.csv](../../inputs/effects.csv) | 12,724 | yes (MedDRA-style) | `MATCH` with expanded value list |
| `indications` | [indications.csv](../../inputs/indications.csv) | 3,152 | yes | `MATCH` (often via `entityFilters`) |
| `species` | [species.csv](../../inputs/species.csv) | 286 | yes (class → members, e.g. Rodent/Primate) | `MATCH` with expanded list |
| `route` | [route.csv](../../inputs/route.csv) | 204 | flat (+ usage counts) | `MATCH` |
| `toxicityParameter` | [toxicity_parameters.csv](../../inputs/toxicity_parameters.csv) | 33 | yes | `MATCH` |
| `documentSource` / `sources` | [sources.csv](../../inputs/sources.csv) | 56 | yes (doc → FDA/EMA parent) | `MATCH` |
| `doseType` | [dose_type.csv](../../inputs/dose_type.csv) | 7 | flat enum | `MATCH` |
| `documentYear` | [document_year.csv](../../inputs/document_year.csv) | 118 | flat (years + ranges) | `MATCH` / `RANGE` / `DATE_RANGE` |
| `targets` | *(taxonomy exists; no CSV shipped here yet — see note)* | — | yes | `MATCH` / `entityFilters` |

> **Note on `targets`:** [enums.csv](../../inputs/enums.csv) lists `Targets` /
> `ActivityTargets` as real `FuzzyLookupFilter` taxonomies, and the gold set uses
> targets (Q21 CDK4), but no `targets.csv` is present in `inputs/`. It is
> conceptually a closed-vocabulary field; the taxonomy export is an
> [open question](../03-proposed-design/architecture.md#open-questions).

### Sub-case: tiny fixed enums

Some closed fields have so few values that a CSV lookup is overkill — they can be
inlined into the Stage-2 translator as a fixed enum rather than a tool call:

| Field | Allowed values | Source |
|-------|----------------|--------|
| `sex` | Male, Female, Both | prompts / fields |
| `doseType` | overdose, repeated, single, single/repeated, single/twice, twice, twice/repeated | [dose_type.csv](../../inputs/dose_type.csv) |
| `metabolitesEnantiomers` (PK) | Not metabolites/enantiomers, Metabolite, Enantiomer | PK prompt |
| `concomitants` (PK) | Fed, Fasted | PK prompt |
| `tissueSpecific` (PK) | Tissue-specific, Not tissue-specific | PK prompt |
| `isPreclinical` | true, false | boolean |

They are still "closed", just handled inline. The `FuzzyLookupFilter.taxonomy`
list in [enums.csv](../../inputs/enums.csv) enumerates which taxonomies the
back-end fuzzy-lookup endpoint can resolve (Drugs, Effects, Species, Sources,
Routes, Indications, Targets, PKParameters, ToxicityParameters, Concomitants, …)
— a useful cross-check on which fields are genuinely closed-vocabulary.

## Set B — Open (LLM-decides) fields

We cannot enumerate the values, so the LLM produces them directly — usually as a
`REGEX` (free-text substring) or a `RANGE` (numeric threshold).

| Field | Why open | Typical operator |
|-------|----------|------------------|
| `studyGroup` | free text; needs synonym expansion (e.g. hepatic impairment → cirrhosis, Child-Pugh B/C, …) | `REGEX` |
| `parameterComment` | free-text qualifier (e.g. "Maternal toxicity") | `MATCH`/`REGEX` |
| `parameterDisplay` (PK) | tissue + metabolite names | `REGEX` |
| `dose` | free numeric+unit text | `MATCH`/`REGEX` |
| `valueNormalized` / `valueMin…` / `valueMax…` (PK) | continuous numeric, unit-normalized | `RANGE` |
| `ages` | substring/category (gold set: "substring search adult") | `REGEX` |
| `comorbidities`, `diseaseName`, `raceEthnicity`, `galenicForm`, … | free text | `MATCH`/`REGEX` |
| metabolite names | open identifiers | `REGEX` |

## Decision rule (used by Stage 1 routing & Stage 2)

```
Is there a taxonomy CSV (or fuzzy-lookup taxonomy) for this field?
├─ yes → CLOSED-VOCAB: ground the value against the CSV via tool calling;
│         expand along the hierarchy if the user named a class/rollup.
└─ no  → OPEN: let the LLM produce the value (REGEX for text, RANGE for numbers),
          applying any service-specific synonym-expansion guidance.
```

The complete field list (response side) is in
[inputs/fields.csv](../../inputs/fields.csv); the request-side criteria and their
types are in [inputs/query_criteria_fields.csv](../../inputs/query_criteria_fields.csv).
