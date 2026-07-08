# Evaluation

The evaluation contract is count-based. The harness runs each gold question
through the fixed pipeline, executes the count-gated query path when execution is
enabled, and compares the final count exactly with the expected count in the
gold workbook.

## Gold workbook

The required gold source is [`PPPK.xlsx`](PPPK.xlsx), especially the `PK_Query`
sheet.

| Sheet | Purpose |
|-------|---------|
| `PK_Query` | 47 PK questions with a literal `Quety number` case id, natural-language `Query`, and `Expected Count`. |
| `Parameter_PK_Taxo_new` | PK parameter abbreviations, definitions, and synonyms used as reference material. |
| `PP_PK_content` | Known content issues and expected resolutions linked to Jira tickets. |

`PK_Query` is the only required gold source for automated scoring. Operation
artifacts are retained for diagnostics, but the docs do not define separate gold
labels for individual pipeline steps.

## Metrics

| Metric | Meaning |
|--------|---------|
| `valid_rate` | Fraction of cases whose final machine query passes validation. |
| `executed_rate` | Fraction of cases with an API execution result. |
| `exact_count` | Number of executed cases where the final API or row-filtered count equals `Expected Count`. |
| `exact_count_rate` | `exact_count / executed cases`. |

The evaluation contract has no count band. A count is either an exact match or a
mismatch.

`oppp eval --no-execute` performs an offline validity run. It can report query
validity and intermediate artifacts, but it does not produce exact-count scores.

## Staged execution scoring

The evaluated count is selected from the branch that completes the pipeline:

| Branch | Evaluated count |
|--------|-----------------|
| Small-closed/early count below `1000` | Number of fetched datapoints remaining after closed, enum, boolean, invariant, and open row filters. |
| Closed count below `1000` | Number of fetched datapoints remaining after open-set row filters. |
| Closed count at least `1000` | `countTotal` from the full API query with open-set filters translated into API constraints. |

The evaluation contract has no LLM judge and no count band. A final count is
either an exact match or a mismatch.

## Diagnostic artifacts

The harness keeps operation artifacts so failures can be localized:

- TERMite annotations;
- decomposition components, field routing, and filter/question type;
- translated machine subqueries and grounding traces;
- count-gate branch decisions, fetched datapoints, row-filter decisions, final
  boolean tree, facets, display columns, validation issues, and warnings.

These diagnostics explain exact-count failures; they are not independently scored
gold labels.
