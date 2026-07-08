# Evaluation: per-step gold set & metrics

The whole point of this project is to **break one giant prompt into a chain of
small steps** (TERMite enhance -> decompose -> translate -> aggregate). That
only pays off if we can **evaluate each step on its own** — otherwise we have
traded one opaque box for four. So evaluation here is **per-step first**: every
stage has a typed contract and an expected output we can score in isolation, and
only then do we roll the steps up to an end-to-end number.

The gold dataset is the **`PK_Query` sheet of [`PPPK.xlsx`](../PPPK.xlsx)**:
47 SME PK questions, each with an expected result count. The workbook also
includes a PK parameter taxonomy (`Parameter_PK_Taxo_new`) and a content-issues
log (`PP_PK_content`).

| Sheet | Rows | Purpose |
|-------|------|---------|
| `PK_Query` | 47 cases | The SME gold query set for PK evaluation. Each row has a query number, the natural-language question, and the expected result count. Used as the primary evaluation reference by the count-based harness (`oppp eval`). |
| `Parameter_PK_Taxo_new` | 111 entries | PK parameter taxonomy with abbreviations, definitions, and synonyms. Useful for open-set `parameter` field translation and evaluation. |
| `PP_PK_content` | 34 entries | Known content issues and their expected solutions, linked to Jira tickets. |

## The gold dataset (`PPPK.xlsx` → `PK_Query` sheet)

Each row in the `PK_Query` sheet records:

- `Quety number` — sequential case identifier;
- `Query` — the natural-language question;
- `Expected Count` — the expected `countTotal` from the PharmaPendium PK API.

The count-based harness (`oppp eval`) runs each query through the full pipeline
and compares the API `countTotal` against `Expected Count`. Per-step evaluation
scores each stage's output against the same questions using the comparators
described below.

## The per-field contract

The evaluator scores per-field Stage-2 output against these PK fields:

| CSV column | Logical field | Notes |
|------------|---------------|-------|
| `drugsFuzzy` | `drugs` | Compare after removing only API wildcard decoration such as a trailing `*`. |
| `species` | `species` | Includes class/member expansions. |
| `route` | `routes` | Closed-set route; pipeline logical field `route`, API field `routes`. |
| `parameter` | `parameter` | Open PK parameter field emitted as a direct API constraint. |
| `parameterDisplay` | `parameterDisplay` | Open display label emitted as a direct API constraint. |
| `studyGroup` | `studyGroup` | Open field; synonym-equivalent strings may use the typed judge. |
| `age` | `age` | Runtime/open field for PK age text. |
| `dose` | `dose` | Runtime/open numeric/unit field. |
| `duration` | `duration` | Runtime/open field for study duration. |
| `sex` | `sex` | Inline enum. |
| `concomitants` | `concomitants` | Enum/invariant field. |
| `tissueSpecific` | `tissueSpecific` | Enum/invariant field. |
| `metabolitesEnantiomers` | `metabolitesEnantiomers` | Enum/invariant field. |
| `isPreclinical` | `isPreclinical` | Boolean. |
| `documentSource` | `documentSource` | Closed-set source field. |
| `documentYear` | `documentYear` | Closed-set year/range field. |

Input closed-set fields are scored against Stage-2 machine subqueries. Open
fields are scored against their direct `MATCH` or `REGEX` constraints and any
recorded zero-count probe warnings.

## Per-step evaluation (the core design)

Each step produces a typed artifact that can be scored independently. The primary
gold reference is `PPPK.xlsx` (`PK_Query` sheet), which provides the question and
the expected `countTotal`. Per-step scoring uses the pipeline's intermediate
artifacts — decomposition components, translated subqueries, aggregated boolean
tree — compared against the expected end-to-end count and any manually verified
stage outputs.

| Step | What is scored | Comparator |
|------|---------------|------------|
| 0 — enhance | TERMite recognized entities (`TYPE:Label` pairs) | **Set match** on (type, label) pairs → precision/recall. Tolerate documented fallbacks (TERMite-miss → CSV fuzzy). |
| 1 — decompose (routing) | `field` + `type` per component | **Exact** on field-routing and filter-vs-question type; **set** on which fields appear (missing / spurious). |
| 1 — decompose (fragment) | the NL span per component | **LLM-as-judge**: spans are free text; judge scores semantic equivalence. |
| 1 — decompose (boolean) | `(OR)` / `(AND)` hints | **Exact** on the per-field boolean hint. |
| 2 — translate (input closed set) | resolved preferred-label set | **Set P/R/F1** over labels, after hierarchy expansion — deterministic. |
| 2 — translate (open set) | direct `MATCH` or `REGEX` constraints plus probe warnings | **Exact/structural** comparison for emitted fields; **LLM-as-judge** for semantically equivalent free-text patterns. |
| 3 — aggregate | boolean tree + facets / displayColumns | **Structural** compare of the normalized tree; **LLM-as-judge** tie-break for logically equivalent but differently shaped trees. |
| final | API JSON payload + count | **Schema validity** + **count proximity** vs `Expected Count`; tolerance band — see End-to-end below. |

This pins a failure to a single step: a wrong final count becomes traceable to a
mis-routed field in Stage 1, a bad expansion in Stage 2, or a wrong boolean in
Stage 3 — instead of "the query was wrong somewhere".

## LLM-as-judge (where exact match can't work)

Some steps emit outputs that have **no single correct string**, so a literal diff
would report false failures. For these we use a constrained LLM-as-judge that
takes *(the step's input, the expected output, the actual output)* and returns a **typed
verdict** (`match | partial | miss` + a one-line reason), so judgements are
auditable and themselves checkable:

- **Stage 1 fragments** — "rats or mice" vs "rats, mice", "at which dose" vs
  "dose" carry the same intent; the judge scores semantic equivalence, not string
  equality. (Field/type routing is still scored deterministically.)
- **Stage 2 open-set constraints** — a `studyGroup` pattern for "hepatic
  impairment" may be represented with equivalent free-text patterns. Exact
  comparison is used when the emitted value is canonical; the judge is used only
  to compare semantically equivalent free-text values.
- **Stage 3 structure (tie-break)** — when the actual boolean tree is logically
  equivalent to the gold one but nested differently, the judge confirms
  equivalence only after the cheap structural compare reports a difference.

To keep judge-based scores trustworthy: prefer a deterministic comparator wherever
the output *is* canonicalisable, constrain the judge to a small typed verdict, log
its reason, and (optionally) spot-check judge verdicts against SME labels. The
judge is the exception for free-text steps, not the default.

## Metric layers (rollup)

Per-step scores roll up into the layers below. Layers 1–3 score intermediate pipeline artifacts; layer 4 reads `Expected Count` from `PPPK.xlsx`.

### 1. Per-field accuracy

For each (question, field) pair, compare the Stage-2 value set to the gold value
set:

- **Precision / recall / F1** over resolved preferred labels (handles the
  `;`-separated multi-value cells and expansions).
- **Exact-set match** rate (did we get the whole field right?).
- Track **closed-set** vs **open-set** fields separately — they fail differently
  (taxonomy grounding/expansion errors vs too-broad or too-empty free-text
  constraints).

This layer is mandatory even when the end-to-end harness is count-based: the
evaluator must verify that `PPPK.xlsx` is loaded and that Stage-2 resolved
values can be compared against the expected per-field values for each question.

### 2. Decomposition quality (Stage 1)

- **Field-routing accuracy:** did every gold field get a subquery, and no spurious
  extras?
- **Role accuracy:** filter-vs-question classification (e.g. "at which dose" must
  be a question, not a filter).
- **Boolean-hint accuracy:** OR vs AND within a field (Q13 vs Q14).

### 3. Hierarchy / expansion correctness

Targeted on the cases requiring hierarchy expansion:

- species class → members (e.g. "Rodent" → Rat, Mouse, …), drug class → members.
- Metric: did the expanded set equal the expected expansion for the case?

### 4. End-to-end

- **Valid-query rate:** fraction that pass Stage-3 validation.
- **Result-count proximity:** compare actual API `countTotal` to `Expected Count` from `PPPK.xlsx`. Counts drift as the DB updates, so treat proximity as a signal, not a hard gate.
- **Executable rate:** fraction the API accepts without error.

## Suggested harness

```
for case in PPPK.xlsx[PK_Query]:              # one row per question
    out = pipeline.run(case.Query, service)   # keep every intermediate artifact
    score step 0 — TERMite entity recognition
    score step 1 — routing/type/boolean exact; fragment via judge
    score step 2 — closed-set F1 and open-set constraint quality; judge only for semantic free-text ties
    score step 3 — structural; judge tie-break
    execute when requested vs case.Expected Count  # API countTotal
report: per-step table + per-stage rollup
```

Each stage is independently invokable (see
[../06-implementation/tech-stack.md](../06-implementation/tech-stack.md) →
*Isolation for evaluation*), so a step can be scored without running the rest.

## Regression guard

Each fixed gold case becomes a frozen **per-step** test: e.g. Q23 must always
expand "Monkeys" to the full monkey species set (its `translate` cell) and resolve
the `Monoclonal antibodies` class node. Because steps are scored independently, a
fix to species expansion cannot silently break drug resolution.

Representative regression cases include:

- **Species class expansion** — "Rodent" must expand to all rodent species members via the species hierarchy.
- **Drug fuzzy match** — misspellings such as "suntinib" must resolve to `Sunitinib` via fuzzy lookup, not be dropped.
- **Open-set parameter** — "AUC or Cmax" must route to the `parameter` field as an OR group, not collapse to a single value.
- **PK invariants** — `concomitants`, `tissueSpecific`, and `metabolitesEnantiomers` defaults must be applied unless the query explicitly overrides them.

Generated implementation tasks and evaluation criteria must cover the same case
list so implementers and evaluators do not work from different regression sets.

