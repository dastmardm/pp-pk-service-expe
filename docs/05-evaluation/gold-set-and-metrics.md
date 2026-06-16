# Evaluation: gold set & metrics

A decomposed pipeline is only worth building if we can prove it beats the
monolith. The good news: the SME gold set is already shaped for **per-field**
evaluation, which the legacy design could never exploit.

## The gold set

[inputs/sme_expected_cases.csv](../../inputs/sme_expected_cases.csv) — 24 SME
questions. Each row gives:

- `question` — the NL input;
- `s` — the expected number of results (an end-to-end sanity check);
- `query_type` — the retrieval pattern (e.g. "Drug Name + Species → ADRs");
- one column per field with the **expected value(s)** (`drugsFuzzy, indications,
  targets, species, effects, parameterComment, toxicityParameter, doseType,
  route, ages, sex, studyGroup, isPreclinical, concomitants`);
- `comment` / `mapping_comment` — SME rationale and where the legacy system failed.

Because the expected output is already per-field, we can score each field
independently — exactly matching the Stage-2 output contract.

## Metric layers

### 1. Per-field accuracy (the new superpower)

For each (question, field) pair, compare the Stage-2 value set to the gold value
set:

- **Precision / recall / F1** over the set of resolved preferred labels (handles
  the `;`-separated multi-value cells and expansions).
- **Exact-set match** rate (did we get the whole field right?).
- Track separately for **closed-vocab** vs **open** fields — they fail
  differently (grounding/expansion errors vs free-text phrasing).

This pinpoints regressions to a single field translator instead of "the query
was wrong somewhere".

### 2. Decomposition quality (Stage 1)

- **Field-routing accuracy:** did every gold field get a subquery, and no
  spurious extra fields?
- **Role accuracy:** filter-vs-output classification (e.g. "at which dose" must be
  output, not a filter).
- **Boolean-hint accuracy:** OR vs AND within a field (Q13 vs Q14).

### 3. Hierarchy / expansion correctness

Targeted on the cases the legacy system failed:

- class → members (Q8, Q23, Q24), species class (Q6, Q23), preclinical set
  (Q7, Q16), MedDRA effect rollups (Q2, Q4, Q5, Q22).
- Metric: did the expanded set equal the SME's expected expansion?

### 4. End-to-end

- **Valid-query rate:** fraction that pass Stage-3 validation (a free win over the
  legacy regex-scrape).
- **Result-count proximity:** compare actual API `countTotal` to the gold `s`
  (within a tolerance band — counts drift as the DB updates, so treat as a signal
  not a hard gate).
- **Executable rate:** fraction the API accepts without error.

## Suggested harness

```
for case in sme_expected_cases.csv:
    pred = pipeline.run(case.question, service)
    record per-field P/R/F1 vs gold columns          # layer 1
    record routing & boolean correctness             # layer 2
    record expansion correctness on flagged cases    # layer 3
    (optional) execute pred against API, compare to s # layer 4
report: per-field table + per-stage rollup + diff vs legacy baseline
```

Run the **legacy translator** over the same gold set first to get a baseline, so
every redesign claim ("fewer invented values", "correct class expansion") is
backed by a number.

## Regression guard

Each fixed gold case becomes a frozen test: e.g. Q23 must always expand "Monkeys"
to the full monkey species set and resolve the `Monoclonal antibodies` class
node. Because translators are per-field, a fix to species expansion cannot
silently break drug resolution.

## Beyond the 24

The gold set is small and Safety-centric. To trust the system broadly:

- extend coverage to **PK** and **RTB** questions (the gold set is mostly Safety);
- add **negative cases** (out-of-scope questions, unknown drugs, empty results);
- add **ambiguity cases** (class-vs-target, brand-vs-generic) since those are the
  documented legacy failure mode.
