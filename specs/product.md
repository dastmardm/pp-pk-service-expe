# Product Specification

## Sources

- `docs/README.md`
- `docs/domain.md`
- `docs/evaluation.md`
- `docs/examples.md`
- `docs/implementation.md`
- `docs/index.md`
- `docs/pipeline.md`
- `docs/agent-dag.drawio`
- `docs/PPPK.xlsx`

## Purpose

`oppp` translates PharmaPendium pharmacokinetics (PK) questions written in natural language into structured requests for the PK advanced search endpoint. It lets a PK user ask questions such as which drugs, species, routes, parameters, doses, or study conditions match a clinical or preclinical PK intent, then returns the final matching row count used by evaluation.

The product is centered on count-correct retrieval, not free-form answer generation. Its primary job is to preserve the user intent across query expansion, field decomposition, entity enrichment, API-side filtering, local row filtering, and final count reporting.

## Core Capabilities

1. Expand terse or abbreviated PK questions while preserving the original meaning.
2. Decompose the expanded question into typed components with these fields:
   - `field`
   - `nl_fragment`
   - `type`
   - `reason`
   - `source`
   - optional boolean grouping metadata
3. Use each decomposition component's `field` as the TERMite enrichment context for that component's `nl_fragment`.
4. Classify PK request fields into operational buckets:
   - Small closed / early fields: closed fields with fewer than `1000` possible values.
   - Closed fields: closed fields with `1000` or more possible values.
   - Enum fields.
   - Boolean fields.
   - Open fields.
5. Translate small closed / early fields first, aggregate them, and query the API for a count.
6. If the early query returns fewer than `1000` rows, fetch those rows and apply all remaining filters locally.
7. If the early query returns `1000` rows or more, progressively translate additional non-early filters, aggregate, and query again until either:
   - the count is below `1000`, then rows are fetched and remaining filters are applied locally; or
   - all filters have been translated into the API query, then the final API count is used.
8. Report the final row count for each question.
9. Evaluate only against the `PK_Query` sheet in `docs/PPPK.xlsx`, using the expected row count as the sole scored assertion.

## Key Actors

- PK analyst: writes natural-language PK search questions and inspects the resulting row count.
- Evaluation runner: executes the gold-set questions from `docs/PPPK.xlsx` and compares final counts with the expected counts.
- Pipeline maintainer: updates field routing, closed-set vocabularies, TERMite mappings, and staged execution behavior.

## Data Flow

1. A PK question enters the pipeline.
2. Query expansion clarifies abbreviations or compact language.
3. Query decomposition produces typed components and includes a `reason` explaining each routing decision.
4. TERMite enrichment runs after decomposition, scoped to each component's selected `field` and `nl_fragment`.
5. Small closed / early components are translated and aggregated into an initial API query.
6. The API count decides the execution path:
   - count `< 1000`: fetch rows, then apply untranslated filters locally;
   - count `>= 1000`: translate more filters into the API query and repeat count checking.
7. The product emits the final filtered row count:
   - row path: the count of locally filtered fetched rows;
   - full API path: the final `countTotal`.

## Integration Surface

- Input: a natural-language PK question.
- Main external search endpoint: `/v1/pk/search/advanced`.
- Gold evaluation workbook: `docs/PPPK.xlsx`.
- Gold evaluation sheet: `PK_Query`.
- Required gold columns:
  - `Quety number`
  - `Query`
  - `Expected Count`

PK fields and their product buckets are:

| Bucket | Fields |
| --- | --- |
| Small closed / early | `species`, `routes`, `documentSource`, `documentYear` |
| Closed | `drugs` |
| Enum | `sex` |
| Boolean | `isPreclinical` |
| Enum/invariant | `concomitants`, `tissueSpecific`, `metabolitesEnantiomers` |
| Open | `parameter`, `parameterDisplay`, `studyGroups`, `age`, `dose`, `duration` |

The documented closed-set counts are:

| Field | Value count |
| --- | ---: |
| `drugs` | `5226` |
| `species` | `285` |
| `routes` | `203` |
| `documentSource` | `55` |
| `documentYear` | `117` |

## Operational Model

The system supports repeatable command-line runs, stage-level inspection, service checks, and evaluation reporting. Evaluation is count-only: a case passes when the final row count exactly equals `Expected Count` from the `PK_Query` sheet.

The pipeline keeps auditability at each stage. Decomposition reasons explain why fragments were assigned to fields. TERMite enrichment records the recognized entities used to support translation. Runtime execution records whether the pipeline stopped at a fetched-row path or a full API-count path.

## Constraints and Non-Goals

- The PK row gate is exactly `1000`; the early path uses `< 1000`, and the staged path continues on `>= 1000`.
- Small closed / early classification is based on closed-set value count, not on field importance.
- `drugs` is closed but not early because it has more than `1000` values.
- TERMite enrichment must not run as a global pre-decomposition rewrite. It is scoped by the decomposition output field.
- Evaluation does not score stage artifacts, qualitative explanations, per-field filter labels, tolerance bands, or any workbook sheet other than `PK_Query`.
- The product does not answer the PK question in prose; it translates and counts matching rows.

## Open Questions

None.
