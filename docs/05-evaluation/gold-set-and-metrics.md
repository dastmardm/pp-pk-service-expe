# Evaluation: per-step gold set & metrics

The whole point of this project is to **break one giant prompt into a chain of
small steps** (optional enhance → decompose → translate → aggregate). That only
pays off if we can **evaluate each step on its own** — otherwise we have traded
one opaque box for four. So evaluation here is **per-step first**: every stage
has a typed contract and an expected output we can score in isolation, and only
then do we roll the steps up to an end-to-end number.

Two SME gold datasets support this, at different granularities:

- **Per-step expected outputs — [`docs/sme_stage_cases.csv`](../sme_stage_cases.csv)**
  *(see [Status](#status)).* One
  column per pipeline step, so each stage's output can be diffed directly against
  what the SME expected at that step. This is the primary reference for per-step
  evaluation.
- **Per-field expected values — [`inputs/sme_expected_cases.csv`](../../inputs/sme_expected_cases.csv)**
  *(the original SME set).* One column per *field*, ideal for scoring Stage 2's
  per-field value selection (precision/recall over resolved labels).

The two are complementary: the per-field set scores *what value did each field
get*; the per-step set scores *what did each stage output* — entities, components,
subqueries, the boolean tree, and the final query.

## The per-step gold dataset (`docs/sme_stage_cases.csv`)

One row per SME question; one column per step of the pipeline. Each column holds
the **expected output of that step** in a compact, human-readable shorthand, so a
stage's actual output can be compared to it.

| Column | Step | What the cell records |
|--------|------|------------------------|
| `nl query` | input | The raw natural-language question. |
| `counts` | end-to-end | Expected result count (the API `countTotal`; same role as `s` in the per-field set). |
| `termite` | Stage 0 — enhance | Expected recognized entities as `TYPE:Label` pairs, with notes (e.g. *fuzzy on misspelled 'suntinib'*, *NOT recognized by TERMite — falls back to CSV fuzzy*, *MIS-TYPED by NER*). |
| `decompose` | Stage 1 — decompose | Expected components as `field[type]:"fragment"` (e.g. `drugs[filter]:"Sunitinib"; effects[question]:"ADRs"`), with boolean hints like `(OR)`. |
| `translate` | Stage 2 — translate | Expected per-field machine subqueries (`MATCH drugsFuzzy=["Sunitinib*"]; MATCH species="Human"; facet:effects`), with grounding/expansion notes (`(+salt Sunitinib Malate)`, `[neutropenia rollup, MedDRA]`, `[PT terms under "Hepatic and hepatobiliary disorders NEC"]`). |
| `aggregate` | Stage 3 — aggregate | Expected boolean structure + output options (`AND[ drugsFuzzy=[…], species="Human" ] \| facets=[effects]` / `\| displayColumns=[dose]`). |
| `machine query` | final | The fully rendered machine-query JSON payload the API receives. |

Because the columns line up with the stages, each stage's evaluator reads exactly
one column as its reference — there is no need to re-derive a stage's expectation
from the final query.

The shorthand notation is SME intent in a compact form. The comparators parse the
parts that are canonical enough to score deterministically; free-text nuances are
sent to the typed judge when needed.

## The per-field gold set (`inputs/sme_expected_cases.csv`)

[inputs/sme_expected_cases.csv](../../inputs/sme_expected_cases.csv) — 24 SME
questions, with one column per **field** rather than per step. Each row gives:

- `question` — the NL input;
- `s` — the expected number of results (an end-to-end sanity check);
- `query_type` — the retrieval pattern (e.g. "Drug Name + Species → ADRs");
- one column per field with the **expected value(s)** (`drugsFuzzy, indications,
  targets, species, effects, parameterComment, toxicityParameter, doseType,
  route, ages, sex, studyGroup, isPreclinical, concomitants`);
- `comment` / `mapping_comment` — SME rationale and where the legacy system failed.

Because the expected output is already per-field, we can score each field
independently — exactly matching the Stage-2 output contract. (See
[../02-domain-inputs/csv-catalog.md](../02-domain-inputs/csv-catalog.md) for the
full column layout.)

## Per-step evaluation (the core design)

Each step is scored against its own column with the comparator that fits its
output shape. Some are exact / set comparisons; **some require an LLM-as-judge**
because the output is free-text or has many equally-correct surface forms.

| Step | Gold column | Output shape | Comparator |
|------|-------------|--------------|------------|
| 0 — enhance | `termite` | set of `TYPE:Label` entities | **Set match** on (type, label) pairs → precision/recall. Tolerate the documented fallbacks (TERMite-miss → CSV fuzzy). |
| 1 — decompose (routing) | `decompose` | `field` + `type` per component | **Exact** on field-routing and filter-vs-question type; **set** on which fields appear (missing / spurious). |
| 1 — decompose (fragment) | `decompose` | the NL span per component | **LLM-as-judge**: spans are free text ("rats or mice", "at which dose"); judge semantic equivalence to the gold fragment. |
| 1 — decompose (boolean) | `decompose` | `(OR)` / `(AND)` hints | **Exact** on the per-field boolean hint. |
| 2 — translate (input closed set) | `translate` | resolved preferred-label set | **Set P/R/F1** over labels, after hierarchy expansion — deterministic. |
| 2 — translate (runtime closed set) | `translate` | selected subset of fetched field values | **Set P/R/F1** over fetched values when canonical; **LLM-as-judge** only when the gold value is free-text and several fetched strings are semantically equivalent. |
| 3 — aggregate (structure) | `aggregate` | boolean tree + facets / displayColumns | **Structural** compare of the normalized tree; **LLM-as-judge** tie-break when two trees are logically equivalent but shaped differently. |
| final | `machine query` / `counts` | full JSON payload | **Schema validity** + structural diff vs `machine query`; **count proximity** vs `counts` (tolerance band — see End-to-end below). |

This pins a failure to a single step: a wrong final count becomes traceable to a
mis-routed field in Stage 1, a bad expansion in Stage 2, or a wrong boolean in
Stage 3 — instead of "the query was wrong somewhere".

## LLM-as-judge (where exact match can't work)

Some steps emit outputs that have **no single correct string**, so a literal diff
would report false failures. For these we use a constrained LLM-as-judge that
takes *(the step's input, the gold cell, the actual output)* and returns a **typed
verdict** (`match | partial | miss` + a one-line reason), so judgements are
auditable and themselves checkable:

- **Stage 1 fragments** — "rats or mice" vs "rats, mice", "at which dose" vs
  "dose" carry the same intent; the judge scores semantic equivalence, not string
  equality. (Field/type routing is still scored deterministically.)
- **Stage 2 runtime closed-set post-filters** — a `studyGroup` value for
  "hepatic impairment" is selected from fetched datapoint values. Exact set
  scoring is used when the fetched value is canonical; the judge is used only to
  compare semantically equivalent free-text values.
- **Stage 3 structure (tie-break)** — when the actual boolean tree is logically
  equivalent to the gold one but nested differently, the judge confirms
  equivalence only after the cheap structural compare reports a difference.

To keep judge-based scores trustworthy: prefer a deterministic comparator wherever
the output *is* canonicalisable, constrain the judge to a small typed verdict, log
its reason, and (optionally) spot-check judge verdicts against SME labels. The
judge is the exception for free-text steps, not the default.

## Metric layers (rollup)

Per-step scores roll up into the layers below. Layers 1–3 read the per-step /
per-field columns; layer 4 reads `counts`.

### 1. Per-field accuracy

For each (question, field) pair, compare the Stage-2 value set to the gold value
set:

- **Precision / recall / F1** over resolved preferred labels (handles the
  `;`-separated multi-value cells and expansions).
- **Exact-set match** rate (did we get the whole field right?).
- Track **input closed-set** vs **runtime closed-set** fields separately — they
  fail differently (taxonomy grounding/expansion errors vs too-broad or too-empty
  fetched candidate sets).

### 2. Decomposition quality (Stage 1)

- **Field-routing accuracy:** did every gold field get a subquery, and no spurious
  extras?
- **Role accuracy:** filter-vs-question classification (e.g. "at which dose" must
  be a question, not a filter).
- **Boolean-hint accuracy:** OR vs AND within a field (Q13 vs Q14).

### 3. Hierarchy / expansion correctness

Targeted on the cases the legacy system failed:

- class → members (Q8, Q23, Q24), species class (Q6, Q23), preclinical set
  (Q7, Q16), MedDRA effect rollups (Q2, Q4, Q5, Q22).
- Metric: did the expanded set equal the SME's expected expansion (the `translate`
  column)?

### 4. End-to-end

- **Valid-query rate:** fraction that pass Stage-3 validation (a free win over the
  legacy regex-scrape).
- **Result-count proximity:** compare actual API `countTotal` to the gold `counts`
  (within a tolerance band — counts drift as the DB updates, so treat as a signal
  not a hard gate).
- **Executable rate:** fraction the API accepts without error.

## Suggested harness

```
for case in sme_stage_cases.csv:               # one row per question, one column per step
    out = pipeline.run(case.nl_query, service) # keep every intermediate artifact
    score step 0 vs case.termite               # set match (+ tolerated fallbacks)
    score step 1 vs case.decompose             # routing/type/boolean exact; fragment via judge
    score step 2 vs case.translate             # input/runtime closed-set F1; judge only for semantic free-text ties
    score step 3 vs case.aggregate             # structural; judge tie-break
    (optional) execute vs case.counts          # count proximity
report: per-step table + per-stage rollup + diff vs legacy baseline
```

Run the **legacy translator** over the same questions first to get a baseline, so
every redesign claim ("fewer invented values", "correct class expansion") is
backed by a number. Each stage is independently invokable (see
[../06-implementation/tech-stack.md](../06-implementation/tech-stack.md) →
*Isolation for evaluation*), so a step can be scored without running the rest.

## Regression guard

Each fixed gold case becomes a frozen **per-step** test: e.g. Q23 must always
expand "Monkeys" to the full monkey species set (its `translate` cell) and resolve
the `Monoclonal antibodies` class node. Because steps are scored independently, a
fix to species expansion cannot silently break drug resolution.

## Status

- **The per-step dataset is compact SME intent.** [`docs/sme_stage_cases.csv`](../sme_stage_cases.csv)
  is parsed by [eval/per_step.py](../../src/oppp/eval/per_step.py), which scores
  TERMite labels, decomposition routing/type pairs, translated field names, and
  final machine-query structure.
- **The CLI harness is count-based.** `oppp eval` runs
  [eval/harness.py](../../src/oppp/eval/harness.py): translate → optionally
  execute → compare `countTotal` to the `counts` column, with CSV/XLSX report
  export.
- **The typed judge is implemented.** [eval/judge.py](../../src/oppp/eval/judge.py)
  exposes `LLMJudge` and `JudgeVerdict` for fragment, open-pattern, and structure
  tie-breaks. Tests inject a fake client so the judge contract stays hermetic.
- **Coverage is Safety-centric.** The current SME sets focus on Safety questions;
  PK and RTB service configs exist, and their broader evaluation coverage is
  represented by targeted service tests.
