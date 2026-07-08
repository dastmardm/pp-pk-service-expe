# Evaluation: gold set & exact-count metrics

The evaluation contract is count-based. The translator runs a PharmaPendium PK
question through the fixed pipeline, executes the resulting API query when
execution is enabled, reads `countTotal`, and compares that count exactly with
the SME expected count.

## Gold dataset

The gold dataset is the **`PK_Query` sheet of [`PPPK.xlsx`](../PPPK.xlsx)**:
47 SME PK questions, each with an expected result count.

| Sheet | Rows | Purpose |
|-------|------|---------|
| `PK_Query` | 47 cases | Primary evaluation reference for `oppp eval`. Each row has a case identifier, the natural-language question, and the expected API count. |
| `Parameter_PK_Taxo_new` | 111 entries | PK parameter taxonomy with abbreviations, definitions, and synonyms. Useful reference material for open-set `parameter` translation. |
| `PP_PK_content` | 34 entries | Known content issues and expected resolutions linked to Jira tickets. |

Each row in `PK_Query` records:

- `Quety number` — literal workbook header for the sequential case identifier;
- `Query` — the natural-language question;
- `Expected Count` — the expected `countTotal` from the PharmaPendium PK API.

The `PK_Query` sheet is the only required gold source for automated scoring.
Stage-level artifacts are retained for debugging, but this documentation does
not define separate gold labels for Stage 0, Stage 1, Stage 2, or Stage 3.

## Field comparison surface

The pipeline can expose intermediate field outputs for diagnostics. These fields
use the same names as the translation contract:

| Field | Bucket | Notes |
|-------|--------|-------|
| `drugs` / `drugsFuzzy` | closed | Compare after removing API wildcard decoration such as a trailing `*`. `drugsFuzzy` values are arrays, including singleton arrays. |
| `species` | closed | Includes class/member expansion diagnostics. |
| `routes` | closed | Closed-set route of administration. |
| `parameter` | open | PK parameter retrieval filter emitted as a direct API constraint. |
| `parameterDisplay` | open | Display label emitted as a direct API constraint. |
| `studyGroups` | open | Study population descriptor, e.g. hepatic impairment. |
| `age` | open | Runtime/open field for PK age text. |
| `dose` | open | Runtime/open numeric/unit field. |
| `duration` | open | Runtime/open field for study duration. |
| `sex` | enum | Inline enum. |
| `concomitants` | enum/invariant | User value wins; otherwise the PK invariant supplies Fasted-or-empty. |
| `tissueSpecific` | enum/invariant | User value wins; otherwise the PK invariant supplies `Not tissue-specific`. |
| `metabolitesEnantiomers` | enum/invariant | User value wins; otherwise the PK invariant supplies `Not metabolites/enantiomers`. |
| `isPreclinical` | boolean | Boolean. |
| `documentSource` | closed | Source taxonomy. |
| `documentYear` | closed | Year/range field. |

## Metrics

`oppp eval` reports:

| Metric | Meaning |
|--------|---------|
| `valid_rate` | Fraction of cases whose final machine query passes validation. |
| `executed_rate` | Fraction of cases with an API execution result. |
| `exact_count` | Number of executed cases where `countTotal == Expected Count`. |
| `exact_count_rate` | `exact_count / executed cases`. |

The evaluation contract has no count band. A count is either an exact match or a
mismatch.

`oppp eval --no-execute` is an offline validity run. It can report query
validity and retained intermediate artifacts, but it does not produce exact-count
scores because no API count is available.

## Open-set probes

Open-set fields (`parameter`, `parameterDisplay`, `studyGroups`, `age`, `dose`,
`duration`) may be checked with isolated zero-count probes during live execution.
A confirmed zero-count probe drops the filter operationally and records a
warning. For evaluation, that warning is a hard mismatch for the case because a
retrieval-defining user constraint did not survive into the executable query.
Probe errors keep the filter and are reported as execution diagnostics.

## Suggested harness

```text
for case in PPPK.xlsx[PK_Query]:
    out = pipeline.run(case.Query, service="pk")
    validate final machine query
    execute final query when execution is enabled
    compare out.countTotal exactly to case.Expected Count
    retain Stage 0-3 artifacts for failure analysis
report: validity, execution, exact-count match, and per-case diagnostics
```

The retained artifacts make a wrong count traceable to TERMite recognition,
decomposition, closed-set translation, open-set direct constraints, aggregation,
or API execution. They are diagnostic evidence, not independently scored gold
labels in this contract.

## Regression cases

Representative cases to inspect when exact-count regressions occur:

- **Species class expansion** — "Rodent" resolves through the species hierarchy.
- **Drug fuzzy match** — misspellings such as "suntinib" resolve to `Sunitinib`.
- **Open-set parameter** — "AUC or Cmax" routes to the `parameter` field as an
  OR group.
- **PK invariants** — `concomitants`, `tissueSpecific`, and
  `metabolitesEnantiomers` defaults are applied unless the query explicitly
  supplies that field.
