# Evaluation

The evaluation contract assesses only expected row count. The harness reads the
`PK_Query` sheet from [`PPPK.xlsx`](PPPK.xlsx), runs each question through the
fixed pipeline, executes the count-gated query path when execution is enabled,
and compares the final returned row count exactly with `Expected Count`.

## PK_Query sheet

`PK_Query` is the only evaluation sheet. The required columns are:

| Column | Purpose |
|--------|---------|
| `Quety number` | Literal case id from the SME sheet. |
| `Query` | Natural-language PK question. |
| `Expected Count` | Expected number of result rows; this is the only scored label. |

No other workbook sheet, intermediate pipeline artifact, generated filter,
explanation, or qualitative answer is assessed.

## Scoring

The only scored assertion is:

```text
final_row_count == Expected Count
```

The final row count is selected from the branch that completes the pipeline:

| Branch | Final row count |
|--------|-----------------|
| Small-closed/early count below `1000` | Number of fetched datapoints remaining after closed, enum, boolean, invariant, and open row filters. |
| Closed count below `1000` | Number of fetched datapoints remaining after open-set row filters. |
| Closed count at least `1000` | `countTotal` from the full API query with open-set filters translated into API constraints. |

A case is either an exact row-count match or a mismatch. The evaluation contract
has no count band and no LLM judge.

`oppp eval --no-execute` performs an offline validity run. It can report query
validity and intermediate artifacts, but it does not produce an expected-row
score because no final row count is available.

## Diagnostics

The harness can retain operation artifacts so row-count mismatches can be
localized:

- TERMite annotations;
- decomposition components, selected field, field reason, and filter/question type;
- translated machine subqueries and grounding traces;
- count-gate branch decisions, fetched datapoints, row-filter decisions, final
  boolean tree, facets, display columns, validation issues, and warnings.

Diagnostics explain exact row-count failures; they are not assessed.
