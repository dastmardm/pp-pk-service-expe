# Product Specification

## Sources
- `docs/README.md`
- `docs/index.md`
- `docs/00-overview/problem-statement.md`
- `docs/00-overview/glossary.md`
- `docs/02-domain-inputs/csv-catalog.md`
- `docs/02-domain-inputs/field-taxonomy.md`
- `docs/02-domain-inputs/machine-query-schema.md`
- `docs/03-proposed-design/architecture.md`
- `docs/03-proposed-design/stage-1-decomposition.md`
- `docs/03-proposed-design/stage-2-subquery-translation.md`
- `docs/03-proposed-design/stage-3-aggregation.md`
- `docs/03-proposed-design/grounding-and-tool-calling.md`
- `docs/03-proposed-design/misspelling-strategy.md`
- `docs/04-examples/worked-examples.md`
- `docs/05-evaluation/gold-set-and-metrics.md`
- `docs/06-implementation/build-status.md`
- `docs/06-implementation/operations.md`
- `docs/06-implementation/streamlit-ui.md`
- `docs/06-implementation/tech-stack.md`

## Purpose
The product converts a natural-language PK question into the machine query the PharmaPendium PK API executes. It replaces the legacy single-prompt translator with a fixed, auditable pipeline that separates query expansion, entity recognition, field decomposition, grounded translation, aggregation, count execution, and post-filtering.

The central product rule: a filter value must come from a closed set before it can narrow results. Fields whose possible values are known before query execution are translated against those closed sets. Fields whose value space is not known until datapoints are fetched are deferred; the unique fetched values become runtime closed sets, and the same grounding translator selects the post-filter subset.

The v0.1 package implements Stage -1 through Stage 3, count execution, and the per-step evaluation harness. Full row fetching and runtime post-filtering are the documented intended path once row retrieval is available; in v0.1, open-set fields are emitted as direct `MATCH`/`REGEX` constraints with optional zero-count probe guards in live runs.

## Core Capabilities
- Accept a natural-language PK question and produce the structured machine query for the PharmaPendium PK API.
- Stage -1: produce a faithful expansion that clarifies abbreviations and wording without adding or removing intent, while preserving the original question.
- Stage 0: run TERMite NER over the decomposed per-field fragments to annotate entities with preferred labels and types. TERMite is required; missing TERMite config is a blocking error for full runs.
- Stage 1: decompose the expanded question into single-field components, each marked as a retrieval filter or a requested output, without consulting controlled vocabularies.
- Stage 2A: translate input closed-set filter components against CSV taxonomies, inline enums, and boolean domains using the documented resolution order.
- Stage 2B (row-level design): for large closed-set fields deferred past Stage 2A, derive a narrowed value list from early-contributor fetched datapoints and translate against that list; repeat until convergence.
- Stage 2C (row-level design): for open-set fields, translate against unique values observed in the final fetched datapoints and apply the selected subset as post-filters.
- Stage 3: aggregate valid Stage 2A subqueries into a structurally valid API query with service invariants, boolean grouping, facets, and display columns; execute for `countTotal`.
- Reject any translation result that contains values outside the field's closed set; record invalid translations in the audit trail without narrowing the query.
- Keep stage outputs independently inspectable via fixed CLI commands and the Streamlit UI without exposing alternative stage implementations.
- Evaluate quality per step, per field, and end to end against the SME gold set in `docs/PPPK.xlsx`.

## Key Actors
| Actor | Role |
|-------|------|
| Analyst | Asks the natural-language PK question and consumes the count and filtered results. |
| Subject-matter expert | Provides gold questions and expected result counts in `docs/PPPK.xlsx`. |
| Developer / evaluator | Runs fixed stage commands, inspects traces, updates tests, and evaluates regressions. |
| PharmaPendium PK API | Executes machine queries at `/v1/pk/search/advanced` and returns `countTotal` or datapoints. |
| TERMite entity recognizer | Supplies required entity labels, types, and synonyms for Stage 0. |
| Language model | Performs faithful Stage -1 expansion, vocab-free Stage 1 decomposition, Stage 2 translation enrichment/selection, Stage 3 aggregation planning, and LLM-as-judge semantic scoring. |

## Data Flow
1. The raw PK question enters the fixed pipeline.
2. Stage -1 produces a faithful expanded query and preserves the original text.
3. Stage 1 decomposes the expanded question into single-field components (no taxonomy lookup).
4. Stage 0 runs TERMite over the per-field fragments and annotates entity labels and types.
5. Stage 2A translates input closed-set filter components (CSV-backed fields, enums, booleans) against their known value sets.
6. Stage 3A assembles valid Stage 2A subqueries into the first API query, applies PK service invariants, and executes for `countTotal` (or datapoints when row fetch is available).
7. Stage 2B (row-level design): derives runtime narrowed sets from Stage 3A datapoints for large closed-set fields and translates new contributor subqueries.
8. Stage 3B (row-level design): assembles all contributor subqueries into the final API query and fetches final datapoints.
9. Stage 2C (row-level design): translates open-set filters against unique values in Stage 3B datapoints and post-filters rows.
10. The pipeline returns a typed result with every intermediate artifact plus issues.

## Integration Surface
- The pipeline targets the PK service on the PharmaPendium API (`/v1/pk/search/advanced`).
- Closed-set vocabularies come from five taxonomy CSVs (`drugs.csv`, `species.csv`, `route.csv`, `sources.csv`, `document_year.csv`), inline enum values (`sex`, `concomitants`, `tissueSpecific`, `metabolitesEnantiomers`), and booleans (`isPreclinical`).
- Open-set fields (`parameter`, `parameterDisplay`, `studyGroup`, `age`, `dose`, `duration`) become runtime closed sets only after datapoints are fetched.
- TERMite annotations seed routing and translation grounding but do not override closed-set authority.
- The evaluation gold set is the `PK_Query` sheet of `docs/PPPK.xlsx` (47 questions with expected counts). The `Parameter_PK_Taxo_new` sheet provides PK parameter taxonomy context.

## Operational Model
- The production path has no user-selectable stage methods and no no-op bypasses. TERMite and LLM credentials are required for full pipeline runs.
- CLI commands (`oppp run`, `oppp enhance`, `oppp decompose`, `oppp field`, `oppp aggregate`, `oppp lookup`, `oppp eval`, `oppp dag`) expose only service, input, execution, and output controls.
- The Streamlit UI (`streamlit run src/oppp/ui/app.py`) is a debug surface over the same fixed pipeline; it shows every stage output without stage backend selectors.
- Offline tests stay hermetic by injecting fakes and fixtures; fakes are not public product methods.
- Live execution posts to the PharmaPendium PK API. Count retrieval supports evaluation; row retrieval (when available) enables runtime post-filtering.

## Constraints and Non-Goals
- Closed-set filter values must never be emitted outside their closed set.
- Invalid translations must appear in the audit trail and be excluded from API queries and post-filters.
- Boolean intent (AND/OR/NOT) must be explicit in data, not implied by prose.
- Stage 1 must segment and route without consulting vocabularies.
- The normalizer policy is fixed per field/bucket and is not a selectable stage or runtime option.
- This product targets the PK service only. Safety and RTB service configuration may remain in the codebase for future use but are not active product scope in v0.1.
- The product consumes vocabularies and the gold set; it does not curate them.
- Live result counts can drift as the database updates; count metrics are tolerance-banded.
- The product is not a general conversational assistant and does not summarize records.

## Open Questions
None. All product-design facts are settled in the documented v0.1 scope above.
