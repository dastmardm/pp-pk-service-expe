# Project Skeleton

## Purpose

This skeleton is the agreed file map for implementing the PK staged count pipeline. It is also the authoritative file-to-owner map for `specs/tasks.md`; every file listed here has exactly one WBS owner, and every owned file in `tasks.md` appears here.

## Directory Tree

```text
src/oppp/
  models.py                  <- typed pipeline, query, runtime, and execution contracts [owner: W1.1.1]
  services/
    base.py                  <- service field bucket model and early threshold [owner: W1.1.2]
    pk.py                    <- PK field metadata, vocabularies, facets, TERMite map [owner: W1.1.2]
  stages/
    decompose.py             <- decomposition contract behavior and compatibility with field-scoped enrichment [owner: W1.2.1]
    enhance.py               <- field-scoped TERMite component enrichment [owner: W1.2.1]
    translate.py             <- staged translation and pending-component tracking [owner: W1.2.2]
    aggregate.py             <- staged aggregation, invariants, validation, payload normalization support, row filters [owner: W1.2.3]
  execute.py                 <- API count and row retrieval support for staged execution [owner: W1.3.1]
  pipeline.py                <- production PK staged orchestrator and runtime result assembly [owner: W1.3.2]
  cli.py                     <- CLI output and command labels for staged execution [owner: W1.4.1]
  ui/
    app.py                   <- Streamlit stage/debug surface for staged execution [owner: W1.4.2]
  eval/
    harness.py               <- PK_Query exact-count evaluation harness and reports [owner: W1.4.3]
    compare.py               <- evaluation comparison helpers aligned to exact final counts [owner: W1.4.3]
tests/
  test_services.py           <- PK field bucket and service metadata tests [owner: W1.5.1]
  test_stages.py             <- decomposition, enrichment, translation, aggregation tests [owner: W1.5.1]
  test_pipeline.py           <- staged orchestration, row gate, final count tests [owner: W1.5.2]
  test_eval.py               <- PK_Query exact-count evaluation tests [owner: W1.5.2]
  test_per_step_eval.py      <- remove or repurpose legacy per-step evaluation coverage [owner: W1.5.2]
```

## File Inventory

| File | Layer | Purpose | Owner |
| --- | --- | --- | --- |
| `src/oppp/models.py` | Contracts | Defines typed stage, query, runtime execution, and final count result models. | `W1.1.1` |
| `src/oppp/services/base.py` | Service metadata | Defines service field bucket types and `EARLY_CONTRIBUTOR_THRESHOLD = 1000`. | `W1.1.2` |
| `src/oppp/services/pk.py` | Service metadata | Defines PK fields, small closed / closed / open / enum / boolean classification, facets, invariants, and TERMite mapping. | `W1.1.2` |
| `src/oppp/stages/decompose.py` | Stage | Produces typed components before TERMite enrichment. | `W1.2.1` |
| `src/oppp/stages/enhance.py` | Stage | Provides field-scoped TERMite enrichment bound to each decomposed component. | `W1.2.1` |
| `src/oppp/stages/translate.py` | Stage | Translates early and non-early components in deterministic stages and tracks pending components. | `W1.2.2` |
| `src/oppp/stages/aggregate.py` | Stage | Aggregates staged subqueries, applies invariants, validates fields/facets, and supports local row filtering. | `W1.2.3` |
| `src/oppp/execute.py` | Execution | Performs count and row retrieval against the PK advanced search endpoint. | `W1.3.1` |
| `src/oppp/pipeline.py` | Orchestration | Runs the production staged PK path and assembles `PipelineResult.final_row_count`. | `W1.3.2` |
| `src/oppp/cli.py` | Surface | Exposes staged execution and final count in CLI commands. | `W1.4.1` |
| `src/oppp/ui/app.py` | Surface | Displays staged runtime state in the Streamlit debug UI. | `W1.4.2` |
| `src/oppp/eval/harness.py` | Evaluation | Loads `docs/PPPK.xlsx` `PK_Query` rows and scores exact final counts. | `W1.4.3` |
| `src/oppp/eval/compare.py` | Evaluation | Provides exact-count comparison helpers used by reports or evaluation summaries. | `W1.4.3` |
| `tests/test_services.py` | Tests | Covers PK service buckets, threshold, field spelling, and invariants. | `W1.5.1` |
| `tests/test_stages.py` | Tests | Covers stage contracts, field-scoped enrichment, staged translation, aggregation, and row filters. | `W1.5.1` |
| `tests/test_pipeline.py` | Tests | Covers staged orchestration, threshold boundary behavior, execution modes, and `final_row_count`. | `W1.5.2` |
| `tests/test_eval.py` | Tests | Covers `PK_Query` loading, exact count scoring, and count-only report output. | `W1.5.2` |
| `tests/test_per_step_eval.py` | Tests | Removes or repurposes legacy per-step evaluation expectations so only count evaluation remains. | `W1.5.2` |

## Conventions

- Product behavior follows `docs/` through generated specs; source code does not introduce alternate product semantics.
- PK field bucket policy lives in `src/oppp/services/`, not in individual stages.
- Runtime data crossing stage boundaries uses Pydantic models or typed dataclasses, not ad hoc dictionaries.
- Public surfaces consume `PipelineResult.final_row_count`; they do not infer the final result from intermediate counts.
- `studyGroups` is the documented PK field spelling. Compatibility aliases may accept `studyGroup`, but emitted payloads and row filters use `studyGroups`.
- No migration files, database migrations, or env template changes are required for this implementation.
